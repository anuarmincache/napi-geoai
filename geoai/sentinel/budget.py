"""Orçamento do piloto. Não baixa JP2 e não publica NDVI."""

from __future__ import annotations

import math
from typing import Any

from geoai.sentinel.assets import BANDS

TILES = ("22KCV", "22KDV")
SELECTED_ACQUISITION = "S2B_20261112T133149_R081"
FALLBACK_ACQUISITION = "S2A_20261109T133231_R081"
BLOCK = 256
MAX_TRANSFER_BYTES = 750_000_000
MAX_MEMORY_BYTES = 512 * 1024 * 1024
MIN_FREE_DISK_BYTES = 5 * 1024 * 1024 * 1024
L2A_SCALE = 0.0001
L2A_OFFSET = -0.1
L2A_NODATA = 0
L2A_QUANTIFICATION = 10000
L2A_ADD_OFFSET = -1000


def envelope_pixels(bbox: list[float], gsd_m: float = 10.0) -> int:
    """Pixels do retângulo geográfico. É teto da AOI, não a contagem municipal."""

    minx, miny, maxx, maxy = (float(item) for item in bbox)
    mid = (miny + maxy) / 2.0
    width_m = (maxx - minx) * 111_320.0 * math.cos(math.radians(mid))
    height_m = (maxy - miny) * 110_540.0
    cols = math.ceil(width_m / gsd_m)
    rows = math.ceil(height_m / gsd_m)
    return int(cols * rows)


def block_working_bytes(block: int = BLOCK, n_tiles: int = 2) -> int:
    """Bytes das bandas de um bloco. A grade inteira não entra nesta conta."""

    pixels = block * block
    per_tile = pixels * (2 + 2 + 1 + 8 + 8)
    output = pixels * (8 + 1)
    return n_tiles * per_tile + output


def full_matrix_bytes(pixels: int, n_tiles: int = 2) -> int:
    """Bytes se B04, B08, SCL e o NDVI ficassem inteiros na memória."""

    return n_tiles * pixels * (8 + 8 + 1) + n_tiles * pixels * (8 + 1) + pixels * 8


def l2a_contract(
    scale: float,
    offset: float,
    nodata: int,
    baseline: int,
) -> dict[str, Any]:
    """L2A com baseline >= 0400 usa quantificação 10000 e offset -1000."""

    scale_ok = abs(float(scale) - L2A_SCALE) <= 1e-12
    offset_ok = abs(float(offset) - L2A_OFFSET) <= 1e-12
    nodata_ok = int(nodata) == L2A_NODATA
    baseline_ok = int(baseline) >= 400
    quantified = (1.0 + L2A_ADD_OFFSET) / L2A_QUANTIFICATION
    scaled = L2A_SCALE + L2A_OFFSET
    equivalent = abs(quantified - scaled)
    return {
        "matches_official_l2a": bool(
            scale_ok and offset_ok and nodata_ok and baseline_ok and equivalent <= 1e-12
        ),
        "scale": L2A_SCALE,
        "offset": L2A_OFFSET,
        "nodata": L2A_NODATA,
        "quantification": L2A_QUANTIFICATION,
        "add_offset": L2A_ADD_OFFSET,
        "baseline": int(baseline),
    }


def _baseline(product_id: str) -> int:
    marker = "_N"
    start = product_id.find(marker)
    if start < 0:
        raise ValueError("baseline ausente")
    digits = product_id[start + 2 : start + 6]
    if not digits.isdigit():
        raise ValueError("baseline ausente")
    return int(digits)


def _selected_products(catalog: dict[str, Any]) -> dict[str, str]:
    group = next(
        item
        for item in catalog["acquisitions"]
        if item["acquisition_id"] == catalog["selected_acquisition"]["acquisition_id"]
    )
    products = {
        tile["mgrs_tile"]: tile["product_id"]
        for tile in group["tiles"]
        if tile.get("selected") and tile["mgrs_tile"] in TILES
    }
    if set(products) != set(TILES):
        raise ValueError("tiles_ausentes")
    return products


def plan_from_catalog(catalog: dict[str, Any], free_bytes: int) -> dict[str, Any]:
    """Plano sem rede. JP2 completo e leitura recortada ficam separados."""

    products = _selected_products(catalog)
    probe = catalog.get("access_probe_scene") or {}
    assets = probe.get("assets") or {}
    known = probe.get("reported_b04_bytes")
    bands: list[dict[str, Any]] = []
    for tile in TILES:
        for band in BANDS:
            href = None
            verified = False
            size = None
            if tile == "22KCV" and probe.get("product_id") == products[tile]:
                href = (assets.get(band) or {}).get("https_path")
                verified = isinstance(href, str) and href.endswith("/$value")
                if band == "B04_10m" and isinstance(known, int):
                    size = known
            bands.append(
                {
                    "tile": tile,
                    "band": band,
                    "product_id": products[tile],
                    "href_verified": verified,
                    "file_bytes": size,
                    "transfer": "complete_jp2" if size is not None else "size_unknown",
                }
            )
    baseline = _baseline(products["22KCV"])
    contract = l2a_contract(
        float(probe.get("raster_scale")),
        float(probe.get("raster_offset")),
        int(probe.get("nodata")),
        baseline,
    )
    pixels = envelope_pixels(catalog["aoi"]["bbox"], float(probe.get("gsd_m") or 10))
    working = block_working_bytes()
    mask = pixels
    matrices = full_matrix_bytes(pixels)
    ceiling = None if not isinstance(known, int) else known * len(bands)
    metadata_ok = contract["matches_official_l2a"] is True
    memory_ok = working + mask <= MAX_MEMORY_BYTES and matrices > working
    disk_ok = free_bytes >= MIN_FREE_DISK_BYTES and (
        ceiling is not None and free_bytes >= ceiling * 2
    )
    transfer_ok = ceiling is not None and ceiling <= MAX_TRANSFER_BYTES
    hrefs_ok = sum(1 for band in bands if band["href_verified"]) == 3
    bands_ok = len(bands) == 6
    download_allowed = bool(
        metadata_ok and memory_ok and disk_ok and transfer_ok and hrefs_ok and bands_ok
    )
    return {
        "acquisition_id": catalog["selected_acquisition"]["acquisition_id"],
        "fallback_acquisition_id": catalog["fallback_acquisition_id"],
        "tiles": list(TILES),
        "n_bands": len(bands),
        "bands": bands,
        "full_jp2_download": "complete_file",
        "clipped_read": "gdal_window",
        "full_jp2_known_bytes": known if isinstance(known, int) else None,
        "full_jp2_unknown_assets": sum(
            1 for band in bands if band["file_bytes"] is None
        ),
        "full_jp2_ceiling_bytes": ceiling,
        "ceiling_rule": "each_band_le_known_b04",
        "aoi_pixels_envelope_estimate": pixels,
        "block": BLOCK,
        "block_working_bytes": working,
        "aoi_mask_bytes": mask,
        "full_matrix_bytes": matrices,
        "selected_memory": "gdal_blocks",
        "max_transfer_bytes": MAX_TRANSFER_BYTES,
        "max_memory_bytes": MAX_MEMORY_BYTES,
        "min_free_disk_bytes": MIN_FREE_DISK_BYTES,
        "disk_free_bytes": int(free_bytes),
        "metadata": contract,
        "metadata_ok": metadata_ok,
        "download_allowed": download_allowed,
        "download_started": False,
        "ndvi_published": False,
        "dates_combined": False,
    }
