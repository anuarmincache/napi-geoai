"""Testes do catálogo de fontes oficiais."""

from __future__ import annotations

from pathlib import Path

import pytest
from geoai.connectors.catalog import SOURCE_CATALOG, get_source, list_sources
from geoai.connectors.contracts import AccessMode, SourceStatus


def test_catalog_contains_priority_sources() -> None:
    ids = {s.source_id for s in SOURCE_CATALOG}
    assert "ibge.malhas_municipais.pr_uf_2025" in ids
    assert "ibge.estimativas_populacao.municipios_2026" in ids
    assert "aneel.siga.empreendimentos_geracao" in ids
    assert "inpe.labren.atlas_solar_2017" in ids
    assert "mapbiomas.brazil.lulc" in ids
    assert "ons.dados_abertos.capacidade_geracao" in ids


def test_prototype_sources_have_connector_module() -> None:
    prototypes = list_sources(status=SourceStatus.PROTOTYPE)
    assert prototypes
    for spec in prototypes:
        assert spec.connector_module
        assert spec.download_url
        assert spec.license_note
        assert spec.catalogued_at
        assert spec.official_update_cadence
        assert spec.verification_policy


def test_get_source_and_access_modes() -> None:
    ibge = get_source("ibge.malhas_municipais.pr_uf_2025")
    assert ibge.access_mode == AccessMode.HTTP_FILE
    assert ibge.update_cadence == ibge.official_update_cadence
    aneel = get_source("aneel.siga.empreendimentos_geracao")
    assert aneel.access_mode == AccessMode.CKAN_RESOURCE
    assert "diária" in aneel.official_update_cadence.lower() or "mensal" in (
        aneel.official_update_cadence.lower()
    )
    mapbiomas = get_source("mapbiomas.brazil.lulc")
    assert mapbiomas.access_mode == AccessMode.GEE_ASSET
    assert mapbiomas.status == SourceStatus.CATALOGUED
    assert "redistribu" in mapbiomas.license_note.lower() or "citar" in (
        mapbiomas.license_note.lower()
    )
    inpe = get_source("inpe.labren.atlas_solar_2017")
    assert "autorização" in inpe.license_note.lower()


def test_unknown_source_raises() -> None:
    with pytest.raises(KeyError, match="desconhecida"):
        get_source("nao.existe")


def test_fonte_em_uso_nao_aparece_como_apenas_catalogada() -> None:
    """Toda fonte que alimenta um artefato precisa constar como coletada.

    A planilha do MapBiomas sustenta a aba de cobertura desde 19/11/2026 e o
    catálogo a mostrava como «catalogada, sem coleta», porque a única entrada
    MapBiomas descrevia a via de raster no Earth Engine, que de fato nunca foi
    baixada. Rótulo errado em uma página chamada «Fontes e qualidade» custa
    mais que a informação que ela dá.
    """
    por_organizacao: dict[str, list] = {}
    for fonte in list_sources():
        por_organizacao.setdefault(fonte.organization, []).append(fonte)

    repo = Path(__file__).resolve().parents[1]
    artefatos = {
        "IBGE": "ibge_pr_population_2026_panel.json",
        "ANEEL": "siga_pr_energy_panel.json",
        "MapBiomas": "mapbiomas_pr_landcover_panel.json",
    }
    for organizacao, artefato in artefatos.items():
        if not (repo / "data" / "derived" / artefato).exists():
            continue
        fontes = por_organizacao.get(organizacao, [])
        assert fontes, f"{organizacao} alimenta {artefato} e sumiu do catálogo"
        assert any(f.status is not SourceStatus.CATALOGUED for f in fontes), (
            f"{organizacao} alimenta {artefato}, então ao menos uma entrada "
            "precisa sair de «catalogada, sem coleta»"
        )
