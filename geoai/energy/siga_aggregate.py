"""Agregação municipal SIGA — 399 municípios; desconhecido ≠ zero."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_normalize import NormalizedPlant

PHASE_OPERACAO = "Operação"

STATUS_AGREGADO = "agregado"
STATUS_SEM = "sem_empreendimento"
STATUS_UNASSIGNED = "nao_associado"

ZERO_SEMANTICS_LIMITED = (
    "sem_usina_georreferenciada_associada: nenhuma usina SIGA na fase "
    "filtrada com ponto válido vinculado a este polígono municipal. "
    "Não prova ausência absoluta de empreendimentos no município — "
    "existem usinas da fase sem associação espacial no painel."
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _derived_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or _repo_root()) / "data" / "derived"


def _kw_to_mw(value: float | None) -> float | None:
    """Converte kW→MW; ``None`` permanece desconhecido (não vira 0.0)."""

    if value is None:
        return None
    return round(float(value) / 1000.0, 6)


def _finite_kw(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    if num < 0:
        return None
    return num


def filter_plants_by_phase(
    plants: list[NormalizedPlant],
    *,
    phase: str | None = PHASE_OPERACAO,
) -> list[NormalizedPlant]:
    if phase is None:
        return list(plants)
    return [p for p in plants if p.phase == phase]


def _empty_tipo_bucket() -> dict[str, Any]:
    return {
        "n": 0,
        "potencia_fiscalizada_mw": 0.0,
        "n_potencia_fiscalizada_ausente": 0,
        "potencia_outorgada_mw": 0.0,
        "n_potencia_outorgada_ausente": 0,
    }


def aggregate_plants_by_municipality(
    joined: gpd.GeoDataFrame,
    municipality_catalog: list[dict[str, str]],
    *,
    phase: str = PHASE_OPERACAO,
) -> dict[str, Any]:
    """Gera painel com exatamente ``len(municipality_catalog)`` municípios.

    ``municipality_catalog``: lista ``{CD_MUN, NM_MUN}`` dos 399.
    Plantas sem CD_MUN vão para ``nao_associados`` (não inventam município).
    Capacidade fiscalizada ausente/negativa ≠ zero conhecido.
    """

    work = joined.copy()
    if "DscFaseUsina" in work.columns:
        work = work[work["DscFaseUsina"].astype(str) == phase]

    by_code: dict[str, dict[str, Any]] = {}
    for _, row in work.iterrows():
        code = row.get("CD_MUN")
        if code is None or (isinstance(code, float) and code != code):
            continue
        code = str(code).strip()
        if not code or code.upper() == "NULL":
            continue
        bucket = by_code.setdefault(
            code,
            {
                "n": 0,
                "fiscalizada_kw_sum": 0.0,
                "fiscalizada_ausente": 0,
                "outorgada_kw_sum": 0.0,
                "outorgada_ausente": 0,
                "tipos": {},
                "plants": [],
            },
        )
        bucket["n"] += 1
        fis = _finite_kw(row.get("potencia_fiscalizada_kw"))
        out = _finite_kw(row.get("potencia_outorgada_kw"))
        if fis is None:
            bucket["fiscalizada_ausente"] += 1
        else:
            bucket["fiscalizada_kw_sum"] += fis
        if out is None:
            bucket["outorgada_ausente"] += 1
        else:
            bucket["outorgada_kw_sum"] += out
        tipo = str(row.get("SigTipoGeracao") or "")
        tb = bucket["tipos"].setdefault(tipo, _empty_tipo_bucket())
        tb["n"] += 1
        if fis is None:
            tb["n_potencia_fiscalizada_ausente"] += 1
        else:
            tb["potencia_fiscalizada_mw"] = round(
                tb["potencia_fiscalizada_mw"] + float(_kw_to_mw(fis) or 0.0),
                6,
            )
        if out is None:
            tb["n_potencia_outorgada_ausente"] += 1
        else:
            tb["potencia_outorgada_mw"] = round(
                tb["potencia_outorgada_mw"] + float(_kw_to_mw(out) or 0.0),
                6,
            )
        bucket["plants"].append(
            {
                "CodCEG": str(row.get("CodCEG")),
                "nome": str(row.get("NomEmpreendimento") or ""),
                "tipo": tipo,
                "potencia_fiscalizada_mw": _kw_to_mw(fis),
                "potencia_outorgada_mw": _kw_to_mw(out),
                "potencia_fiscalizada_conhecida": fis is not None,
                "potencia_outorgada_conhecida": out is not None,
            }
        )

    municipalities: list[dict[str, Any]] = []
    for item in municipality_catalog:
        code = str(item["CD_MUN"]).strip()
        name = str(item["NM_MUN"]).strip()
        hit = by_code.get(code)
        if not hit:
            municipalities.append(
                {
                    "CD_MUN": code,
                    "NM_MUN": name,
                    "status_dados": STATUS_SEM,
                    "n_empreendimentos": 0,
                    "potencia_fiscalizada_mw": 0.0,
                    "potencia_outorgada_mw": 0.0,
                    "n_potencia_fiscalizada_ausente": 0,
                    "n_potencia_outorgada_ausente": 0,
                    "potencia_fiscalizada_cobertura": 1.0,
                    "potencia_fiscalizada_completa": True,
                    "por_tipo": {},
                    "zero_semantics": ZERO_SEMANTICS_LIMITED,
                }
            )
            continue
        n = int(hit["n"])
        aus_f = int(hit["fiscalizada_ausente"])
        aus_o = int(hit["outorgada_ausente"])
        known_mw = _kw_to_mw(hit["fiscalizada_kw_sum"]) or 0.0
        known_out = _kw_to_mw(hit["outorgada_kw_sum"]) or 0.0
        coverage = (n - aus_f) / n if n else 1.0
        municipalities.append(
            {
                "CD_MUN": code,
                "NM_MUN": name,
                "status_dados": STATUS_AGREGADO,
                "n_empreendimentos": n,
                "potencia_fiscalizada_mw": known_mw,
                "potencia_outorgada_mw": known_out,
                "n_potencia_fiscalizada_ausente": aus_f,
                "n_potencia_outorgada_ausente": aus_o,
                "potencia_fiscalizada_cobertura": round(coverage, 6),
                "potencia_fiscalizada_completa": aus_f == 0,
                "por_tipo": hit["tipos"],
                "empreendimentos": hit["plants"],
                "zero_semantics": None,
            }
        )

    unassigned_rows = work[work["match_status"].astype(str) != "matched"]

    nao_associados = []
    for _, row in unassigned_rows.iterrows():
        fis = _finite_kw(row.get("potencia_fiscalizada_kw"))
        out = _finite_kw(row.get("potencia_outorgada_kw"))
        nao_associados.append(
            {
                "CodCEG": str(row.get("CodCEG")),
                "nome": str(row.get("NomEmpreendimento") or ""),
                "fase": str(row.get("DscFaseUsina") or ""),
                "tipo": str(row.get("SigTipoGeracao") or ""),
                "match_status": str(row.get("match_status") or STATUS_UNASSIGNED),
                "municipios_declarados": str(row.get("municipios_declarados") or ""),
                "potencia_fiscalizada_mw": _kw_to_mw(fis),
                "potencia_outorgada_mw": _kw_to_mw(out),
                "potencia_fiscalizada_conhecida": fis is not None,
                "potencia_outorgada_conhecida": out is not None,
            }
        )

    sum_mun_fis = sum(float(m["potencia_fiscalizada_mw"]) for m in municipalities)
    sum_mun_n = sum(int(m["n_empreendimentos"]) for m in municipalities)
    sum_mun_aus = sum(int(m["n_potencia_fiscalizada_ausente"]) for m in municipalities)
    sum_un_fis = sum(
        float(p["potencia_fiscalizada_mw"])
        for p in nao_associados
        if p.get("potencia_fiscalizada_conhecida")
    )
    sum_un_aus = sum(
        1 for p in nao_associados if not p.get("potencia_fiscalizada_conhecida")
    )
    sum_un_n = len(nao_associados)
    aus_fase = sum_mun_aus + sum_un_aus
    completa = aus_fase == 0

    return {
        "phase_filter": phase,
        "spatial_reference": "qgis",
        "metric_note": (
            "Capacidade fiscalizada/outorgada em MW (kW/1000), apenas valores "
            "conhecidos e não negativos. Ausência ≠ zero. "
            "Não é geração efetiva (MWh). Não inclui MMGD."
        ),
        "municipality_count": len(municipalities),
        "municipality_count_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "municipalities": municipalities,
        "nao_associados": nao_associados,
        "nao_associados_limitation_pt": (
            f"{sum_un_n} empreendimentos da fase sem associação municipal "
            "(coords ausentes/inválidas, fora da malha ou ausentes no join "
            "QGIS). Municípios 'sem_empreendimento' referem-se apenas a "
            "usinas georreferenciadas e vinculadas — não são zero absoluto."
        ),
        "totals": {
            "n_empreendimentos_municipios": sum_mun_n,
            "n_empreendimentos_nao_associados": sum_un_n,
            "n_empreendimentos_fase": sum_mun_n + sum_un_n,
            "potencia_fiscalizada_mw_municipios": round(sum_mun_fis, 6),
            "potencia_fiscalizada_mw_nao_associados": round(sum_un_fis, 6),
            "potencia_fiscalizada_mw_conhecida_fase": round(
                sum_mun_fis + sum_un_fis, 6
            ),
            # Alias explícito: não rotular como total sem ressalva.
            "potencia_fiscalizada_mw_total_fase": round(sum_mun_fis + sum_un_fis, 6),
            "n_potencia_fiscalizada_ausente_fase": aus_fase,
            "soma_cobertura": "completa" if completa else "parcial",
            "soma_rotulo": (
                "capacidade_fiscalizada_conhecida_mw"
                if completa
                else "capacidade_fiscalizada_conhecida_mw_parcial"
            ),
        },
        "totals_caveat_pt": (
            None
            if completa
            else (
                f"Soma parcial: {aus_fase} registro(s) sem potência fiscalizada "
                "válida (ausente/inválida/negativa). Não interpretar o total "
                "como cobertura completa da capacidade da fase."
            )
        ),
        "reconciliation_note": (
            "n_fase = municípios + não associados (mesma fase). "
            "MW = soma apenas de potências fiscalizadas conhecidas. "
            "CD_MUN de referência = QGIS (reconciliado com GeoPandas)."
        ),
    }


@dataclass(frozen=True, slots=True)
class EnergyPanelBundle:
    available: bool
    panel: dict[str, Any]
    provenance: dict[str, Any]
    quality: dict[str, Any]
    qgis_report: dict[str, Any] | None
    missing_reason_pt: str | None = None


def energy_panel_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "siga_pr_energy_panel.json"


def energy_provenance_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "siga_pr_energy.provenance.json"


def energy_quality_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "siga_pr_energy.quality.json"


def energy_qgis_report_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "siga_pr_qgis_join_report.json"


def load_energy_panel_bundle(repo_root: Path | None = None) -> EnergyPanelBundle:
    root = repo_root or _repo_root()
    panel_p = energy_panel_path(root)
    prov_p = energy_provenance_path(root)
    qual_p = energy_quality_path(root)
    qgis_p = energy_qgis_report_path(root)
    if not panel_p.is_file() or not prov_p.is_file() or not qual_p.is_file():
        return EnergyPanelBundle(
            available=False,
            panel={},
            provenance={},
            quality={},
            qgis_report=None,
            missing_reason_pt=(
                "Artefatos SIGA ausentes. Gere com "
                "scripts/prepare_siga_parana.py (e worker QGIS)."
            ),
        )
    panel = json.loads(panel_p.read_text(encoding="utf-8"))
    provenance = json.loads(prov_p.read_text(encoding="utf-8"))
    quality = json.loads(qual_p.read_text(encoding="utf-8"))
    qgis_report = (
        json.loads(qgis_p.read_text(encoding="utf-8")) if qgis_p.is_file() else None
    )
    if int(panel.get("municipality_count") or 0) != EXPECTED_PR_MUNICIPALITY_COUNT:
        return EnergyPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            qgis_report=qgis_report,
            missing_reason_pt=(
                f"Painel com {panel.get('municipality_count')} municípios; "
                f"esperado {EXPECTED_PR_MUNICIPALITY_COUNT}."
            ),
        )
    recon = quality.get("spatial_reconciliation") or {}
    if qgis_report is None:
        return EnergyPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            qgis_report=None,
            missing_reason_pt=(
                "Relatório QGIS ausente — referência espacial obrigatória."
            ),
        )
    if not recon.get("ok", False):
        return EnergyPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            qgis_report=qgis_report,
            missing_reason_pt=(
                "Reconciliação espacial QGIS↔GeoPandas não OK (fail-closed)."
            ),
        )
    if not (qgis_report.get("assignments") or []):
        return EnergyPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            qgis_report=qgis_report,
            missing_reason_pt=(
                "Relatório QGIS sem assignments CodCEG→CD_MUN."
            ),
        )
    return EnergyPanelBundle(
        available=True,
        panel=panel,
        provenance=provenance,
        quality=quality,
        qgis_report=qgis_report,
        missing_reason_pt=None,
    )
