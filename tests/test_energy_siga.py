"""Testes do painel energético SIGA (MVP 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.connectors.aneel import parse_siga_file
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_aggregate import PHASE_OPERACAO, load_energy_panel_bundle
from geoai.energy.siga_normalize import (
    normalize_siga_rows,
    parse_br_decimal,
    parse_coord_pair,
)
from geoai.portal.energy_panel import (
    compare_municipal_energy,
    municipalities_ranked,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "aneel_siga_mini.csv"


def test_parse_br_decimal_and_coords() -> None:
    assert parse_br_decimal("10000,00") == 10000.0
    assert parse_br_decimal("74,82") == pytest.approx(74.82)
    assert parse_br_decimal(float("inf")) is None
    pair = parse_coord_pair("-23,74974679", "-50,90792543")
    assert pair is not None
    assert pair[0] == pytest.approx(-50.90792543)
    assert parse_coord_pair("0", "0") is None
    assert parse_coord_pair("91", "-50") is None


def test_normalize_fixture_pr_plants() -> None:
    rows = parse_siga_file(FIXTURE, uf="PR")
    accepted, rejected = normalize_siga_rows(rows, uf="PR")
    assert rejected == []
    assert len(accepted) == 5
    assert all(p.phase == "Operação" for p in accepted)
    assert all(p.coord_ok for p in accepted)
    assert accepted[0].potencia_fiscalizada_kw == 10000.0


def test_energy_panel_covers_399_and_reconciles() -> None:
    bundle = load_energy_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip(bundle.missing_reason_pt or "painel ausente")
    assert bundle.panel["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert bundle.panel["phase_filter"] == PHASE_OPERACAO
    totals = bundle.panel["totals"]
    assert (
        totals["n_empreendimentos_municipios"]
        + totals["n_empreendimentos_nao_associados"]
        == totals["n_empreendimentos_fase"]
    )
    assert totals["n_empreendimentos_fase"] == 310
    sem = [
        m
        for m in bundle.panel["municipalities"]
        if m["status_dados"] == "sem_empreendimento"
    ]
    assert sem
    assert all(m["n_empreendimentos"] == 0 for m in sem)
    assert all(m.get("zero_semantics") for m in sem)
    ranked = municipalities_ranked(bundle, limit=5)
    assert ranked
    assert (
        ranked[0]["potencia_fiscalizada_mw"]
        >= ranked[-1]["potencia_fiscalizada_mw"]
    )


def test_compare_energy_disclaimer() -> None:
    bundle = load_energy_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip("painel ausente")
    ranked = municipalities_ranked(bundle, limit=2)
    if len(ranked) < 2:
        pytest.skip("poucos municípios com usinas")
    cmp = compare_municipal_energy(
        bundle, ranked[0]["CD_MUN"], ranked[1]["CD_MUN"]
    )
    assert cmp["ok"] is True
    assert "MWh" in cmp["disclaimer_pt"]
    assert "MMGD" in cmp["disclaimer_pt"]


def test_qgis_join_report_contract() -> None:
    path = REPO / "data" / "derived" / "siga_pr_qgis_join_report.json"
    if not path.is_file():
        pytest.skip("relatório QGIS ausente")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert "native:joinattributesbylocation" in str(
        report.get("engine", {}).get("algorithms")
    )
    assert report["results"]["matched"] == 276
    assert report["engine"].get("qgis_version")
    assert report["engine"].get("gdal_version")
    assert report.get("not_mmgd") is True
