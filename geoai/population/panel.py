"""Painel municipal demográfico + indicadores (399 municípios)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.connectors.ibge_population import IBGE_POP_REFERENCE_DATE
from geoai.population.indicators import build_municipality_indicators


class EnergyCoverageError(ValueError):
    """Painel SIGA disponível mas cobertura municipal incompleta/divergente."""


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


def _assert_energy_covers_mesh(
    mesh_codes: set[str],
    energy_by_code: dict[str, dict[str, Any]],
) -> None:
    energy_codes = {str(c).strip() for c in energy_by_code}
    if len(energy_codes) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise EnergyCoverageError(
            f"Painel SIGA com {len(energy_codes)} códigos únicos; "
            f"esperado {EXPECTED_PR_MUNICIPALITY_COUNT}."
        )
    if len(energy_by_code) != len(energy_codes):
        raise EnergyCoverageError(
            "Painel SIGA com CD_MUN duplicados — fail-closed."
        )
    if energy_codes != mesh_codes:
        only_e = sorted(energy_codes - mesh_codes)[:5]
        only_m = sorted(mesh_codes - energy_codes)[:5]
        raise EnergyCoverageError(
            "CD_MUN SIGA ≠ malha: "
            f"só_siga={only_e} só_malha={only_m}"
        )


def build_population_energy_panel(
    *,
    mesh_rows: list[dict[str, Any]],
    population_by_code: dict[str, dict[str, Any]],
    energy_by_code: dict[str, dict[str, Any]],
    nao_associados_n: int,
    energy_source_available: bool,
) -> dict[str, Any]:
    """Une malha + população + energia em ficha por CD_MUN (399).

    - SIGA indisponível: população/densidade ok; energia = n/d
      (``energia_indisponivel``), sem inventar 0 MW/kW/hab.
    - SIGA disponível: exige 399 códigos únicos iguais à malha; sem fallback.
    """

    if len(mesh_rows) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise ValueError(
            f"malha com {len(mesh_rows)} municípios; "
            f"esperado {EXPECTED_PR_MUNICIPALITY_COUNT}"
        )
    mesh_codes = {str(r["CD_MUN"]).strip() for r in mesh_rows}
    if len(mesh_codes) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise ValueError("malha com CD_MUN duplicados — fail-closed")

    if energy_source_available:
        _assert_energy_covers_mesh(mesh_codes, energy_by_code)
    elif energy_by_code:
        raise EnergyCoverageError(
            "energy_by_code não-vazio com energy_source_available=False"
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
        if energy_source_available:
            energy = energy_by_code[code]
        else:
            energy = None
        municipalities.append(
            build_municipality_indicators(
                cd_mun=code,
                nm_mun=name,
                area_km2=area_f,
                population=pop,
                energy=energy,
                energy_source_available=energy_source_available,
                nao_associados_n=nao_associados_n,
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
        "energy_source_available": energy_source_available,
        "energy_reference": (
            "SIGA/ANEEL potência fiscalizada conhecida, fase Operação, "
            "geração centralizada (não MMGD, não MWh)"
            if energy_source_available
            else "SIGA indisponível — métricas energéticas n/d (não inventadas)"
        ),
        "nao_associados_siga_n": nao_associados_n if energy_source_available else None,
        "nao_associados_limitation_pt": (
            (
                f"{nao_associados_n} empreendimentos SIGA sem associação "
                "municipal; sem_empreendimento = zero vinculado "
                "(georreferenciado/associado), não ausência absoluta."
            )
            if energy_source_available
            else (
                "Painel SIGA indisponível: não há contagem de não associados "
                "nem zero energético inventado."
            )
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
