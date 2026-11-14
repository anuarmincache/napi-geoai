"""Orçamento do piloto. Não baixa JP2 e não publica NDVI."""

from __future__ import annotations

import math
from typing import Any

from geoai.sentinel.assets import BANDS, https_path_matches
from geoai.sentinel.cdse_auth import MAX_ASSET_BYTES
from geoai.sentinel.integrity import checksum_declared, grid_declared

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


def transfer_allowance(expected_bytes: int, remaining_bytes: int) -> int:
    """Teto desta banda antes de abrir a conexão. Não passa do orçamento restante."""

    if (
        not isinstance(expected_bytes, int)
        or expected_bytes <= 0
        or expected_bytes > MAX_ASSET_BYTES
        or expected_bytes > remaining_bytes
    ):
        raise PermissionError("transferencia_acima_do_limite")
    return expected_bytes


def acquisitions_authorized_for_measure(catalog: dict[str, Any]) -> tuple[str, ...]:
    """Só a passagem selecionada. A reserva S2A exige autorização nova."""

    return (str(catalog["selected_acquisition"]["acquisition_id"]),)


def _official_size(table: dict[str, Any], tile: str, band: str) -> int | None:
    raw = (table.get(tile) or {}).get(band)
    if isinstance(raw, int) and raw > 0:
        return raw
    return None


def plan_from_catalog(catalog: dict[str, Any], free_bytes: int) -> dict[str, Any]:
    """Plano sem rede. JP2 completo e leitura recortada ficam separados."""

    products = _selected_products(catalog)
    probe = catalog.get("access_probe_scene") or {}
    assets = probe.get("assets") or {}
    official = (
        catalog.get("official_band_bytes")
        or probe.get("official_band_bytes")
        or {}
    )
    paths = (
        catalog.get("official_https_paths")
        or probe.get("official_https_paths")
        or {}
    )
    checksums = (
        catalog.get("official_band_checksums")
        or probe.get("official_band_checksums")
        or {}
    )
    grids = catalog.get("official_grids") or probe.get("official_grids") or {}
    bands: list[dict[str, Any]] = []
    for tile in TILES:
        for band in BANDS:
            href = (paths.get(tile) or {}).get(band)
            legacy = None
            if tile == "22KCV" and probe.get("product_id") == products[tile]:
                legacy = (assets.get(band) or {}).get("https_path")
            verified = (
                isinstance(href, str)
                and https_path_matches(href, products[tile], tile, band)
                and (not isinstance(legacy, str) or legacy == href)
            )
            size = _official_size(official, tile, band)
            checksum = (checksums.get(tile) or {}).get(band)
            identity = checksum_declared(checksum) and grid_declared(
                grids.get(tile),
                band,
            )
            bands.append(
                {
                    "tile": tile,
                    "band": band,
                    "product_id": products[tile],
                    "href_verified": verified,
                    "file_bytes": size,
                    "identity_declared": identity,
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
    unknown = sum(1 for band in bands if band["file_bytes"] is None)
    known_sizes = [int(band["file_bytes"]) for band in bands if band["file_bytes"]]
    complete = unknown == 0 and len(known_sizes) == len(bands)
    total = sum(known_sizes) if complete else None
    within_asset = complete and all(size <= MAX_ASSET_BYTES for size in known_sizes)
    metadata_ok = contract["matches_official_l2a"] is True
    memory_ok = working + mask <= MAX_MEMORY_BYTES and matrices > working
    disk_ok = (
        free_bytes >= MIN_FREE_DISK_BYTES
        and total is not None
        and free_bytes >= total * 2
    )
    transfer_ok = (
        total is not None and total <= MAX_TRANSFER_BYTES and within_asset
    )
    hrefs_ok = all(band["href_verified"] for band in bands)
    identity_ok = all(band["identity_declared"] for band in bands)
    bands_ok = len(bands) == 6
    download_allowed = bool(
        metadata_ok
        and memory_ok
        and disk_ok
        and transfer_ok
        and hrefs_ok
        and identity_ok
        and bands_ok
        and complete
    )
    return {
        "acquisition_id": catalog["selected_acquisition"]["acquisition_id"],
        "fallback_acquisition_id": catalog["fallback_acquisition_id"],
        "fallback_download": "not_authorized",
        "tiles": list(TILES),
        "n_bands": len(bands),
        "bands": bands,
        "full_jp2_download": "complete_file",
        "clipped_read": "gdal_window",
        "full_jp2_bytes": total,
        "full_jp2_unknown_assets": unknown,
        "full_jp2_ceiling_bytes": None,
        "size_rule": "official_stac_sum" if complete else "blocked_unknown_size",
        "identity_rule": (
            "official_sha3_and_grid" if identity_ok else "blocked_unknown_identity"
        ),
        "max_asset_bytes": MAX_ASSET_BYTES,
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
