"""Inventário ambiental: só o que existe no repositório."""

from __future__ import annotations

from pathlib import Path

from geoai.portal.environment_panel import environment_source_inventory

REPO = Path(__file__).resolve().parents[1]


def test_environment_inventory_separates_catalog_from_files() -> None:
    rows = {item.theme_pt: item for item in environment_source_inventory(REPO)}
    assert set(rows) == {
        "Limites municipais",
        "Uso e cobertura da terra",
        "Unidades de conservação",
        "Recursos hídricos",
    }
    mesh = rows["Limites municipais"]
    assert mesh.catalogued is True
    assert mesh.local_file is True
    assert mesh.validated is True
    assert mesh.integrated is True
    assert mesh.supports_environmental_indicator is False

    land = rows["Uso e cobertura da terra"]
    assert land.source_id == "mapbiomas.brazil.lulc"
    assert land.catalogued is True
    assert land.local_file is False
    assert land.validated is False

    for theme in ("Unidades de conservação", "Recursos hídricos"):
        item = rows[theme]
        assert item.catalogued is False
        assert item.local_file is False
        assert item.validated is False
        assert item.integrated is False
        assert item.supports_environmental_indicator is False


def test_no_environmental_indicator_is_marked_ready() -> None:
    assert all(
        item.supports_environmental_indicator is False
        for item in environment_source_inventory(REPO)
    )
