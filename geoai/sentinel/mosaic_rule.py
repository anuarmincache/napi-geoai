"""Composição de duas tiles sem média e sem contar o mesmo pixel duas vezes."""

from __future__ import annotations

from typing import Any

import numpy as np

RULE = "first_valid_tile_in_declared_order"
MIN_VALID_PIXEL_FRACTION = 0.70


def compose_first_valid(
    valid: np.ndarray,
    values: np.ndarray,
    aoi: np.ndarray,
) -> dict[str, Any]:
    """A primeira tile válida na ordem declarada fica com o pixel.

    `valid` e `values` têm forma (tiles, linhas, colunas). A máscara `aoi`
    restringe o denominador ao município. Sobreposição com dois valores
    válidos conta um pixel e guarda a origem.
    """

    if valid.shape != values.shape or valid.ndim != 3:
        raise ValueError("grades de tiles incompatíveis")
    n_tiles, rows, cols = valid.shape
    if aoi.shape != (rows, cols):
        raise ValueError("máscara da AOI incompatível com a grade")
    if n_tiles < 1:
        raise ValueError("nenhuma tile")
    provenance = np.zeros((rows, cols), dtype=np.uint8)
    output = np.full((rows, cols), np.nan, dtype=np.float64)
    usable = np.asarray(valid, dtype=bool)
    for index in range(n_tiles):
        take = usable[index] & aoi & (provenance == 0)
        output[take] = values[index][take]
        provenance[take] = np.uint8(index + 1)
    per_tile = [
        int(((provenance == index + 1) & aoi).sum()) for index in range(n_tiles)
    ]
    n_aoi = int(np.asarray(aoi, dtype=bool).sum())
    n_valid = int(sum(per_tile))
    if n_tiles >= 2:
        overlap_both = int((usable[0] & usable[1] & aoi).sum())
    else:
        overlap_both = 0
    fraction = None if n_aoi == 0 else n_valid / n_aoi
    approved = fraction is not None and fraction >= MIN_VALID_PIXEL_FRACTION
    return {
        "ndvi": output,
        "provenance": provenance,
        "n_aoi": n_aoi,
        "n_valid": n_valid,
        "valid_fraction": fraction,
        "pixels_per_tile": per_tile,
        "overlap_both_valid": overlap_both,
        "quality_approved": approved,
        "rule": RULE,
    }
