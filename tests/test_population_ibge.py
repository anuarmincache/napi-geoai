"""Testes MVP 11 — população IBGE 2026 e indicadores (positivos/negativos)."""

from __future__ import annotations

from pathlib import Path

import pytest
from geoai.connectors.errors import ValidationConnectorError
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.connectors.ibge_population import EXPECTED_PR_POPULATION_UF_TOTAL
from geoai.population.indicators import (
    STATUS_ENERGIA_INDISPONIVEL,
    STATUS_SEM_EMPREENDIMENTO,
    build_municipality_indicators,
    density_hab_km2,
    kw_per_inhabitant,
    plants_per_100k_hab,
    safe_div,
)
from geoai.population.panel import (
    EnergyCoverageError,
    build_population_energy_panel,
    load_population_panel_bundle,
)
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


def test_indicators_energia_indisponivel_no_invented_zero() -> None:
    row = build_municipality_indicators(
        cd_mun="4115200",
        nm_mun="Maringá",
        area_km2=100.0,
        population=1000,
        energy=None,
        energy_source_available=False,
        nao_associados_n=0,
    )
    assert row["status_energia_siga"] == STATUS_ENERGIA_INDISPONIVEL
    assert row["potencia_fiscalizada_conhecida_mw"] is None
    assert row["potencia_fiscalizada_conhecida_kw_por_habitante"] is None
    assert row["n_empreendimentos_siga_operacao"] is None
    assert row["usinas_por_100mil_hab"] is None
    assert row["densidade_demografica_estimada_2026_hab_km2"] == pytest.approx(10.0)
    assert row["zero_vinculado"] is False


def test_indicators_sem_empreendimento_is_zero_vinculado() -> None:
    row = build_municipality_indicators(
        cd_mun="4100103",
        nm_mun="Abatiá",
        area_km2=50.0,
        population=5000,
        energy={
            "n_empreendimentos": 0,
            "potencia_fiscalizada_mw": 0.0,
            "potencia_fiscalizada_completa": True,
            "status_dados": STATUS_SEM_EMPREENDIMENTO,
        },
        energy_source_available=True,
        nao_associados_n=34,
    )
    assert row["status_energia_siga"] == STATUS_SEM_EMPREENDIMENTO
    assert row["potencia_fiscalizada_conhecida_mw"] == pytest.approx(0.0)
    assert row["potencia_fiscalizada_conhecida_kw_por_habitante"] == pytest.approx(
        0.0
    )
    assert row["zero_vinculado"] is True
    assert "zero absoluto" in (row["kw_por_habitante_note_pt"] or "").lower() or (
        "Zero vinculado" in (row["kw_por_habitante_note_pt"] or "")
    )
    assert "34" in (row["unassociated_plants_limitation_pt"] or "")


def _mini_mesh_pop_energy(
    n: int = EXPECTED_PR_MUNICIPALITY_COUNT,
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    """Gera malha/pop/energia sintéticas com n códigos (só para testes de erro)."""

    mesh = []
    pop_by = {}
    energy_by = {}
    for i in range(n):
        code = f"41{i:05d}"
        mesh.append({"CD_MUN": code, "NM_MUN": f"M{i}", "AREA_KM2": 10.0})
        pop_by[code] = {"populacao_estimada_2026_hab": 1000 + i}
        energy_by[code] = {
            "n_empreendimentos": 0,
            "potencia_fiscalizada_mw": 0.0,
            "potencia_fiscalizada_completa": True,
            "status_dados": STATUS_SEM_EMPREENDIMENTO,
        }
    return mesh, pop_by, energy_by


def test_build_panel_siga_unavailable_keeps_pop_energy_nd() -> None:
    # Usa 399 códigos sintéticos válidos no contrato de contagem.
    mesh, pop_by, _ = _mini_mesh_pop_energy()
    panel = build_population_energy_panel(
        mesh_rows=mesh,
        population_by_code=pop_by,
        energy_by_code={},
        nao_associados_n=0,
        energy_source_available=False,
    )
    assert panel["energy_source_available"] is False
    assert all(
        m["status_energia_siga"] == STATUS_ENERGIA_INDISPONIVEL
        for m in panel["municipalities"]
    )
    assert all(
        m["potencia_fiscalizada_conhecida_mw"] is None
        for m in panel["municipalities"]
    )
    assert all(
        m["potencia_fiscalizada_conhecida_kw_por_habitante"] is None
        for m in panel["municipalities"]
    )
    assert panel["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT


def test_build_panel_siga_available_missing_code_fail_closed() -> None:
    mesh, pop_by, energy_by = _mini_mesh_pop_energy()
    missing = mesh[0]["CD_MUN"]
    del energy_by[missing]
    with pytest.raises(EnergyCoverageError):
        build_population_energy_panel(
            mesh_rows=mesh,
            population_by_code=pop_by,
            energy_by_code=energy_by,
            nao_associados_n=34,
            energy_source_available=True,
        )


def test_build_panel_rejects_fallback_dict_when_siga_off() -> None:
    mesh, pop_by, energy_by = _mini_mesh_pop_energy()
    with pytest.raises(EnergyCoverageError):
        build_population_energy_panel(
            mesh_rows=mesh,
            population_by_code=pop_by,
            energy_by_code=energy_by,
            nao_associados_n=0,
            energy_source_available=False,
        )


def test_population_panel_399_and_totals() -> None:
    bundle = load_population_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip(bundle.missing_reason_pt or "painel populacional ausente")
    assert bundle.panel["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert bundle.panel["population_sum_hab"] == EXPECTED_PR_POPULATION_UF_TOTAL
    assert bundle.quality.get("codes_match_mesh") is True
    assert bundle.panel.get("population_reference_date") == "2026-07-01"
    # Artefato versionado com SIGA disponível
    assert bundle.panel.get("energy_source_available") is True
    assert bundle.panel.get("nao_associados_siga_n") == 34
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
    sem = [
        m
        for m in bundle.panel["municipalities"]
        if m["status_energia_siga"] == STATUS_SEM_EMPREENDIMENTO
    ]
    assert sem
    assert all(m.get("zero_vinculado") is True for m in sem)
    assert all(
        m["potencia_fiscalizada_conhecida_mw"] == 0.0 for m in sem
    )
    assert all(
        "vinculado" in (m.get("kw_por_habitante_note_pt") or "").lower()
        or "associad" in (m.get("kw_por_habitante_note_pt") or "").lower()
        for m in sem
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
