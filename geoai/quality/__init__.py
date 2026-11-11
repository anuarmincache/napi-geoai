"""Qualidade de dados e schemas de dataset (MVP 06)."""

from geoai.quality.contracts import (
    CANONICAL_ENERGY_UNITS,
    DatasetSchema,
    EnergyQuantityKind,
    FieldConstraint,
    GeometryKind,
    QualityFinding,
    QualityReport,
    QualityStatus,
)
from geoai.quality.schemas import territorial_pr_uf_schema
from geoai.quality.validate import (
    assert_energy_field_unit_coherent,
    assert_energy_quantities_separated,
    is_sha256_hex,
    validate_field_value,
    validate_record,
    validate_tabular_record,
    verify_content_sha256,
)

__all__ = [
    "CANONICAL_ENERGY_UNITS",
    "DatasetSchema",
    "EnergyQuantityKind",
    "FieldConstraint",
    "GeometryKind",
    "QualityFinding",
    "QualityReport",
    "QualityStatus",
    "assert_energy_field_unit_coherent",
    "assert_energy_quantities_separated",
    "is_sha256_hex",
    "territorial_pr_uf_schema",
    "validate_field_value",
    "validate_record",
    "validate_tabular_record",
    "verify_content_sha256",
]
