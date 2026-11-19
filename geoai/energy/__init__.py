"""Domínio energia — SIGA e MMGD separados (capacidade ≠ geração MWh)."""

from geoai.energy.mmgd_aggregate import aggregate_mmgd_by_municipality
from geoai.energy.mmgd_normalize import (
    NormalizedMmgdPlant,
    normalize_mmgd_row,
)
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
    "NormalizedMmgdPlant",
    "NormalizedPlant",
    "aggregate_mmgd_by_municipality",
    "aggregate_plants_by_municipality",
    "load_energy_panel_bundle",
    "normalize_mmgd_row",
    "normalize_siga_rows",
    "parse_br_decimal",
    "parse_coord_pair",
]
