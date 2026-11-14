"""Decisão de publicação. Não grava raster."""

from __future__ import annotations

from geoai.sentinel.mosaic_rule import MIN_VALID_PIXEL_FRACTION


def publication_allowed(
    *,
    official_pixels: bool,
    valid_fraction: float | None,
    acquisition_ids: tuple[str, ...] | list[str],
) -> bool:
    """Publica só uma passagem oficial com fração válida de pelo menos 0,70."""

    if not official_pixels or valid_fraction is None:
        return False
    identities = {item for item in acquisition_ids if item}
    if len(identities) != 1:
        return False
    return float(valid_fraction) >= MIN_VALID_PIXEL_FRACTION
