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


def describe_future_gdal_windows() -> dict[str, str]:
    """Contrato da etapa seguinte. Não abre dataset, rede nem COG."""

    return {
        "compose_blocked_memory": "full_arrays",
        "future_read": "ReadAsArray(xoff, yoff, xsize, ysize)",
        "future_write": "WriteArray(array, xoff, yoff)",
        "download": "not_executed",
        "ndvi_published": "false",
    }


def compose_blocked(
    tile_red: list[np.ndarray],
    tile_nir: list[np.ndarray],
    tile_scl: list[np.ndarray],
    aoi: np.ndarray,
    *,
    block: int = 256,
) -> dict[str, Any]:
    """Aplica a regra por janela sobre arrays já inteiros na memória.

    `valid` e `values` têm o tamanho da grade. O laço só recorta essas
    matrizes. A leitura e a escrita reais do GDAL, por `ReadAsArray` e
    `WriteArray`, ainda não rodam aqui.
    """

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


def iter_blocks(rows: int, cols: int, block: int) -> list[tuple[int, int, int, int]]:
    """Fatias (linha0, linha1, coluna0, coluna1). Não aloca a grade."""

    if block < 1:
        raise ValueError("bloco inválido")
    pieces: list[tuple[int, int, int, int]] = []
    for row0 in range(0, rows, block):
        for col0 in range(0, cols, block):
            pieces.append(
                (row0, min(rows, row0 + block), col0, min(cols, col0 + block))
            )
    return pieces


def measure_blocks(
    reader: Any,
    rows: int,
    cols: int,
    *,
    block: int = 256,
    writer: Any | None = None,
) -> dict[str, Any]:
    """Soma a fração por bloco e descarta o NDVI de cada janela.

    `reader` devolve as bandas só daquele bloco. O resultado não contém a grade.
    """

    from geoai.sentinel.mosaic_rule import MIN_VALID_PIXEL_FRACTION, RULE

    n_aoi = 0
    n_valid = 0
    overlap = 0
    pixels: list[int] | None = None
    for row0, row1, col0, col1 in iter_blocks(rows, cols, block):
        reds, nirs, scls, aoi = reader(row0, row1, col0, col1)
        expected = (row1 - row0, col1 - col0)
        if aoi.shape != expected:
            raise ValueError("bloco maior que a janela pedida")
        for band in (*reds, *nirs, *scls):
            if band.shape != expected:
                raise ValueError("banda maior que o bloco")
        composed = compose_blocked(list(reds), list(nirs), list(scls), aoi, block=block)
        if pixels is None:
            pixels = [0 for _ in composed["pixels_per_tile"]]
        if len(pixels) != len(composed["pixels_per_tile"]):
            raise ValueError("número de tiles mudou entre blocos")
        n_aoi += int(composed["n_aoi"])
        n_valid += int(composed["n_valid"])
        overlap += int(composed["overlap_both_valid"])
        for index, count in enumerate(composed["pixels_per_tile"]):
            pixels[index] += int(count)
        if writer is not None:
            writer(row0, col0, composed["ndvi"], composed["provenance"])
        del composed
    fraction = None if n_aoi == 0 else n_valid / n_aoi
    approved = fraction is not None and fraction >= MIN_VALID_PIXEL_FRACTION
    return {
        "n_aoi": n_aoi,
        "n_valid": n_valid,
        "valid_fraction": fraction,
        "pixels_per_tile": pixels or [],
        "overlap_both_valid": overlap,
        "quality_approved": approved,
        "rule": RULE,
        "retained_grid": False,
    }
