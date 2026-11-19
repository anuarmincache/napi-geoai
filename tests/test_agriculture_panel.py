"""Inventário agrícola: só o que existe no repositório."""

from __future__ import annotations

from pathlib import Path

from geoai.portal.agriculture_panel import agriculture_source_inventory
from geoai.portal.agro_panel import load_agro_panel_bundle

REPO = Path(__file__).resolve().parents[1]
AGRO_READY = load_agro_panel_bundle(REPO).available


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
    # PAM e PPM só abrem quando o artefato IBGE validado existe.
    for item in (pam, rows["Pecuária municipal"]):
        assert item.catalogued is AGRO_READY
        assert item.validated is AGRO_READY
        assert item.integrated is AGRO_READY
        assert item.supports_agricultural_indicator is AGRO_READY

    for theme in (
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


def test_indicators_ready_only_with_validated_artifact(tmp_path: Path) -> None:
    # Repositório sem artefato agropecuário: nada fica marcado como pronto.
    assert all(
        item.supports_agricultural_indicator is False
        for item in agriculture_source_inventory(tmp_path)
    )
    ready = {
        item.theme_pt
        for item in agriculture_source_inventory(REPO)
        if item.supports_agricultural_indicator
    }
    expected = (
        {"Produção Agrícola Municipal", "Pecuária municipal"} if AGRO_READY else set()
    )
    assert ready == expected
