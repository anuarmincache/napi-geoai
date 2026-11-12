"""Indicadores demográficos e energéticos per capita (sem inventar dados)."""

from __future__ import annotations

from typing import Any

DENSITY_NOTE_PT = (
    "Densidade estimada = população IBGE 01/07/2026 ÷ AREA_KM2 da malha "
    "municipal IBGE 2025. Mistura referências temporais; não é a densidade "
    "censitária oficial do Censo."
)
KW_PER_HAB_NOTE_PT = (
    "kW/hab = potência fiscalizada conhecida SIGA (MW×1000) ÷ população "
    "estimada 2026. Escopo: geração centralizada em Operação; não é MWh, "
    "MMGD nem consumo."
)
MW_PER_KM2_NOTE_PT = (
    "MW/km² = potência fiscalizada conhecida SIGA ÷ AREA_KM2 (malha 2025). "
    "Não é aptidão energética."
)


def safe_div(numer: float | None, denom: float | None) -> float | None:
    """Divisão segura; None se divisor ausente/≤0 ou numerador ausente."""

    if numer is None or denom is None:
        return None
    if denom <= 0:
        return None
    return float(numer) / float(denom)


def density_hab_km2(population: int | None, area_km2: float | None) -> float | None:
    value = safe_div(
        float(population) if population is not None else None,
        area_km2,
    )
    if value is None:
        return None
    return round(value, 4)


def kw_per_inhabitant(
    potencia_fiscalizada_mw_conhecida: float | None,
    population: int | None,
    *,
    potencia_completa: bool = True,
) -> tuple[float | None, str | None]:
    """Retorna (kW/hab, ressalva). n/d se incompleto ou pop inválida."""

    if not potencia_completa:
        return None, "cobertura de potência fiscalizada incompleta no município"
    if potencia_fiscalizada_mw_conhecida is None:
        return None, "potência fiscalizada conhecida ausente"
    if population is None or population <= 0:
        return None, "população estimada ausente ou ≤ 0"
    kw = potencia_fiscalizada_mw_conhecida * 1000.0
    value = safe_div(kw, float(population))
    if value is None:
        return None, "divisão inválida"
    return round(value, 6), None


def mw_per_km2(
    potencia_fiscalizada_mw_conhecida: float | None,
    area_km2: float | None,
    *,
    potencia_completa: bool = True,
) -> tuple[float | None, str | None]:
    if not potencia_completa:
        return None, "cobertura de potência fiscalizada incompleta no município"
    if potencia_fiscalizada_mw_conhecida is None:
        return None, "potência fiscalizada conhecida ausente"
    value = safe_div(potencia_fiscalizada_mw_conhecida, area_km2)
    if value is None:
        return None, "área ausente ou ≤ 0"
    return round(value, 6), None


def plants_per_100k_hab(
    n_empreendimentos: int | None,
    population: int | None,
) -> float | None:
    if n_empreendimentos is None or population is None or population <= 0:
        return None
    return round(100_000.0 * float(n_empreendimentos) / float(population), 4)


def build_municipality_indicators(
    *,
    cd_mun: str,
    nm_mun: str,
    area_km2: float | None,
    population: int | None,
    energy: dict[str, Any] | None,
) -> dict[str, Any]:
    """Monta ficha tabular de um município (todas as chaves explícitas)."""

    energy = energy or {}
    n_plants = int(energy.get("n_empreendimentos") or 0)
    mw = energy.get("potencia_fiscalizada_mw")
    completa = bool(energy.get("potencia_fiscalizada_completa", True))
    status_energy = energy.get("status_dados") or "sem_empreendimento"
    dens = density_hab_km2(population, area_km2)
    kw_hab, kw_note = kw_per_inhabitant(
        float(mw) if mw is not None else None,
        population,
        potencia_completa=completa,
    )
    # Município sem usina associada: kW/hab = 0 conhecido (MW=0), não n/d,
    # desde que pop válida e cobertura completa (nada ausente).
    if status_energy == "sem_empreendimento" and population and population > 0:
        if completa and (mw is None or float(mw) == 0.0):
            kw_hab, kw_note = 0.0, None
    mw_km2, mw_km2_note = mw_per_km2(
        float(mw) if mw is not None else (
            0.0 if status_energy == "sem_empreendimento" else None
        ),
        area_km2,
        potencia_completa=completa,
    )
    if status_energy == "sem_empreendimento" and area_km2 and area_km2 > 0:
        if completa:
            mw_km2, mw_km2_note = 0.0, None

    return {
        "CD_MUN": cd_mun,
        "NM_MUN": nm_mun,
        "area_km2_ibge_2025": area_km2,
        "populacao_estimada_2026_hab": population,
        "populacao_referencia_data": "2026-07-01",
        "populacao_nao_e_censo": True,
        "densidade_demografica_estimada_2026_hab_km2": dens,
        "densidade_note_pt": DENSITY_NOTE_PT,
        "status_energia_siga": status_energy,
        "n_empreendimentos_siga_operacao": n_plants,
        "potencia_fiscalizada_conhecida_mw": (
            float(mw) if mw is not None else (
                0.0 if status_energy == "sem_empreendimento" else None
            )
        ),
        "potencia_fiscalizada_completa": completa,
        "potencia_fiscalizada_conhecida_kw_por_habitante": kw_hab,
        "kw_por_habitante_note_pt": kw_note or KW_PER_HAB_NOTE_PT,
        "potencia_fiscalizada_conhecida_mw_por_km2": mw_km2,
        "mw_por_km2_note_pt": mw_km2_note or MW_PER_KM2_NOTE_PT,
        "usinas_por_100mil_hab": plants_per_100k_hab(n_plants, population),
        "energy_scope_pt": (
            "SIGA/ANEEL geração centralizada, fase Operação; MMGD excluído; "
            "MW ≠ MWh."
        ),
        "unassociated_plants_limitation_pt": (
            "Município sem usina associada ≠ prova de ausência absoluta: "
            "há empreendimentos SIGA sem associação municipal no painel."
        ),
    }
