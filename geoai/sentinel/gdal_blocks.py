"""Leitura em blocos e reflectância. O import do GDAL fica na função."""

from __future__ import annotations

from typing import Any

import numpy as np

from geoai.processing.ndvi import NDVI_DENOM_EPS, SCL_INVALID
from geoai.sentinel.mosaic_rule import compose_first_valid


def reflectance_block(
    dn: np.ndarray,
    *,
    scale: float,
    offset: float,
    nodata: float | int | None,
) -> np.ndarray:
    """DN * scale + offset. Nodata não recebe offset."""

    data = np.asarray(dn)
    out = np.full(data.shape, np.nan, dtype=np.float64)
    finite = np.isfinite(data.astype(np.float64))
    if nodata is None:
        mask = finite
    else:
        mask = finite & (data != nodata)
    out[mask] = data[mask].astype(np.float64) * float(scale) + float(offset)
    return out


def ndvi_pair(red: np.ndarray, nir: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """NDVI e máscara. Denominador nulo fica inválido. Sem clamp."""

    denom = nir + red
    valid = np.isfinite(red) & np.isfinite(nir) & (np.abs(denom) > NDVI_DENOM_EPS)
    out = np.full(red.shape, np.nan, dtype=np.float64)
    out[valid] = (nir[valid] - red[valid]) / denom[valid]
    return out, valid


def scl_is_valid(scl: np.ndarray) -> np.ndarray:
    data = np.asarray(scl)
    invalid = np.isin(data, list(SCL_INVALID))
    return ~invalid & np.isfinite(data.astype(np.float64))


def compose_blocked(
    tile_red: list[np.ndarray],
    tile_nir: list[np.ndarray],
    tile_scl: list[np.ndarray],
    aoi: np.ndarray,
    *,
    block: int = 256,
) -> dict[str, Any]:
    """Percorre a grade em janelas e aplica a regra da primeira tile válida."""

    if block < 1:
        raise ValueError("bloco inválido")
    rows, cols = aoi.shape
    valid = np.zeros((len(tile_red), rows, cols), dtype=bool)
    values = np.full((len(tile_red), rows, cols), np.nan, dtype=np.float64)
    bands = zip(tile_red, tile_nir, tile_scl, strict=True)
    for index, (red, nir, scl) in enumerate(bands):
        aligned = red.shape == (rows, cols) and nir.shape == red.shape
        if not aligned or scl.shape != red.shape:
            raise ValueError("bandas desalinhadas")
        for row0 in range(0, rows, block):
            for col0 in range(0, cols, block):
                row1 = min(rows, row0 + block)
                col1 = min(cols, col0 + block)
                window_red = red[row0:row1, col0:col1]
                window_nir = nir[row0:row1, col0:col1]
                ndvi, spectral = ndvi_pair(window_red, window_nir)
                usable = spectral & scl_is_valid(scl[row0:row1, col0:col1])
                valid[index, row0:row1, col0:col1] = usable
                values[index, row0:row1, col0:col1] = ndvi
    return compose_first_valid(valid, values, aoi)
