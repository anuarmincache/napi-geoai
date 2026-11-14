"""NDVI em janela e reamostragem categórica (sem download Sentinel)."""

from __future__ import annotations

import math
from typing import Any

# Limiar numérico do denominador: evita divisão por ~0 em reflectância.
NDVI_DENOM_EPS = 1e-6

# SCL Sentinel-2 L2A consideradas inválidas para NDVI publicado
# (nuvem, sombra, defeito, saturado, sem dado). Não é máscara operacional
# até uma cena real ser validada.
SCL_INVALID = frozenset({0, 1, 3, 8, 9, 10, 11})


def resample_nearest(
    values: list[list[int | None]],
    out_rows: int,
    out_cols: int,
) -> list[list[int | None]]:
    """Reamostra grade categórica por vizinho mais próximo (não bilinear)."""

    if out_rows <= 0 or out_cols <= 0:
        raise ValueError("grade de saída inválida")
    src_rows = len(values)
    src_cols = len(values[0]) if src_rows else 0
    if src_rows == 0 or src_cols == 0:
        raise ValueError("grade SCL vazia")
    out: list[list[int | None]] = []
    for r in range(out_rows):
        src_r = min(src_rows - 1, int((r + 0.5) * src_rows / out_rows))
        row: list[int | None] = []
        for c in range(out_cols):
            src_c = min(src_cols - 1, int((c + 0.5) * src_cols / out_cols))
            row.append(values[src_r][src_c])
        out.append(row)
    return out


def ndvi_window(
    b04: list[list[float | None]],
    b08: list[list[float | None]],
    *,
    valid: list[list[bool]] | None = None,
    denom_eps: float = NDVI_DENOM_EPS,
) -> list[list[float | None]]:
    """NDVI = (B08-B04)/(B08+B04) só onde a máscara e o denominador são válidos.

    Não clampa resultados. Pixel inválido permanece None (n/d, não zero).
    As bandas devem já estar em reflectância compatível; este módulo não
    assume DN/10000.
    """

    rows = len(b04)
    if rows == 0 or len(b08) != rows:
        raise ValueError("bandas B04/B08 com forma incompatível")
    cols = len(b04[0])
    out: list[list[float | None]] = []
    for r in range(rows):
        if len(b04[r]) != cols or len(b08[r]) != cols:
            raise ValueError("janela não retangular")
        line: list[float | None] = []
        for c in range(cols):
            if valid is not None and not valid[r][c]:
                line.append(None)
                continue
            red = b04[r][c]
            nir = b08[r][c]
            if red is None or nir is None:
                line.append(None)
                continue
            if not (math.isfinite(red) and math.isfinite(nir)):
                line.append(None)
                continue
            denom = nir + red
            if not math.isfinite(denom) or abs(denom) <= denom_eps:
                line.append(None)
                continue
            line.append((nir - red) / denom)
        out.append(line)
    return out


def valid_mask_from_scl(scl: list[list[int | None]]) -> list[list[bool]]:
    mask: list[list[bool]] = []
    for row in scl:
        mask.append([cell is not None and int(cell) not in SCL_INVALID for cell in row])
    return mask


def ndvi_summary(grid: list[list[float | None]]) -> dict[str, Any]:
    values = [v for row in grid for v in row if v is not None and math.isfinite(v)]
    total = sum(len(row) for row in grid)
    return {
        "n_pixels": total,
        "n_valid": len(values),
        "fraction_valid": (len(values) / total) if total else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "ndvi_is_spectral_index": True,
        "not_biogas_or_yield": True,
    }


SENTINEL_SEARCH_POLICY = {
    "product_level": "L2A",
    "preferred_search_days": 7,
    "fallback_search_days": 30,
    "bands": ["B04", "B08"],
    "scl_resampling": "nearest",
    "guarantee": (
        "Janelas de 7 e 30 dias são busca, não garantia de cena sem nuvens."
    ),
    "download_in_this_release": False,
}
