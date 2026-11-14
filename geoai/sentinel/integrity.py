"""Identidade do JP2 usado. Não apaga um arquivo que já estava no disco."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

_HEX = set("0123456789abcdef")


def checksum_declared(value: object) -> bool:
    """Multihash SHA3-256 do STAC: prefixo 1620 e 32 bytes."""

    if not isinstance(value, str) or len(value) != 68 or not value.startswith("1620"):
        return False
    return all(char in _HEX for char in value[4:])


def grid_declared(tile_grid: object, band: str) -> bool:
    if not isinstance(tile_grid, dict) or not isinstance(tile_grid.get("epsg"), int):
        return False
    band_grid = tile_grid.get(band)
    if not isinstance(band_grid, dict):
        return False
    shape = band_grid.get("shape")
    transform = band_grid.get("transform")
    shape_ok = (
        isinstance(shape, list)
        and len(shape) == 2
        and all(isinstance(item, int) and item > 0 for item in shape)
    )
    transform_ok = (
        isinstance(transform, list)
        and len(transform) == 6
        and all(isinstance(item, (int, float)) for item in transform)
    )
    return shape_ok and transform_ok


def _sha3_digest(checksum: str) -> bytes:
    if not checksum_declared(checksum):
        raise PermissionError("checksum_oficial_desconhecido")
    return bytes.fromhex(checksum[4:])


def file_matches_checksum(path: Path, checksum: str) -> bool:
    expected = _sha3_digest(checksum)
    digest = hashlib.sha3_256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.digest() == expected


def _epsg_in_projection(projection: str, epsg: int) -> bool:
    compact = projection.upper().replace(" ", "")
    return (
        f'AUTHORITY["EPSG","{epsg}"]' in compact
        or f'ID["EPSG",{epsg}]' in compact
        or f"EPSG:{epsg}" in compact
    )


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 1e-6


def grid_matches(
    info: dict[str, Any],
    shape: list[int],
    transform: list[float],
    epsg: int,
) -> bool:
    """CRS, dimensões, resolução e origem. O transform é o afim do STAC."""

    geotransform = info.get("geotransform")
    if not isinstance(geotransform, tuple) or len(geotransform) != 6:
        return False
    if not _epsg_in_projection(str(info.get("projection") or ""), int(epsg)):
        return False
    rows, cols = int(shape[0]), int(shape[1])
    scale_x, rot_x, origin_x, rot_y, scale_y, origin_y = (
        float(item) for item in transform
    )
    origin_ok = _close(geotransform[0], origin_x) and _close(geotransform[3], origin_y)
    scale_ok = _close(geotransform[1], scale_x) and _close(geotransform[5], scale_y)
    rotation_ok = _close(geotransform[2], rot_x) and _close(geotransform[4], rot_y)
    return (
        int(info["rows"]) == rows
        and int(info["cols"]) == cols
        and origin_ok
        and scale_ok
        and rotation_ok
    )


def accept_used_jp2(
    path: Path,
    info: dict[str, Any],
    *,
    expected_bytes: int,
    checksum: str,
    shape: list[int],
    transform: list[float],
    epsg: int,
) -> None:
    """Confere o arquivo já escolhido. Divergência não apaga o JP2."""

    if path.stat().st_size != int(expected_bytes):
        raise PermissionError("tamanho_oficial_divergente")
    if not file_matches_checksum(path, checksum):
        raise PermissionError("checksum_oficial_divergente")
    if not grid_matches(info, shape, transform, epsg):
        raise PermissionError("grade_oficial_divergente")


def keep_or_drop_failed_download(path: Path, *, existed_before: bool) -> None:
    """Preserva o JP2 anterior. Remove só o arquivo criado nesta tentativa."""

    if not existed_before:
        path.unlink(missing_ok=True)


def band_contract(catalog: dict[str, Any], tile: str, band: str) -> dict[str, Any]:
    probe = catalog.get("access_probe_scene") or {}
    sizes = catalog.get("official_band_bytes") or probe.get("official_band_bytes") or {}
    checksums = (
        catalog.get("official_band_checksums")
        or probe.get("official_band_checksums")
        or {}
    )
    grids = catalog.get("official_grids") or probe.get("official_grids") or {}
    size = (sizes.get(tile) or {}).get(band)
    checksum = (checksums.get(tile) or {}).get(band)
    tile_grid = grids.get(tile) or {}
    band_grid = tile_grid.get(band) if isinstance(tile_grid, dict) else None
    if (
        not isinstance(size, int)
        or size <= 0
        or not checksum_declared(checksum)
        or not isinstance(tile_grid, dict)
        or not grid_declared(tile_grid, band)
        or not isinstance(band_grid, dict)
    ):
        raise RuntimeError("contrato_oficial_ausente")
    return {
        "expected_bytes": size,
        "checksum": checksum,
        "shape": list(band_grid["shape"]),
        "transform": [float(item) for item in band_grid["transform"]],
        "epsg": int(tile_grid["epsg"]),
    }
