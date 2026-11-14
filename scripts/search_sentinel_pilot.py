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
    describe_asset_response,
)
from geoai.sentinel.aoi import (  # noqa: E402
    footprint_coverage_m2,
    load_official_municipality,
    union_coverage_m2,
)
from geoai.sentinel.catalog import catalog_path  # noqa: E402
from geoai.sentinel.pilot import (  # noqa: E402
    MESH_RELATIVE,
    MIN_FOOTPRINT_COVERAGE,
    MIN_VALID_PIXEL_FRACTION,
    PILOT_CD_MUN,
    STAC_COLLECTION,
    STAC_COLLECTION_URL,
    STAC_SEARCH_URL,
)
from geoai.sentinel.selection import (  # noqa: E402
    rank_full_coverage,
    scene_is_accepted,
)
from geoai.sentinel.windows import choose_search_window, parse_as_of, search_windows  # noqa: E402

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


def _tile_rows(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for scene in scenes:
        tile = scene.get("mgrs_tile") or "desconhecida"
        row = grouped.setdefault(
            tile,
            {"mgrs_tile": tile, "max_aoi_coverage": 0.0, "n_scenes": 0},
        )
        row["n_scenes"] += 1
        coverage = float(scene.get("aoi_coverage") or 0.0)
        if coverage > row["max_aoi_coverage"]:
            row["max_aoi_coverage"] = coverage
    rows = list(grouped.values())
    rows.sort(key=lambda item: item["max_aoi_coverage"], reverse=True)
    return rows


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


def _best_intersecting(scenes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not scenes:
        return None

    def _cloud_key(item: dict[str, Any]) -> tuple[bool, float]:
        cloud = item.get("eo_cloud_cover")
        if cloud is None:
            return (True, 0.0)
        return (False, float(cloud))

    ordered = list(scenes)
    ordered.sort(key=lambda item: item.get("datetime") or "", reverse=True)
    ordered.sort(key=_cloud_key)
    ordered.sort(key=lambda item: float(item.get("aoi_coverage") or 0.0), reverse=True)
    return ordered[0]


def _public_scene(scene: dict[str, Any] | None) -> dict[str, Any] | None:
    if scene is None:
        return None
    return {key: value for key, value in scene.items() if not key.startswith("_")}


def _public_message(
    municipality_name: str,
    window_used: str,
    candidate: dict[str, Any] | None,
    http_status: int | None,
    scheme_names: list[str],
    union_coverage: float | None,
    probe_scene: dict[str, Any] | None,
) -> str:
    access = describe_asset_response(
        http_status=http_status,
        authorization_sent=False,
        scheme_names=scheme_names,
    )
    if candidate is None:
        covered = "n/d" if union_coverage is None else f"{union_coverage:.1%}"
        probe_bit = ""
        if probe_scene is not None:
            probe_bit = (
                f" A cena {probe_scene.get('product_id')} "
                f"({probe_scene.get('datetime')}), "
                f"tile {probe_scene.get('mgrs_tile')}, "
                f"cobre {probe_scene.get('aoi_coverage')} do polígono e serviu "
                f"apenas para inspecionar o acesso. {access}"
            )
        return (
            f"{municipality_name}: nenhuma cena L2A cobre pelo menos "
            f"{MIN_FOOTPRINT_COVERAGE:.1%} do polígono oficial em uma única "
            f"tile na janela {window_used}. A união dos footprints, um por "
            f"tile, cobre {covered}. Mosaico não foi montado.{probe_bit} "
            "A fração de pixels válidos na AOI não foi medida. "
            "Nenhum NDVI foi publicado."
        )
    return (
        f"{municipality_name}: cena {candidate.get('product_id')} "
        f"({candidate.get('datetime')}), tile {candidate.get('mgrs_tile')}, "
        f"cobertura geométrica {candidate.get('aoi_coverage')}. {access} "
        "A fração de pixels válidos na AOI não foi medida. "
        "Nenhum NDVI foi publicado."
    )


def _status(candidate: dict[str, Any] | None, http_status: int | None) -> str:
    if candidate is None:
        return "no_adequate_footprint"
    if http_status in (401, 403):
        return "assets_unauthorized"
    if http_status is not None and 200 <= http_status < 300:
        return "bands_reachable_pipeline_incomplete"
    return "bands_not_read"


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
    ranked_7d = rank_full_coverage(scenes_7d)
    window_used = choose_search_window(len(ranked_7d))
    features = features_7d
    scenes = scenes_7d
    ranked = ranked_7d
    truncated = truncated_7d
    if window_used == "30d":
        body["datetime"] = windows["30d"]
        features, truncated = _search_pages(body)
        scenes = _evaluate(features, municipality)
        ranked = rank_full_coverage(scenes)
    elapsed = time.perf_counter() - started

    top = ranked[0] if ranked else None
    if top is not None:
        top["accepted"] = scene_is_accepted(top.get("valid_pixel_fraction"))
    inspected = top if top is not None else _best_intersecting(scenes)
    per_tile = {}
    for scene in scenes:
        tile = scene.get("mgrs_tile") or "desconhecida"
        current = per_tile.get(tile)
        if current is None or scene["aoi_coverage"] > current["aoi_coverage"]:
            per_tile[tile] = scene
    union_coverage = union_coverage_m2(
        [scene["_geometry"] for scene in per_tile.values()],
        municipality,
    )
    for scene in scenes:
        scene.pop("_geometry", None)

    collection = _request_json(STAC_COLLECTION_URL)
    auth = collection_auth_summary(collection)
    scheme_names = sorted((auth.get("auth_schemes") or {}).keys())
    probe: dict[str, Any] | None = None
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
        if https_href:
            probe = _probe_https(str(https_href))
    http_status = None if probe is None else probe.get("http_status")
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
        inspected["meets_footprint_threshold"] = top is not None
        if top is not None:
            inspected["role"] = "footprint_candidate"
        else:
            inspected["role"] = "access_probe_only"
    catalog = {
        "status": _status(top, http_status),
        "ndvi_published": False,
        "pilot_aoi": True,
        "public_message_pt": _public_message(
            municipality.name,
            window_used,
            top,
            http_status,
            scheme_names,
            union_coverage,
            inspected,
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
                else "Nenhuma cena de 7 dias cobre o polígono no limiar geométrico."
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
        "candidate": _public_scene(top),
        "access_probe_scene": _public_scene(inspected),
        "tile_union_coverage": round(union_coverage, 6),
        "tiles": _tile_rows(scenes),
        "mosaic_required": top is None,
        "n_features_returned": len(features),
        "n_full_coverage": len(ranked),
        "n_features_7d": len(features_7d),
        "n_full_coverage_7d": len(ranked_7d),
        "downloaded_bytes": 0,
        "asset_access": {
            "probed_asset": None if inspected is None else "B04_10m",
            "https_host": ((inspected or {}).get("assets") or {})
            .get("B04_10m", {})
            .get("https_host"),
            "probe": probe,
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
    summary = {
        "status": catalog["status"],
        "window_used": window_used,
        "ndvi_published": False,
        "candidate": None
        if top is None
        else {
            "product_id": top.get("product_id"),
            "mgrs_tile": top.get("mgrs_tile"),
            "aoi_coverage": top.get("aoi_coverage"),
            "accepted": top.get("accepted"),
        },
        "http_status": http_status,
        "tile_union_coverage": catalog["tile_union_coverage"],
        "tiles": catalog["tiles"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
