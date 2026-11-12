"""Testes do painel energético SIGA (MVP 10) — positivos e negativos."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from geoai.connectors.aneel import parse_siga_file
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_aggregate import (
    PHASE_OPERACAO,
    ZERO_SEMANTICS_LIMITED,
    _kw_to_mw,
    aggregate_plants_by_municipality,
    load_energy_panel_bundle,
)
from geoai.energy.siga_normalize import (
    normalize_siga_rows,
    parse_br_decimal,
    parse_coord_pair,
)
from geoai.energy.siga_reconcile import (
    SpatialReconciliationError,
    assignments_from_qgis_report,
    reconcile_spatial_assignments,
)
from geoai.portal.energy_panel import (
    compare_municipal_energy,
    energy_scope_totals,
    municipalities_ranked,
    project_municipality_metrics,
)
from shapely.geometry import Point

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


def test_kw_to_mw_unknown_is_none_not_zero() -> None:
    assert _kw_to_mw(None) is None
    assert _kw_to_mw(1000.0) == pytest.approx(1.0)


def test_normalize_rejects_negative_capacity() -> None:
    rows = [
        {
            "CodCEG": "NEG1",
            "SigUFPrincipal": "PR",
            "NomEmpreendimento": "x",
            "DscFaseUsina": "Operação",
            "SigTipoGeracao": "UFV",
            "DscOrigemCombustivel": "Solar",
            "DscMuninicpios": "Teste",
            "DatGeracaoConjuntoDados": "2026-01-01",
            "MdaPotenciaOutorgadaKw": "10,00",
            "MdaPotenciaFiscalizadaKw": "-1,00",
            "NumCoordNEmpreendimento": "-23,5",
            "NumCoordEEmpreendimento": "-51,5",
        }
    ]
    accepted, rejected = normalize_siga_rows(rows, uf="PR")
    assert accepted == []
    assert len(rejected) == 1
    assert "negativa" in (rejected[0].reject_reason or "")


def test_normalize_fixture_pr_plants() -> None:
    rows = parse_siga_file(FIXTURE, uf="PR")
    accepted, rejected = normalize_siga_rows(rows, uf="PR")
    assert rejected == []
    assert len(accepted) == 5
    assert all(p.phase == "Operação" for p in accepted)
    assert all(p.coord_ok for p in accepted)
    assert accepted[0].potencia_fiscalizada_kw == 10000.0


def test_aggregate_unknown_capacity_not_counted_as_zero() -> None:
    gdf = gpd.GeoDataFrame(
        [
            {
                "CodCEG": "A",
                "NomEmpreendimento": "com",
                "DscFaseUsina": PHASE_OPERACAO,
                "SigTipoGeracao": "UFV",
                "potencia_fiscalizada_kw": 2000.0,
                "potencia_outorgada_kw": 2000.0,
                "CD_MUN": "4115200",
                "match_status": "matched",
                "municipios_declarados": "",
            },
            {
                "CodCEG": "B",
                "NomEmpreendimento": "sem",
                "DscFaseUsina": PHASE_OPERACAO,
                "SigTipoGeracao": "UFV",
                "potencia_fiscalizada_kw": None,
                "potencia_outorgada_kw": 1000.0,
                "CD_MUN": "4115200",
                "match_status": "matched",
                "municipios_declarados": "",
            },
        ],
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4674",
    )
    catalog = [
        {"CD_MUN": "4115200", "NM_MUN": "Maringá"},
        {"CD_MUN": "4106902", "NM_MUN": "Curitiba"},
    ]
    panel = aggregate_plants_by_municipality(gdf, catalog, phase=PHASE_OPERACAO)
    mga = next(m for m in panel["municipalities"] if m["CD_MUN"] == "4115200")
    assert mga["n_empreendimentos"] == 2
    assert mga["potencia_fiscalizada_mw"] == pytest.approx(2.0)
    assert mga["n_potencia_fiscalizada_ausente"] == 1
    assert mga["potencia_fiscalizada_completa"] is False
    assert panel["totals"]["soma_cobertura"] == "parcial"
    assert panel["totals_caveat_pt"]
    cwb = next(m for m in panel["municipalities"] if m["CD_MUN"] == "4106902")
    assert cwb["status_dados"] == "sem_empreendimento"
    assert "zero_real" not in (cwb.get("zero_semantics") or "")
    assert "georreferenciada" in (cwb.get("zero_semantics") or "")


def test_reconcile_fail_closed_on_cd_mun_divergence() -> None:
    qgis = {"CEG1": "4115200", "CEG2": None}
    gpd_map = {"CEG1": "4106902", "CEG2": None}
    with pytest.raises(SpatialReconciliationError):
        reconcile_spatial_assignments(
            qgis_assignments=qgis,
            geopandas_assignments=gpd_map,
            qgis_input={
                "siga_sha256": "abc",
                "municipios_sha256": "def",
            },
            provenance={
                "content_sha256": "abc",
                "municipios_zip_sha256": "def",
            },
            phase=PHASE_OPERACAO,
        )


def test_reconcile_fail_closed_on_hash_mismatch() -> None:
    with pytest.raises(SpatialReconciliationError):
        reconcile_spatial_assignments(
            qgis_assignments={"CEG1": "4115200"},
            geopandas_assignments={"CEG1": "4115200"},
            qgis_input={
                "siga_sha256": "aaa",
                "municipios_sha256": "bbb",
            },
            provenance={
                "content_sha256": "ccc",
                "municipios_zip_sha256": "bbb",
            },
            phase=PHASE_OPERACAO,
        )


def test_energy_panel_covers_399_and_reconciles() -> None:
    bundle = load_energy_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip(bundle.missing_reason_pt or "painel ausente")
    assert bundle.panel["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert bundle.panel["phase_filter"] == PHASE_OPERACAO
    assert bundle.panel.get("spatial_reference") == "qgis"
    totals = bundle.panel["totals"]
    assert (
        totals["n_empreendimentos_municipios"]
        + totals["n_empreendimentos_nao_associados"]
        == totals["n_empreendimentos_fase"]
    )
    assert totals["n_empreendimentos_fase"] == 310
    assert totals["n_empreendimentos_nao_associados"] == 34
    assert totals["soma_cobertura"] in {"completa", "parcial"}
    assert "conhecida" in str(totals.get("soma_rotulo") or "")
    sem = [
        m
        for m in bundle.panel["municipalities"]
        if m["status_dados"] == "sem_empreendimento"
    ]
    assert sem
    assert all(m["n_empreendimentos"] == 0 for m in sem)
    assert all(m.get("zero_semantics") for m in sem)
    assert all("zero_real" not in (m.get("zero_semantics") or "") for m in sem)
    assert ZERO_SEMANTICS_LIMITED in {m["zero_semantics"] for m in sem}
    assert bundle.panel.get("nao_associados_limitation_pt")
    recon = bundle.quality.get("spatial_reconciliation") or {}
    assert recon.get("ok") is True
    assert (recon.get("agreement") or {}).get("cd_mun_divergences") == 0
    ranked = municipalities_ranked(bundle, limit=5)
    assert ranked
    assert (
        ranked[0]["display_mw"]
        >= ranked[-1]["display_mw"]
    )


def test_energy_scope_totals_recalculate_for_technology() -> None:
    bundle = load_energy_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip("painel ausente")
    all_scope = energy_scope_totals(bundle, tipo=None)
    assert all_scope["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert all_scope["n_empreendimentos_fase"] == 310
    assert all_scope["n_empreendimentos_nao_associados"] == 34
    assert all_scope["metric_scope"] == "todas_tecnologias"
    ufv = energy_scope_totals(bundle, tipo="UFV")
    assert ufv["metric_scope"] == "tipo:UFV"
    assert ufv["municipality_count"] == EXPECTED_PR_MUNICIPALITY_COUNT
    assert ufv["n_empreendimentos_fase"] < all_scope["n_empreendimentos_fase"]
    assert (
        ufv["potencia_fiscalizada_mw_conhecida_fase"]
        < all_scope["potencia_fiscalizada_mw_conhecida_fase"]
    )
    assert ufv["n_municipios_com_usinas"] < all_scope["n_municipios_com_usinas"]
    assert ufv["n_empreendimentos_nao_associados"] == 25
    assert (
        ufv["n_empreendimentos_municipios"] + ufv["n_empreendimentos_nao_associados"]
        == ufv["n_empreendimentos_fase"]
    )
    assert "tipo:UFV" in ufv["kpi_caption_pt"]


def test_technology_filter_changes_mw_not_just_presence() -> None:
    bundle = load_energy_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip("painel ausente")
    all_rank = municipalities_ranked(bundle, tipo=None, limit=50)
    # Escolhe um município com mais de um tipo, se existir
    multi = None
    for row in bundle.panel["municipalities"]:
        por = row.get("por_tipo") or {}
        if len(por) >= 2:
            multi = row
            break
    if multi is None:
        pytest.skip("nenhum município multi-tecnologia no painel")
    tipos = list((multi.get("por_tipo") or {}).keys())
    t0 = tipos[0]
    proj_all = project_municipality_metrics(multi, tipo=None)
    proj_t = project_municipality_metrics(multi, tipo=t0)
    assert proj_t["metric_scope"] == f"tipo:{t0}"
    assert proj_t["display_n"] <= proj_all["display_n"]
    assert proj_t["display_mw"] <= proj_all["display_mw"] + 1e-9
    # Se o município tem outras tecnologias, MW filtrado deve ser estritamente menor
    if proj_t["display_n"] < proj_all["display_n"]:
        assert proj_t["display_mw"] < proj_all["display_mw"] + 1e-9
    ranked_t = municipalities_ranked(bundle, tipo=t0, limit=20)
    assert all(t0 in (r.get("por_tipo") or {}) for r in ranked_t)
    assert all(r["metric_scope"] == f"tipo:{t0}" for r in ranked_t)
    # Garantir que ranking não reutiliza MW total quando filtro ativo
    for r in ranked_t:
        raw = next(
            m
            for m in bundle.panel["municipalities"]
            if m["CD_MUN"] == r["CD_MUN"]
        )
        tipo_mw = float(
            ((raw.get("por_tipo") or {}).get(t0) or {}).get(
                "potencia_fiscalizada_mw"
            )
            or 0.0
        )
        assert float(r["display_mw"]) == pytest.approx(tipo_mw)
    assert all_rank  # sanity


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
    assert "Ausência" in cmp["disclaimer_pt"] or "ausência" in cmp["disclaimer_pt"]


def test_qgis_join_report_assignments_contract() -> None:
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
    assigns = assignments_from_qgis_report(report)
    assert len(assigns) == 310
    assert sum(1 for v in assigns.values() if v is not None) == 276
    assert sum(1 for v in assigns.values() if v is None) == 34
