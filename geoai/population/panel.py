"""Painel municipal demográfico + indicadores (399 municípios)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.connectors.ibge_population import IBGE_POP_REFERENCE_DATE
from geoai.population.indicators import build_municipality_indicators


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _derived_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or _repo_root()) / "data" / "derived"


def population_panel_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "ibge_pr_population_2026_panel.json"


def population_provenance_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "ibge_pr_population_2026.provenance.json"


def population_quality_path(repo_root: Path | None = None) -> Path:
    return _derived_dir(repo_root) / "ibge_pr_population_2026.quality.json"


@dataclass(frozen=True, slots=True)
class PopulationPanelBundle:
    available: bool
    panel: dict[str, Any]
    provenance: dict[str, Any]
    quality: dict[str, Any]
    missing_reason_pt: str | None = None


def build_population_energy_panel(
    *,
    mesh_rows: list[dict[str, Any]],
    population_by_code: dict[str, dict[str, Any]],
    energy_by_code: dict[str, dict[str, Any]],
    nao_associados_n: int,
) -> dict[str, Any]:
    """Une malha + população + energia em ficha por CD_MUN (399)."""

    if len(mesh_rows) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise ValueError(
            f"malha com {len(mesh_rows)} municípios; "
            f"esperado {EXPECTED_PR_MUNICIPALITY_COUNT}"
        )
    municipalities: list[dict[str, Any]] = []
    for row in mesh_rows:
        code = str(row["CD_MUN"]).strip()
        name = str(row["NM_MUN"]).strip()
        area = row.get("AREA_KM2")
        area_f = float(area) if area is not None else None
        if area_f is not None and (area_f != area_f or area_f <= 0):
            area_f = None
        pop_rec = population_by_code.get(code)
        if pop_rec is None:
            raise ValueError(f"população ausente para {code}")
        pop = int(pop_rec["populacao_estimada_2026_hab"])
        energy = energy_by_code.get(code) or {
            "n_empreendimentos": 0,
            "potencia_fiscalizada_mw": 0.0,
            "potencia_fiscalizada_completa": True,
            "status_dados": "sem_empreendimento",
        }
        municipalities.append(
            build_municipality_indicators(
                cd_mun=code,
                nm_mun=name,
                area_km2=area_f,
                population=pop,
                energy=energy,
            )
        )

    pop_sum = sum(int(m["populacao_estimada_2026_hab"] or 0) for m in municipalities)
    return {
        "product": "ibge_pr_population_energy_indicators",
        "municipality_count": len(municipalities),
        "municipality_count_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "population_reference_date": IBGE_POP_REFERENCE_DATE,
        "population_sum_hab": pop_sum,
        "area_reference": "AREA_KM2 malha municipal IBGE municipio_2025",
        "energy_reference": (
            "SIGA/ANEEL potência fiscalizada conhecida, fase Operação, "
            "geração centralizada (não MMGD, não MWh)"
        ),
        "nao_associados_siga_n": nao_associados_n,
        "nao_associados_limitation_pt": (
            f"{nao_associados_n} empreendimentos SIGA sem associação municipal; "
            "sem_empreendimento ≠ ausência absoluta de usinas."
        ),
        "municipalities": municipalities,
    }


def load_population_panel_bundle(
    repo_root: Path | None = None,
) -> PopulationPanelBundle:
    root = repo_root or _repo_root()
    panel_p = population_panel_path(root)
    prov_p = population_provenance_path(root)
    qual_p = population_quality_path(root)
    if not panel_p.is_file() or not prov_p.is_file() or not qual_p.is_file():
        return PopulationPanelBundle(
            available=False,
            panel={},
            provenance={},
            quality={},
            missing_reason_pt=(
                "Artefatos populacionais ausentes. Gere com "
                "scripts/prepare_population_parana.py."
            ),
        )
    panel = json.loads(panel_p.read_text(encoding="utf-8"))
    provenance = json.loads(prov_p.read_text(encoding="utf-8"))
    quality = json.loads(qual_p.read_text(encoding="utf-8"))
    if int(panel.get("municipality_count") or 0) != EXPECTED_PR_MUNICIPALITY_COUNT:
        return PopulationPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            missing_reason_pt=(
                f"Painel populacional com {panel.get('municipality_count')} "
                f"municípios; esperado {EXPECTED_PR_MUNICIPALITY_COUNT}."
            ),
        )
    if not quality.get("codes_match_mesh"):
        return PopulationPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            missing_reason_pt="Join CD_MUN população×malha não validado (fail-closed).",
        )
    return PopulationPanelBundle(
        available=True,
        panel=panel,
        provenance=provenance,
        quality=quality,
        missing_reason_pt=None,
    )
