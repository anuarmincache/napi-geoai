"""Testes do serviço de apresentação MMGD (sem Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal.mmgd_panel import (
    compare_municipal_mmgd,
    list_mmgd_filter_options,
    load_mmgd_panel_bundle,
    mmgd_attribution_lines,
    mmgd_ranked,
    mmgd_scope_totals,
    project_mmgd_metrics,
)

REPO = Path(__file__).resolve().parents[1]


def test_load_mmgd_bundle_reconciled() -> None:
    bundle = load_mmgd_panel_bundle(REPO)
    assert bundle.available is True, bundle.missing_reason_pt
    assert bundle.panel["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert bundle.quality.get("reconcile_ok") is True
    assert int(bundle.panel["totals"]["n_empreendimentos"]) == int(
        bundle.quality["n_valid"]
    )
    text = json.dumps(bundle.panel, ensure_ascii=False)
    assert "NomTitularEmpreendimento" not in text
    assert "NumCPFCNPJ" not in text


def test_scope_totals_unfiltered_and_ufv() -> None:
    bundle = load_mmgd_panel_bundle(REPO)
    assert bundle.available
    all_scope = mmgd_scope_totals(bundle)
    assert all_scope["filter_ok"] is True
    assert all_scope["n_empreendimentos"] == 335_899
    assert all_scope["potencia_instalada_mw_conhecida"] == pytest.approx(
        6901.84659, rel=1e-6
    )
    assert all_scope["mw_available_in_scope"] is True

    ufv = mmgd_scope_totals(bundle, tipo="UFV")
    assert ufv["filter_ok"] is True
    assert ufv["n_empreendimentos"] == 335_781
    assert ufv["potencia_instalada_mw_conhecida"] is None
    assert ufv["mw_available_in_scope"] is False


def test_multi_filter_fail_closed() -> None:
    bundle = load_mmgd_panel_bundle(REPO)
    bad = mmgd_scope_totals(bundle, tipo="UFV", classe="Residencial")
    assert bad["filter_ok"] is False
    assert bad["n_empreendimentos"] is None


def test_compare_and_rank() -> None:
    bundle = load_mmgd_panel_bundle(REPO)
    ranked = mmgd_ranked(bundle, limit=5)
    assert len(ranked) == 5
    assert ranked[0]["display_mw"] >= ranked[1]["display_mw"]
    cmp = compare_municipal_mmgd(bundle, "4115200", "4113700")
    assert cmp["ok"] is True
    assert cmp["a"]["CD_MUN"] == "4115200"
    assert "SIGA" in cmp["disclaimer_pt"] or "MMGD" in cmp["disclaimer_pt"]


def test_project_metrics_and_options() -> None:
    bundle = load_mmgd_panel_bundle(REPO)
    row = next(
        r
        for r in bundle.panel["municipalities"]
        if r["CD_MUN"] == "4115200"
    )
    full = project_mmgd_metrics(row)
    assert full["mw_available_in_scope"] is True
    assert int(full["display_n"] or 0) > 0
    filt = project_mmgd_metrics(row, tipo="UFV")
    assert filt["mw_available_in_scope"] is False
    opts = list_mmgd_filter_options(bundle)
    assert "UFV" in opts["tipo"]
    assert "Residencial" in opts["classe"]
    lines = mmgd_attribution_lines(bundle)
    assert any("ODbL" in line for line in lines)
    assert any("11/2026" in line or "periodo" in line.lower() for line in lines)


def test_missing_artifacts_fail_closed(tmp_path: Path) -> None:
    bundle = load_mmgd_panel_bundle(tmp_path)
    assert bundle.available is False
    assert bundle.missing_reason_pt


def test_corrupt_json_fail_closed(tmp_path: Path) -> None:
    derived = tmp_path / "data" / "derived"
    derived.mkdir(parents=True)
    (derived / "mmgd_pr_panel.json").write_text("{not-json", encoding="utf-8")
    (derived / "mmgd_pr.quality.json").write_text("{}", encoding="utf-8")
    (derived / "mmgd_pr.provenance.json").write_text("{}", encoding="utf-8")
    bundle = load_mmgd_panel_bundle(tmp_path)
    assert bundle.available is False
    assert "corrompido" in (bundle.missing_reason_pt or "").lower() or (
        "ilegível" in (bundle.missing_reason_pt or "").lower()
    )


def test_pii_marker_blocks_panel(tmp_path: Path) -> None:
    derived = tmp_path / "data" / "derived"
    derived.mkdir(parents=True)
    good = load_mmgd_panel_bundle(REPO)
    assert good.available
    panel = dict(good.panel)
    # re-serializa com lista; injeta marcador PII no texto
    text = json.dumps(panel, ensure_ascii=False)
    text = text.replace(
        '"source_id"',
        '"NomTitularEmpreendimento": "X", "source_id"',
        1,
    )
    (derived / "mmgd_pr_panel.json").write_text(text, encoding="utf-8")
    (derived / "mmgd_pr.quality.json").write_text(
        json.dumps(good.quality), encoding="utf-8"
    )
    (derived / "mmgd_pr.provenance.json").write_text(
        json.dumps(good.provenance), encoding="utf-8"
    )
    blocked = load_mmgd_panel_bundle(tmp_path)
    assert blocked.available is False
    assert "pessoal" in (blocked.missing_reason_pt or "").lower()
