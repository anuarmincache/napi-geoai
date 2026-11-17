"""Catálogo local de mapas. Não publica arquivos e não agenda atualizações."""

from geoai.catalog.entry import (
    build_catalog_entry,
    download_menu,
    file_states,
    frontend_view,
    parse_acquisition,
)
from geoai.catalog.integrity import verify_integrity
from geoai.catalog.maringa import build_maringa_pilot
from geoai.catalog.style import ndvi_style
from geoai.catalog.updates import attempt_is_due, decide_update, scene_tile_plan

__all__ = [
    "attempt_is_due",
    "build_catalog_entry",
    "build_maringa_pilot",
    "decide_update",
    "download_menu",
    "file_states",
    "frontend_view",
    "ndvi_style",
    "parse_acquisition",
    "scene_tile_plan",
    "verify_integrity",
]
