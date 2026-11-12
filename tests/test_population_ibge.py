"""Testes MVP 11 — população IBGE 2026 e indicadores."""

from __future__ import annotations

from pathlib import Path

import pytest
from geoai.connectors.errors import ValidationConnectorError
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.connectors.ibge_population import EXPECTED_PR_POPULATION_UF_TOTAL
from geoai.population.indicators import (
    density_hab_km2,
    kw_per_inhabitant,
    plants_per_100k_hab,
    safe_div,
)
from geoai.population.panel import load_population_panel_bundle
from geoai.population.parse import parse_population_int
from geoai.portal.municipal_profile import (
    compare_municipal_profiles,
    profile_for_code,
)

REPO = Path(__file__).resolve().parents[1]


def test_safe_div_and_density() -> None:
    assert safe_div(100.0, 0.0) is None
    assert safe_div(None, 10.0) is None
    assert density_hab_km2(1000, 10.0) == pytest.approx(100.0)
    assert density_hab_km2(1000, 0.0) is None
    assert density_hab_km2(None, 10.0) is None


def test_kw_per_hab_unknown_and_zero() -> None:
    val, note = kw_per_inhabitant(2.0, 1000, potencia_completa=True)
    assert val == pytest.approx(2.0)  # 2000 kW / 1000 hab
    val_nd, note_nd = kw_per_inhabitant(2.0, 1000, potencia_completa=False)
    assert val_nd is None
    assert note_nd
    val0, note0 = kw_per_inhabitant(0.0, 5000, potencia_completa=True)
    assert val0 == pytest.approx(0.0)
    assert note0 is None
    assert plants_per_100k_hab(2, 100_000) == pytest.approx(2.0)
    assert plants_per_100k_hab(1, 0) is None


def test_parse_population_int() -> None:
    assert parse_population_int("11952456") == 11_952_456
    assert parse_population_int(22724) == 22724
    assert parse_population_int(-1) is None
    assert parse_population_int("abc") is None


def test_population_panel_399_and_totals() -> None:
    bundle = load_population_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip(bundle.missing_reason_pt or "painel populacional ausente")
    assert bundle.panel["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert bundle.panel["population_sum_hab"] == EXPECTED_PR_POPULATION_UF_TOTAL
    assert bundle.quality.get("codes_match_mesh") is True
    assert bundle.panel.get("population_reference_date") == "2026-07-01"
    mga = profile_for_code(bundle, "4115200")
    assert mga is not None
    assert mga["populacao_estimada_2026_hab"] > 0
    assert mga["densidade_demografica_estimada_2026_hab_km2"] is not None
    assert mga["populacao_nao_e_censo"] is True
    dens = density_hab_km2(
        mga["populacao_estimada_2026_hab"],
        mga["area_km2_ibge_2025"],
    )
    assert dens == pytest.approx(
        mga["densidade_demografica_estimada_2026_hab_km2"]
    )


def test_compare_profiles_disclaimer() -> None:
    bundle = load_population_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip("painel ausente")
    cmp = compare_municipal_profiles(bundle, "4115200", "4113700")
    assert cmp["ok"] is True
    assert "Censo" in cmp["disclaimer_pt"] or "censo" in cmp["disclaimer_pt"].lower()
    assert "MMGD" in cmp["disclaimer_pt"]
    assert cmp["deltas"]["populacao_estimada_2026_hab"] is not None


def test_assert_codes_mismatch_fails() -> None:
    from geoai.population.parse import assert_codes_match_mesh

    with pytest.raises(ValidationConnectorError):
        assert_codes_match_mesh(
            [{"CD_MUN": "4115200"}],
            {"4106902"},
        )
