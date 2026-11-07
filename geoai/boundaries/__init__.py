"""Validação e preparação de limites territoriais."""

from __future__ import annotations

from geoai.boundaries.parana import prepare_parana_boundary
from geoai.boundaries.validate import GeometryValidationReport, validate_polygon_layer

__all__ = [
    "GeometryValidationReport",
    "prepare_parana_boundary",
    "validate_polygon_layer",
]
