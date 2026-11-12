"""População IBGE estimada + indicadores territoriais."""

from geoai.population.indicators import (
    density_hab_km2,
    kw_per_inhabitant,
    safe_div,
)
from geoai.population.panel import (
    PopulationPanelBundle,
    load_population_panel_bundle,
)
from geoai.population.parse import parse_municipality_populations

__all__ = [
    "PopulationPanelBundle",
    "density_hab_km2",
    "kw_per_inhabitant",
    "load_population_panel_bundle",
    "parse_municipality_populations",
    "safe_div",
]
