"""Identidade do piloto. Área, bbox e geometria vêm da malha oficial."""

from __future__ import annotations

PILOT_CD_MUN = "4115200"
MESH_RELATIVE = "data/raw/ibge/PR_Municipios_2025.zip"
CATALOG_NAME = "sentinel_maringa_pilot.json"

# Cobertura do footprint sobre o polígono. Não é fração de pixels válidos.
MIN_FOOTPRINT_COVERAGE = 0.999
# Aceite só depois da máscara SCL na AOI. Não é o cloud cover do item.
MIN_VALID_PIXEL_FRACTION = 0.70

STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
STAC_COLLECTION_URL = (
    "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a"
)
STAC_COLLECTION = "sentinel-2-l2a"
