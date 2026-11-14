"""DN Sentinel-2 L2A para reflectância, só com escala e offset informados."""

from __future__ import annotations

import math


class ReflectanceMetadataError(ValueError):
    """Escala, offset ou nodata ausentes. Não se assume DN/10000."""


def reflectance_dn(
    dn: float | int | None,
    *,
    scale: float | None,
    offset: float | None,
    nodata: float | int | None,
) -> float | None:
    """reflectância = DN * scale + offset, exceto nodata.

    DN de nodata não recebe offset. Sem scale ou offset o cálculo para.
    """

    if scale is None or offset is None:
        raise ReflectanceMetadataError("scale e offset são obrigatórios")
    if not math.isfinite(scale) or not math.isfinite(offset):
        raise ReflectanceMetadataError("scale ou offset não finito")
    if dn is None:
        return None
    if isinstance(dn, bool) or not isinstance(dn, (int, float)):
        raise ReflectanceMetadataError("DN inválido")
    if nodata is not None and dn == nodata:
        return None
    if not math.isfinite(dn):
        return None
    value = float(dn) * float(scale) + float(offset)
    if not math.isfinite(value):
        return None
    return value
