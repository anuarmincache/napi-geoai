"""Consulta o STAC oficial e grava o catálogo do piloto sem baixar bandas.

Uso:
py -3 scripts/search_sentinel_pilot.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.sentinel.catalog import catalog_path  # noqa: E402
from geoai.sentinel.pilot import (  # noqa: E402
    PILOT_AREA_KM2,
    PILOT_BBOX,
    PILOT_CD_MUN,
    PILOT_CRS,
    PILOT_NAME,
    STAC_COLLECTION,
    STAC_SEARCH_URL,
)
from geoai.sentinel.selection import (  # noqa: E402
    footprint_coverage,
    rank_full_coverage,
    scene_is_accepted,
)

MESSAGE = (
    "Há uma cena Sentinel-2 L2A no STAC do Copernicus Data Space que cobre "
    "Pinhais nos últimos 7 dias. As bandas não foram lidas: o download HTTPS "
    "responde 401 sem credencial OIDC. A fração de pixels válidos na AOI não "
    "foi medida. Nenhum NDVI foi publicado."
)


def _search(datetime_range: str) -> tuple[dict, float]:
    body = {
        "collections": [STAC_COLLECTION],
        "bbox": PILOT_BBOX,
        "datetime": datetime_range,
        "limit": 20,
    }
    request = urllib.request.Request(
        STAC_SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    return payload, time.perf_counter() - started


def _aoi_geometry() -> dict:
    import geopandas as gpd

    frame = gpd.read_file(REPO / "data" / "raw" / "ibge" / "PR_Municipios_2025.zip")
    row = frame[frame["CD_MUN"].astype(str) == PILOT_CD_MUN]
    from shapely.geometry import mapping

    return mapping(row.geometry.iloc[0])


def _candidate(feature: dict, coverage: float) -> dict:
    assets = feature.get("assets") or {}
    red = assets.get("B04_10m") or {}
    return {
        "product_id": feature.get("id"),
        "datetime": (feature.get("properties") or {}).get("datetime"),
        "eo_cloud_cover": (feature.get("properties") or {}).get("eo:cloud_cover"),
        "aoi_coverage": coverage,
        "accepted": False,
        "valid_pixel_fraction": None,
        "proj_code": red.get("proj:code"),
        "gsd_m": red.get("gsd"),
        "raster_scale": red.get("raster:scale"),
        "raster_offset": red.get("raster:offset"),
        "nodata": red.get("nodata"),
        "reported_b04_bytes": red.get("file:size"),
        "downloaded_bytes": 0,
    }


def main() -> int:
    aoi = _aoi_geometry()
    windows = {
        "7d": "2026-11-07T00:00:00Z/2026-11-14T23:59:59Z",
        "30d": "2026-10-15T00:00:00Z/2026-11-14T23:59:59Z",
    }
    used = "7d"
    payload, elapsed = _search(windows["7d"])
    features = payload.get("features") or []
    if not features:
        used = "30d"
        payload, elapsed = _search(windows["30d"])
        features = payload.get("features") or []
    candidates = []
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        coverage = footprint_coverage(geometry, aoi)
        candidates.append(_candidate(feature, round(coverage, 6)))
    ranked = rank_full_coverage(candidates)
    top = ranked[0] if ranked else None
    if top is not None:
        top["accepted"] = scene_is_accepted(top.get("valid_pixel_fraction"))
    catalog = {
        "status": "blocked_credentials",
        "ndvi_published": False,
        "public_message_pt": MESSAGE,
        "queried_at_utc": datetime.now(UTC).isoformat(),
        "stac_search_seconds": round(elapsed, 3),
        "aoi": {
            "name": PILOT_NAME,
            "cd_mun": PILOT_CD_MUN,
            "area_km2_official": PILOT_AREA_KM2,
            "crs": PILOT_CRS,
            "bbox": PILOT_BBOX,
            "geometry_source": "data/raw/ibge/PR_Municipios_2025.zip",
            "why_pt": (
                "Menor AREA_KM2 oficial da malha IBGE 2025 no Paraná "
                "(61,008 km²), geometria válida no relatório QGIS, no fuso "
                "UTM 22S e pequena o bastante para um recorte de uma tile."
            ),
        },
        "criteria": {
            "collection": STAC_COLLECTION,
            "search_order": ["7d", "30d"],
            "window_used": used,
            "min_footprint_coverage": 0.999,
            "min_valid_pixel_fraction": 0.70,
            "cloud_cover_role": (
                "Triagem do item. Não mede a fração válida dentro da AOI."
            ),
        },
        "candidate": top,
        "n_features_returned": len(features),
        "n_full_coverage": len(ranked),
        "download_http_status": 401,
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
    summary = {"status": catalog["status"], "candidate": top}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
