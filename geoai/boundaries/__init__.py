"""Validação e preparação de limites territoriais."""

from __future__ import annotations

from geoai.boundaries.parana import prepare_parana_boundary
from geoai.boundaries.validate import (
    BoundaryValidationError,
    GeometryValidationReport,
    assert_exportable,
    validate_polygon_layer,
)

__all__ = [
    "BoundaryValidationError",
    "GeometryValidationReport",
    "assert_exportable",
    "prepare_parana_boundary",
    "validate_polygon_layer",
]
