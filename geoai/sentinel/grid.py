"""Janela de pixel alinhada. Não abre arquivo nem rede."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

GeoTransform = tuple[float, float, float, float, float, float]


def require_north_up(geotransform: GeoTransform) -> tuple[float, float]:
    """Devolve o tamanho do pixel em X e em Y, ambos positivos."""

    pixel_x = float(geotransform[1])
    rotation_x = float(geotransform[2])
    rotation_y = float(geotransform[4])
    pixel_y = float(geotransform[5])
    if rotation_x != 0.0 or rotation_y != 0.0:
        raise ValueError("a grade tem rotação")
    if pixel_x <= 0.0 or pixel_y >= 0.0:
        raise ValueError("a grade não está orientada para norte")
    return pixel_x, -pixel_y


def grids_share_alignment(
    left: GeoTransform,
    right: GeoTransform,
    *,
    tolerance: float = 1e-6,
) -> bool:
    """As duas grades cabem na mesma origem inteira de pixel."""

    left_x, left_y = require_north_up(left)
    right_x, right_y = require_north_up(right)
    if abs(left_x - right_x) > tolerance or abs(left_y - right_y) > tolerance:
        return False
    delta_x = float(right[0]) - float(left[0])
    delta_y = float(left[3]) - float(right[3])
    return (
        abs(delta_x / left_x - round(delta_x / left_x)) <= tolerance
        and abs(delta_y / left_y - round(delta_y / left_y)) <= tolerance
    )


def snap_aoi_grid(
    bounds: tuple[float, float, float, float],
    reference: GeoTransform,
) -> dict[str, Any]:
    """Grade de saída que cobre o retângulo e herda o alinhamento de referência."""

    pixel_x, pixel_y = require_north_up(reference)
    minx, miny, maxx, maxy = bounds
    if maxx <= minx or maxy <= miny:
        raise ValueError("retângulo da AOI vazio")
    origin_x = float(reference[0])
    origin_y = float(reference[3])
    col0 = math.floor((minx - origin_x) / pixel_x)
    col1 = math.ceil((maxx - origin_x) / pixel_x)
    row0 = math.floor((origin_y - maxy) / pixel_y)
    row1 = math.ceil((origin_y - miny) / pixel_y)
    if col1 <= col0 or row1 <= row0:
        raise ValueError("a AOI não gera pixel")
    snapped = (
        origin_x + col0 * pixel_x,
        pixel_x,
        0.0,
        origin_y - row0 * pixel_y,
        0.0,
        -pixel_y,
    )
    return {
        "geotransform": snapped,
        "cols": col1 - col0,
        "rows": row1 - row0,
        "pixel_x": pixel_x,
        "pixel_y": pixel_y,
    }


def source_window_for_output(
    source: GeoTransform,
    source_cols: int,
    source_rows: int,
    output: GeoTransform,
    output_cols: int,
    output_rows: int,
) -> dict[str, int] | None:
    """Interseção inteira entre a grade de saída e o raster de origem."""

    if not grids_share_alignment(output, source):
        raise ValueError("origem fora da grade de saída")
    pixel_x, pixel_y = require_north_up(output)
    col = int(round((float(source[0]) - float(output[0])) / pixel_x))
    row = int(round((float(output[3]) - float(source[3])) / pixel_y))
    dst_x0 = max(0, col)
    dst_y0 = max(0, row)
    dst_x1 = min(output_cols, col + source_cols)
    dst_y1 = min(output_rows, row + source_rows)
    if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return None
    return {
        "src_xoff": dst_x0 - col,
        "src_yoff": dst_y0 - row,
        "xsize": dst_x1 - dst_x0,
        "ysize": dst_y1 - dst_y0,
        "dst_xoff": dst_x0,
        "dst_yoff": dst_y0,
    }


def grid_bounds(
    geotransform: GeoTransform,
    cols: int,
    rows: int,
) -> tuple[float, float, float, float]:
    pixel_x, pixel_y = require_north_up(geotransform)
    minx = float(geotransform[0])
    maxy = float(geotransform[3])
    return (minx, maxy - rows * pixel_y, minx + cols * pixel_x, maxy)


def window_covering_bounds(
    geotransform: GeoTransform,
    cols: int,
    rows: int,
    bounds: tuple[float, float, float, float],
) -> dict[str, Any] | None:
    """Recorte do raster que cobre o retângulo, em pixels inteiros."""

    pixel_x, pixel_y = require_north_up(geotransform)
    minx, miny, maxx, maxy = bounds
    origin_x = float(geotransform[0])
    origin_y = float(geotransform[3])
    col0 = math.floor((minx - origin_x) / pixel_x)
    col1 = math.ceil((maxx - origin_x) / pixel_x)
    row0 = math.floor((origin_y - maxy) / pixel_y)
    row1 = math.ceil((origin_y - miny) / pixel_y)
    col0 = max(0, col0)
    row0 = max(0, row0)
    col1 = min(cols, col1)
    row1 = min(rows, row1)
    if col1 <= col0 or row1 <= row0:
        return None
    return {
        "xoff": col0,
        "yoff": row0,
        "xsize": col1 - col0,
        "ysize": row1 - row0,
        "geotransform": (
            origin_x + col0 * pixel_x,
            pixel_x,
            0.0,
            origin_y - row0 * pixel_y,
            0.0,
            -pixel_y,
        ),
    }


def place_array(
    destination: np.ndarray,
    source: np.ndarray,
    window: dict[str, int],
) -> None:
    """Copia a janela lida para a grade de saída. Não faz média."""

    y = int(window["dst_yoff"])
    x = int(window["dst_xoff"])
    height = int(window["ysize"])
    width = int(window["xsize"])
    if source.shape != (height, width):
        raise ValueError("janela com forma diferente do recorte")
    view = destination[y : y + height, x : x + width]
    if view.shape != source.shape:
        raise ValueError("janela fora da grade de saída")
    view[:, :] = source


def nearest_sample(
    source: np.ndarray,
    source_geotransform: GeoTransform,
    output_geotransform: GeoTransform,
    output_rows: int,
    output_cols: int,
    *,
    fill: int = 0,
) -> np.ndarray:
    """Amostra o centro de cada pixel de saída no pixel de origem mais próximo."""

    src_x, src_y = require_north_up(source_geotransform)
    out_x, out_y = require_north_up(output_geotransform)
    columns = np.arange(output_cols, dtype=np.float64)
    rows = np.arange(output_rows, dtype=np.float64)
    center_x = float(output_geotransform[0]) + (columns + 0.5) * out_x
    center_y = float(output_geotransform[3]) - (rows + 0.5) * out_y
    src_col = np.floor((center_x - float(source_geotransform[0])) / src_x).astype(int)
    src_row = np.floor((float(source_geotransform[3]) - center_y) / src_y).astype(int)
    col_grid, row_grid = np.meshgrid(src_col, src_row)
    inside = (
        (row_grid >= 0)
        & (col_grid >= 0)
        & (row_grid < source.shape[0])
        & (col_grid < source.shape[1])
    )
    output = np.full((output_rows, output_cols), fill, dtype=source.dtype)
    output[inside] = source[row_grid[inside], col_grid[inside]]
    return output
