"""Testes do catálogo de fontes oficiais."""

from __future__ import annotations

import pytest
from geoai.connectors.catalog import SOURCE_CATALOG, get_source, list_sources
from geoai.connectors.contracts import AccessMode, SourceStatus


def test_catalog_contains_priority_sources() -> None:
    ids = {s.source_id for s in SOURCE_CATALOG}
    assert "ibge.malhas_municipais.pr_uf_2025" in ids
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


def test_get_source_and_access_modes() -> None:
    ibge = get_source("ibge.malhas_municipais.pr_uf_2025")
    assert ibge.access_mode == AccessMode.HTTP_FILE
    aneel = get_source("aneel.siga.empreendimentos_geracao")
    assert aneel.access_mode == AccessMode.CKAN_RESOURCE
    mapbiomas = get_source("mapbiomas.brazil.lulc")
    assert mapbiomas.access_mode == AccessMode.GEE_ASSET
    assert mapbiomas.status == SourceStatus.CATALOGUED


def test_unknown_source_raises() -> None:
    with pytest.raises(KeyError, match="desconhecida"):
        get_source("nao.existe")
