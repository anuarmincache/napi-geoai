"""Leitura do catálogo estático do piloto. A UI não busca cenas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.sentinel.pilot import CATALOG_NAME


def catalog_path(repo_root: Path) -> Path:
    return repo_root / "data" / "derived" / CATALOG_NAME


def load_pilot_catalog(repo_root: Path) -> dict[str, Any]:
    path = catalog_path(repo_root)
    if not path.is_file():
        return {
            "status": "unavailable",
            "ndvi_published": False,
            "public_message_pt": (
                "Catálogo do piloto Sentinel-2 ausente. "
                "Nenhum NDVI foi publicado."
            ),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "ndvi_published": False,
            "public_message_pt": "Catálogo do piloto ilegível.",
        }
    payload["ndvi_published"] = payload.get("ndvi_published") is True
    return payload


def show_ndvi(catalog: dict[str, Any]) -> bool:
    return catalog.get("ndvi_published") is True and catalog.get("status") == "ready"
