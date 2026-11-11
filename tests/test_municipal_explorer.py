"""Testes da malha municipal e explorador territorial (MVP 09)."""

from __future__ import annotations

from pathlib import Path

import pytest
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal.municipal_explorer import (
    POLO_CITIES,
    compare_municipalities,
    get_municipality,
    list_municipalities,
    load_municipality_layer,
    municipality_map_html,
    polo_city_records,
    search_municipalities,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mun_bundle():
    bundle = load_municipality_layer(REPO)
    if not bundle.available:
        pytest.skip(bundle.missing_reason_pt or "artefato municipal ausente")
    return bundle


def test_municipality_layer_count_codes_sha(mun_bundle) -> None:
    assert mun_bundle.validated_for_map is True
    assert mun_bundle.feature_count == EXPECTED_PR_MUNICIPALITY_COUNT
    assert mun_bundle.content_sha256_ok is True
    codes = mun_bundle.gdf["CD_MUN"].astype(str)
    assert codes.nunique() == EXPECTED_PR_MUNICIPALITY_COUNT
    assert mun_bundle.gdf.crs is not None
    assert str(mun_bundle.gdf.crs.to_epsg()) == "4674"
    assert "AREA_KM2" in mun_bundle.gdf.columns
    assert float(mun_bundle.gdf["AREA_KM2"].min()) > 0


def test_polo_cities_resolve(mun_bundle) -> None:
    assert len(POLO_CITIES) == 20
    resolved = polo_city_records(mun_bundle)
    assert len(resolved) == 20
    names = {r.name for r in resolved}
    assert "Maringá" in names
    assert "Curitiba" in names
    assert "Londrina" in names


def test_search_and_get(mun_bundle) -> None:
    hits = search_municipalities(mun_bundle, "maringa", limit=5)
    assert hits
    assert any(h.code == "4115200" for h in hits)
    rec = get_municipality(mun_bundle, "4115200")
    assert rec is not None
    assert rec.name == "Maringá"


def test_compare_two_cities_no_invented_indicators(mun_bundle) -> None:
    cmp = compare_municipalities(mun_bundle, "4115200", "4106902")
    assert cmp["ok"] is True
    assert set(cmp["a"]) == {"code", "name", "area_km2", "uf"}
    assert set(cmp["b"]) == {"code", "name", "area_km2", "uf"}
    forbidden_keys = {
        "pib",
        "populacao",
        "population",
        "irradiacao",
        "aptidao",
        "ranking",
    }
    assert forbidden_keys.isdisjoint(set(cmp) | set(cmp["a"]) | set(cmp["b"]))
    assert "disclaimer_pt" in cmp


def test_list_municipalities_complete(mun_bundle) -> None:
    rows = list_municipalities(mun_bundle)
    assert len(rows) == EXPECTED_PR_MUNICIPALITY_COUNT
    codes = [r.code for r in rows]
    assert len(set(codes)) == EXPECTED_PR_MUNICIPALITY_COUNT


def test_map_html_smoke(mun_bundle) -> None:
    pytest.importorskip("folium")
    html = municipality_map_html(mun_bundle, selected_code="4115200")
    assert "Maringá" in html or "4115200" in html
    assert "folium" in html.casefold() or "leaflet" in html.casefold()
