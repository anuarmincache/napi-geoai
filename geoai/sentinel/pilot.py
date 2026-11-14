"""Constantes do piloto Sentinel-2. Não são uma cena processada."""

from __future__ import annotations

PILOT_CD_MUN = "4119152"
PILOT_NAME = "Pinhais"
PILOT_AREA_KM2 = 61.008
PILOT_CRS = "EPSG:4674"
# BBox da geometria oficial no ZIP IBGE 2025, não do GeoJSON simplificado.
PILOT_BBOX = [-49.2034816999999, -25.471936, -49.1039079, -25.378058]

# Cobertura do footprint sobre o polígono. Não é fração de pixels válidos.
MIN_FOOTPRINT_COVERAGE = 0.999
# Aceite só depois da máscara SCL na AOI. Não é o cloud cover do item.
MIN_VALID_PIXEL_FRACTION = 0.70

STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
STAC_COLLECTION = "sentinel-2-l2a"
