"""Visualizador local do NDVI. Não publica e não recalcula o raster."""

from geoai.viewer.policy import local_downloads_enabled, public_downloads_enabled
from geoai.viewer.session import load_index, scientific_panel

__all__ = [
    "load_index",
    "local_downloads_enabled",
    "public_downloads_enabled",
    "scientific_panel",
]
