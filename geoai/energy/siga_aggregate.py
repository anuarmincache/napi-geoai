"""Agregação municipal SIGA — 399 municípios, zero ≠ ausência de ingestão."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_normalize import NormalizedPlant

PHASE_OPERACAO = "Operação"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _derived_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or _repo_root()) / "data" / "derived"

STATUS_AGREGADO = "agregado"
STATUS_SEM = "sem_empreendimento"
STATUS_UNASSIGNED = "nao_associado"


def _kw_to_mw(value: float | None) -> float:
    if value is None:
        return 0.0
    return round(float(value) / 1000.0, 6)


def filter_plants_by_phase(
    plants: list[NormalizedPlant],
    *,
    phase: str | None = PHASE_OPERACAO,
) -> list[NormalizedPlant]:
    if phase is None:
        return list(plants)
    return [p for p in plants if p.phase == phase]


def aggregate_plants_by_municipality(
    joined: gpd.GeoDataFrame,
    municipality_catalog: list[dict[str, str]],
    *,
    phase: str = PHASE_OPERACAO,
) -> dict[str, Any]:
    """Gera painel com exatamente ``len(municipality_catalog)`` municípios.

    ``municipality_catalog``: lista ``{CD_MUN, NM_MUN}`` dos 399.
    Plantas sem CD_MUN vão para ``nao_associados`` (não inventam município).
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
        bucket = by_code.setdefault(
            code,
            {
                "n": 0,
                "fiscalizada_kw": 0.0,
                "outorgada_kw": 0.0,
                "tipos": {},
                "plants": [],
            },
        )
        bucket["n"] += 1
        fis = row.get("potencia_fiscalizada_kw")
        out = row.get("potencia_outorgada_kw")
        if fis is not None and fis == fis:
            bucket["fiscalizada_kw"] += float(fis)
        if out is not None and out == out:
            bucket["outorgada_kw"] += float(out)
        tipo = str(row.get("SigTipoGeracao") or "")
        bucket["tipos"][tipo] = bucket["tipos"].get(tipo, 0) + 1
        bucket["plants"].append(
            {
                "CodCEG": str(row.get("CodCEG")),
                "nome": str(row.get("NomEmpreendimento") or ""),
                "tipo": tipo,
                "potencia_fiscalizada_mw": _kw_to_mw(
                    float(fis) if fis == fis and fis is not None else None
                ),
                "potencia_outorgada_mw": _kw_to_mw(
                    float(out) if out == out and out is not None else None
                ),
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
                    "por_tipo": {},
                    "zero_semantics": (
                        "zero_real: nenhum empreendimento SIGA na fase filtrada "
                        "associado a este município após join espacial completo."
                    ),
                }
            )
            continue
        municipalities.append(
            {
                "CD_MUN": code,
                "NM_MUN": name,
                "status_dados": STATUS_AGREGADO,
                "n_empreendimentos": int(hit["n"]),
                "potencia_fiscalizada_mw": _kw_to_mw(hit["fiscalizada_kw"]),
                "potencia_outorgada_mw": _kw_to_mw(hit["outorgada_kw"]),
                "por_tipo": hit["tipos"],
                "empreendimentos": hit["plants"],
                "zero_semantics": None,
            }
        )

    unassigned_rows = work[work["match_status"].astype(str) != "matched"]
    nao_associados = []
    for _, row in unassigned_rows.iterrows():
        fis = row.get("potencia_fiscalizada_kw")
        out = row.get("potencia_outorgada_kw")
        nao_associados.append(
            {
                "CodCEG": str(row.get("CodCEG")),
                "nome": str(row.get("NomEmpreendimento") or ""),
                "fase": str(row.get("DscFaseUsina") or ""),
                "tipo": str(row.get("SigTipoGeracao") or ""),
                "match_status": str(row.get("match_status") or STATUS_UNASSIGNED),
                "municipios_declarados": str(row.get("municipios_declarados") or ""),
                "potencia_fiscalizada_mw": _kw_to_mw(
                    float(fis) if fis is not None and fis == fis else None
                ),
                "potencia_outorgada_mw": _kw_to_mw(
                    float(out) if out is not None and out == out else None
                ),
            }
        )

    sum_mun_fis = sum(m["potencia_fiscalizada_mw"] for m in municipalities)
    sum_mun_n = sum(m["n_empreendimentos"] for m in municipalities)
    sum_un_fis = sum(p["potencia_fiscalizada_mw"] for p in nao_associados)
    sum_un_n = len(nao_associados)

    return {
        "phase_filter": phase,
        "metric_note": (
            "Capacidade fiscalizada/outorgada em MW (kW/1000). "
            "Não é geração efetiva (MWh). Não inclui MMGD."
        ),
        "municipality_count": len(municipalities),
        "municipality_count_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "municipalities": municipalities,
        "nao_associados": nao_associados,
        "totals": {
            "n_empreendimentos_municipios": sum_mun_n,
            "n_empreendimentos_nao_associados": sum_un_n,
            "n_empreendimentos_fase": sum_mun_n + sum_un_n,
            "potencia_fiscalizada_mw_municipios": round(sum_mun_fis, 6),
            "potencia_fiscalizada_mw_nao_associados": round(sum_un_fis, 6),
            "potencia_fiscalizada_mw_total_fase": round(sum_mun_fis + sum_un_fis, 6),
        },
        "reconciliation_note": (
            "total_fase ≈ soma municípios + não associados "
            "(mesma fase e unidade MW fiscalizada)."
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
    return EnergyPanelBundle(
        available=True,
        panel=panel,
        provenance=provenance,
        quality=quality,
        qgis_report=qgis_report,
        missing_reason_pt=None,
    )
