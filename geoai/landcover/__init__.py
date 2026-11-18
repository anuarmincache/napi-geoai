"""Cobertura do solo. Sem indicador enquanto o arquivo oficial não for validado."""

from geoai.landcover.mapbiomas_col11 import (
    CLASS_NAME,
    COLLECTION,
    CONTENT_SHA256,
    DISPLAY_GROUPS,
    LOCAL_FILE,
    YEAR_MAX,
    YEAR_MIN,
    CoverageRecord,
    MapBiomasContractError,
    composition_percent,
    validate_fixture_records,
    validate_parana_records,
)

__all__ = [
    "CLASS_NAME",
    "COLLECTION",
    "CONTENT_SHA256",
    "DISPLAY_GROUPS",
    "LOCAL_FILE",
    "YEAR_MAX",
    "YEAR_MIN",
    "CoverageRecord",
    "MapBiomasContractError",
    "composition_percent",
    "validate_fixture_records",
    "validate_parana_records",
]
