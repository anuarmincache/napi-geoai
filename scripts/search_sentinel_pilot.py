"""Consulta o STAC oficial e grava o catálogo do piloto sem baixar bandas.

Uso:
py -3 scripts/search_sentinel_pilot.py --as-of 2026-11-14T18:00:00Z
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.sentinel.access import (  # noqa: E402
    collection_auth_summary,
    declared_asset_access,
)
from geoai.sentinel.aoi import (  # noqa: E402
    footprint_coverage_m2,
    load_official_municipality,
)
from geoai.sentinel.catalog import catalog_path  # noqa: E402
from geoai.sentinel.cdse_auth import (  # noqa: E402
    authorized_probe,
    credential_flags,
    unattempted_report,
)
from geoai.sentinel.passes import (  # noqa: E402
    minimal_covering_tiles,
    parse_product_id,
)
from geoai.sentinel.pilot import (  # noqa: E402
    MESH_RELATIVE,
    MIN_FOOTPRINT_COVERAGE,
    MIN_VALID_PIXEL_FRACTION,
    PILOT_CD_MUN,
    STAC_COLLECTION,
    STAC_COLLECTION_URL,
    STAC_SEARCH_URL,
)
from geoai.sentinel.windows import (  # noqa: E402
    choose_search_window,
    parse_as_of,
    search_windows,
)

_TILE = re.compile(r"_T(\d{2}[A-Z]{3})_")
_PAGE_CAP = 200


def _request_json(url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"resposta STAC inválida em {url}")
    return payload


def _search_pages(body: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    payload = _request_json(STAC_SEARCH_URL, body)
    features = list(payload.get("features") or [])
    truncated = False
    pages = 1
    while pages < 5:
        links = payload.get("links") or []
        nxt = next((item for item in links if item.get("rel") == "next"), None)
        if not isinstance(nxt, dict):
            break
        if len(features) >= _PAGE_CAP:
            truncated = True
            break
        href = str(nxt.get("href") or STAC_SEARCH_URL)
        nxt_body = nxt.get("body") if isinstance(nxt.get("body"), dict) else body
        payload = _request_json(href, nxt_body)
        features.extend(payload.get("features") or [])
        pages += 1
    overflow = len(features) > _PAGE_CAP
    return features[:_PAGE_CAP], truncated or overflow


def _mgrs_tile(feature: dict[str, Any]) -> tuple[str | None, str | None]:
    props = feature.get("properties") or {}
    if props.get("s2:mgrs_tile"):
        return str(props["s2:mgrs_tile"]), "s2:mgrs_tile"
    if props.get("grid:code"):
        return str(props["grid:code"]), "grid:code"
    match = _TILE.search(str(feature.get("id") or ""))
    if match:
        return match.group(1), "product_id"
    return None, None


def _candidate(feature: dict[str, Any], coverage: float) -> dict[str, Any]:
    assets = feature.get("assets") or {}
    red = assets.get("B04_10m") or {}
    nir = assets.get("B08_10m") or {}
    scl = assets.get("SCL_20m") or {}
    tile, tile_property = _mgrs_tile(feature)
    return {
        "product_id": feature.get("id"),
        "datetime": (feature.get("properties") or {}).get("datetime"),
        "eo_cloud_cover": (feature.get("properties") or {}).get("eo:cloud_cover"),
        "mgrs_tile": tile,
        "tile_property": tile_property,
        "aoi_coverage": round(coverage, 6),
        "accepted": False,
        "valid_pixel_fraction": None,
        "proj_code": red.get("proj:code"),
        "gsd_m": red.get("gsd"),
        "raster_scale": red.get("raster:scale"),
        "raster_offset": red.get("raster:offset"),
        "nodata": red.get("nodata"),
        "reported_b04_bytes": red.get("file:size"),
        "downloaded_bytes": 0,
        "assets": {
            "B04_10m": declared_asset_access(red),
            "B08_10m": declared_asset_access(nir),
            "SCL_20m": declared_asset_access(scl),
        },
    }


def _probe_https(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Range": "bytes=0-0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            status = int(response.status)
            www = response.headers.get("WWW-Authenticate")
            content_type = response.headers.get("Content-Type")
    except urllib.error.HTTPError as error:
        status = int(error.code)
        www = error.headers.get("WWW-Authenticate") if error.headers else None
        content_type = error.headers.get("Content-Type") if error.headers else None
    return {
        "authorization_sent": False,
        "http_status": status,
        "www_authenticate": www,
        "content_type": content_type,
        "body_stored": False,
    }


def _public_scene(scene: dict[str, Any] | None) -> dict[str, Any] | None:
    if scene is None:
        return None
    return {key: value for key, value in scene.items() if not key.startswith("_")}


def _public_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def _acquisition_plans(
    scenes: list[dict[str, Any]],
    municipality,
) -> list[dict[str, Any]]:
    import geopandas as gpd
    from shapely import make_valid
    from shapely.geometry import shape

    grouped: dict[str, list[tuple[dict[str, Any], dict[str, str]]]] = {}
    for scene in scenes:
        parsed = parse_product_id(str(scene.get("product_id") or ""))
        if parsed is None or not scene.get("_geometry"):
            continue
        grouped.setdefault(parsed["acquisition_id"], []).append((scene, parsed))
    plans = []
    aoi_metric = (
        gpd.GeoSeries([municipality.geometry], crs=municipality.crs)
        .to_crs(municipality.coverage_crs)
        .iloc[0]
    )
    for _acquisition_id, items in grouped.items():
        per_tile: dict[str, tuple[dict[str, Any], dict[str, str]]] = {}
        for scene, parsed in items:
            current = per_tile.get(parsed["mgrs_tile"])
            newer = parsed["processing_time"]
            if current is None or newer > current[1]["processing_time"]:
                per_tile[parsed["mgrs_tile"]] = (scene, parsed)
        names = list(per_tile)
        geometries = []
        for name in names:
            geom = shape(per_tile[name][0]["_geometry"])
            if not geom.is_valid:
                geom = make_valid(geom)
            geometries.append(geom)
        projected = gpd.GeoSeries(geometries, crs="EPSG:4326").to_crs(
            municipality.coverage_crs
        )
        tile_map = {name: projected.iloc[index] for index, name in enumerate(names)}
        measured = minimal_covering_tiles(
            tile_map,
            aoi_metric,
            MIN_FOOTPRINT_COVERAGE,
        )
        identity = per_tile[names[0]][1]
        tiles = []
        for name in names:
            scene, parsed = per_tile[name]
            tiles.append(
                {
                    "mgrs_tile": name,
                    "product_id": scene.get("product_id"),
                    "datetime": scene.get("datetime"),
                    "eo_cloud_cover": scene.get("eo_cloud_cover"),
                    "aoi_coverage": round(
                        float(measured["tile_coverages"].get(name, 0.0)),
                        6,
                    ),
                    "selected": name in measured["selected_tiles"],
                    "valid_pixel_fraction": None,
                }
            )
        probe_name = (
            measured["selected_tiles"][0] if measured["selected_tiles"] else names[0]
        )
        plans.append(
            {
                "acquisition_id": identity["acquisition_id"],
                "satellite": identity["satellite"],
                "sensing_time": identity["sensing_time"],
                "sensing_time_utc": identity["sensing_time_utc"],
                "relative_orbit": identity["relative_orbit"],
                "composition": "single_acquisition",
                "dates_combined": False,
                "union_coverage": round(float(measured["union_coverage"]), 6),
                "gap": round(float(measured["gap"]), 6),
                "overlap_coverage": round(float(measured["overlap_coverage"]), 6),
                "pass_union_coverage": round(float(measured["pass_union_coverage"]), 6),
                "selected_tiles": measured["selected_tiles"],
                "covers_threshold": measured["covers_threshold"],
                "mosaic_required": measured["mosaic_required"],
                "tiles": tiles,
                "_probe_scene": per_tile[probe_name][0],
            }
        )
    plans.sort(key=lambda item: item["sensing_time"], reverse=True)
    return plans


def _choose_acquisition(plans: list[dict[str, Any]]) -> dict[str, Any] | None:
    ready = [plan for plan in plans if plan.get("covers_threshold")]
    if not ready:
        return None
    ready.sort(key=lambda plan: plan["sensing_time"], reverse=True)
    return ready[0]


def _public_message(
    municipality_name: str,
    selected: dict[str, Any] | None,
    anonymous_status: int | None,
    auth_sentence: str,
) -> str:
    if selected is None:
        return (
            f"{municipality_name}: nenhuma passagem única cobre pelo menos "
            f"{MIN_FOOTPRINT_COVERAGE:.1%} do polígono oficial. "
            "Nenhum NDVI foi publicado."
        )
    tiles = ", ".join(selected.get("selected_tiles") or [])
    anonymous = ""
    if anonymous_status is not None:
        anonymous = (
            f" Uma requisição sem Authorization ao B04 de uma tile "
            f"selecionada respondeu HTTP {anonymous_status}."
        )
    return (
        f"{municipality_name}: passagem {selected.get('acquisition_id')} "
        f"({selected.get('sensing_time_utc')}, órbita "
        f"R{selected.get('relative_orbit')}) cobre "
        f"{selected.get('union_coverage')} do polígono com as tiles {tiles}. "
        f"Lacuna {selected.get('gap')}. "
        f"Sobreposição {selected.get('overlap_coverage')}. "
        "É uma única aquisição, não uma composição de datas. "
        f"{auth_sentence}{anonymous} "
        "A fração de pixels válidos não foi medida. "
        "O processamento raster não foi executado. Nenhum NDVI foi publicado."
    )


def _evaluate(features: list[dict[str, Any]], municipality) -> list[dict[str, Any]]:
    scenes = []
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        coverage = footprint_coverage_m2(geometry, municipality)
        scene = _candidate(feature, coverage)
        scene["_geometry"] = geometry
        scenes.append(scene)
    return scenes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Catálogo STAC do piloto Maringá")
    parser.add_argument("--as-of", default=None, help="Instante UTC RFC3339")
    args = parser.parse_args(argv)
    as_of = parse_as_of(args.as_of)
    windows = search_windows(as_of)
    municipality = load_official_municipality(REPO / MESH_RELATIVE, PILOT_CD_MUN)
    if municipality.cd_mun != PILOT_CD_MUN:
        raise SystemExit("a malha devolveu outro CD_MUN")

    started = time.perf_counter()
    body = {
        "collections": [STAC_COLLECTION],
        "bbox": municipality.bbox,
        "datetime": windows["7d"],
        "limit": 100,
    }
    features_7d, truncated_7d = _search_pages(body)
    scenes_7d = _evaluate(features_7d, municipality)
    plans_7d = _acquisition_plans(scenes_7d, municipality)
    adequate_7d = sum(1 for plan in plans_7d if plan.get("covers_threshold"))
    window_used = choose_search_window(adequate_7d)
    features = features_7d
    scenes = scenes_7d
    plans = plans_7d
    truncated = truncated_7d
    if window_used == "30d":
        body["datetime"] = windows["30d"]
        features, truncated = _search_pages(body)
        scenes = _evaluate(features, municipality)
        plans = _acquisition_plans(scenes, municipality)
    elapsed = time.perf_counter() - started
    selected = _choose_acquisition(plans)
    inspected = None if selected is None else selected.get("_probe_scene")
    for scene in scenes_7d:
        scene.pop("_geometry", None)
    for scene in scenes:
        scene.pop("_geometry", None)

    collection = _request_json(STAC_COLLECTION_URL)
    auth = collection_auth_summary(collection)
    probe: dict[str, Any] | None = None
    https_href = None
    if inspected is not None:
        raw = next(
            (
                feature
                for feature in features
                if feature.get("id") == inspected.get("product_id")
            ),
            None,
        )
        red = ((raw or {}).get("assets") or {}).get("B04_10m") or {}
        https_href = ((red.get("alternate") or {}).get("https") or {}).get("href")
        flags = credential_flags()
        if https_href and not (
            flags["password_grant_configured"] or flags["bearer_configured"]
        ):
            probe = _probe_https(str(https_href))
    http_status = None if probe is None else probe.get("http_status")
    if https_href and (
        credential_flags()["password_grant_configured"]
        or credential_flags()["bearer_configured"]
    ):
        try:
            authorized = authorized_probe(str(https_href))
        except (PermissionError, ValueError) as error:
            authorized = unattempted_report()
            authorized["token_error"] = error.__class__.__name__
    else:
        authorized = unattempted_report()
    if authorized.get("authorized_attempted"):
        auth_sentence = (
            "A requisição autorizada ao B04 leu "
            f"{authorized.get('bytes_read')} bytes "
            f"com HTTP {authorized.get('http_status')}."
        )
    else:
        auth_sentence = (
            "O ambiente local não tem credencial OIDC do CDSE. "
            "A requisição autorizada não foi enviada."
        )
    openid_url = ((auth.get("auth_schemes") or {}).get("oidc") or {}).get(
        "openIdConnectUrl"
    )
    issuer = None
    token_endpoint = None
    if isinstance(openid_url, str) and openid_url.startswith("https://"):
        try:
            document = _request_json(openid_url)
        except urllib.error.URLError:
            document = {}
        issuer = document.get("issuer")
        token_endpoint = document.get("token_endpoint")

    if inspected is not None:
        inspected["role"] = "mosaic_member_access_probe"
        inspected["accepted"] = False
    selection_status = "no_coverage" if selected is None else "mosaic_candidate"
    access_status = authorized.get("access_status") or "blocked_auth"
    if selected is None:
        catalog_status = "no_coverage"
    elif access_status != "authorized":
        catalog_status = "blocked_auth"
    else:
        catalog_status = "mosaic_candidate"
    catalog = {
        "status": catalog_status,
        "selection_status": selection_status,
        "access_status": access_status,
        "processing_status": "not_evaluated",
        "ndvi_published": False,
        "pilot_aoi": True,
        "public_message_pt": _public_message(
            municipality.name,
            selected,
            http_status,
            auth_sentence,
        ),
        "as_of_utc": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "queried_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stac_search_seconds": round(elapsed, 3),
        "aoi": {
            **municipality.public_dict(),
            "geometry_source": MESH_RELATIVE,
            "why_pt": (
                "AOI oficial aprovada na Issue #42 em 14/11/2026. "
                "Geometria, AREA_KM2 e bbox lidos da feição "
                f"CD_MUN {PILOT_CD_MUN} em {MESH_RELATIVE}."
            ),
        },
        "criteria": {
            "collection": STAC_COLLECTION,
            "search_order": ["7d", "30d"],
            "window_used": window_used,
            "windows_utc": windows,
            "widened_because": (
                None
                if window_used == "7d"
                else (
                    "Nenhuma passagem única dos 7 dias cobre o polígono "
                    "no limiar geométrico."
                )
            ),
            "temporal_rule": (
                "Um grupo é o mesmo satélite, o mesmo instante de aquisição "
                "no identificador do produto e a mesma órbita relativa. "
                "Datas diferentes não formam uma aquisição."
            ),
            "min_footprint_coverage": MIN_FOOTPRINT_COVERAGE,
            "min_valid_pixel_fraction": MIN_VALID_PIXEL_FRACTION,
            "coverage_method": (
                "Interseção do polígono oficial com o footprint STAC, "
                "em área no CRS métrico SIRGAS 2000 / UTM do centroide. "
                "A geometria STAC é tratada como EPSG:4326."
            ),
            "cloud_cover_role": (
                "Triagem do item. Não mede a fração válida dentro da AOI "
                "e não decide a troca de 7 para 30 dias."
            ),
            "stac_filter": "bbox",
            "truncated": truncated,
        },
        "candidate": None,
        "selected_acquisition": _public_plan(selected),
        "acquisitions": [_public_plan(plan) for plan in plans],
        "access_probe_scene": _public_scene(inspected),
        "mosaic_required": bool(selected and selected.get("mosaic_required")),
        "n_features_returned": len(features),
        "n_acquisitions": len(plans),
        "n_features_7d": len(features_7d),
        "n_acquisitions_7d": len(plans_7d),
        "n_adequate_acquisitions_7d": adequate_7d,
        "downloaded_bytes": 0,
        "asset_access": {
            "probed_asset": None if inspected is None else "B04_10m",
            "https_host": ((inspected or {}).get("assets") or {})
            .get("B04_10m", {})
            .get("https_host"),
            "anonymous_probe": probe,
            "authorized": authorized,
            "collection": auth,
            "openid_issuer": issuer,
            "openid_token_endpoint": token_endpoint,
            "s3_credentials_loaded": False,
        },
        "source": "Copernicus Data Space STAC sentinel-2-l2a",
        "source_url": STAC_SEARCH_URL,
    }
    path = catalog_path(REPO)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(path)
    chosen = catalog["selected_acquisition"] or {}
    summary = {
        "status": catalog["status"],
        "selection_status": catalog["selection_status"],
        "window_used": window_used,
        "ndvi_published": False,
        "acquisition_id": chosen.get("acquisition_id"),
        "sensing_time_utc": chosen.get("sensing_time_utc"),
        "selected_tiles": chosen.get("selected_tiles"),
        "union_coverage": chosen.get("union_coverage"),
        "gap": chosen.get("gap"),
        "overlap_coverage": chosen.get("overlap_coverage"),
        "mosaic_required": catalog["mosaic_required"],
        "authorized_attempted": authorized.get("authorized_attempted"),
        "anonymous_http_status": http_status,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
