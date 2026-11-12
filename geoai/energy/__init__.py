"""Domínio energia — agregações SIGA/ANEEL (capacidade ≠ geração MWh)."""

from geoai.energy.siga_aggregate import (
    PHASE_OPERACAO,
    aggregate_plants_by_municipality,
    load_energy_panel_bundle,
)
from geoai.energy.siga_normalize import (
    NormalizedPlant,
    normalize_siga_rows,
    parse_br_decimal,
    parse_coord_pair,
)

__all__ = [
    "PHASE_OPERACAO",
    "NormalizedPlant",
    "aggregate_plants_by_municipality",
    "load_energy_panel_bundle",
    "normalize_siga_rows",
    "parse_br_decimal",
    "parse_coord_pair",
]
