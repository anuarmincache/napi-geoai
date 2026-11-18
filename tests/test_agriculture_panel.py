"""Inventário agrícola: só o que existe no repositório."""

from __future__ import annotations

from pathlib import Path

from geoai.portal.agriculture_panel import agriculture_source_inventory

REPO = Path(__file__).resolve().parents[1]


def test_agriculture_inventory_keeps_statistics_closed() -> None:
    rows = {item.theme_pt: item for item in agriculture_source_inventory(REPO)}
    assert set(rows) == {
        "Limites municipais",
        "Produção Agrícola Municipal",
        "Pecuária municipal",
        "Séries agrícolas",
        "Indicadores agropecuários do Paraná",
        "Uso agrícola do solo",
    }
    mesh = rows["Limites municipais"]
    assert mesh.catalogued is True
    assert mesh.local_file is True
    assert mesh.validated is True
    assert mesh.integrated is True
    assert mesh.supports_agricultural_indicator is False

    pam = rows["Produção Agrícola Municipal"]
    assert pam.organization == "IBGE/SIDRA — PAM"
    assert pam.catalogued is False
    assert pam.local_file is False
    assert pam.validated is False

    for theme in (
        "Pecuária municipal",
        "Séries agrícolas",
        "Indicadores agropecuários do Paraná",
    ):
        item = rows[theme]
        assert item.catalogued is False
        assert item.local_file is False
        assert item.source_id is None
        assert item.supports_agricultural_indicator is False

    land = rows["Uso agrícola do solo"]
    assert land.source_id == "mapbiomas.brazil.lulc"
    assert land.catalogued is True
    assert land.local_file is False
    assert land.supports_agricultural_indicator is False


def test_no_agricultural_indicator_is_marked_ready() -> None:
    assert all(
        item.supports_agricultural_indicator is False
        for item in agriculture_source_inventory(REPO)
    )
