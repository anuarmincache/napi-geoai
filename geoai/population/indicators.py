"""Indicadores demográficos e energéticos per capita (sem inventar dados)."""

from __future__ import annotations

from typing import Any

STATUS_SEM_EMPREENDIMENTO = "sem_empreendimento"
STATUS_AGREGADO = "agregado"
STATUS_ENERGIA_INDISPONIVEL = "energia_indisponivel"

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
ZERO_VINCULADO_NOTE_PT = (
    "Zero vinculado: nenhuma usina SIGA georreferenciada associada a este "
    "polígono na fase Operação. Não é zero absoluto — podem existir "
    "empreendimentos sem associação municipal no painel."
)
ENERGIA_INDISPONIVEL_NOTE_PT = (
    "Indicadores energéticos indisponíveis: painel SIGA ausente ou inválido. "
    "População e densidade permanecem; MW/kW/hab = n/d (não inventados)."
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
    energy_source_available: bool,
    nao_associados_n: int = 0,
) -> dict[str, Any]:
    """Monta ficha tabular de um município (todas as chaves explícitas).

    Se ``energy_source_available`` é falso, métricas energéticas ficam n/d
    com ``status_energia_siga=energia_indisponivel`` — nunca inventa 0 MW.
    """

    dens = density_hab_km2(population, area_km2)
    limitation = (
        f"{nao_associados_n} empreendimento(s) SIGA sem associação municipal "
        "no painel. Zero vinculado ≠ ausência absoluta de usinas no município."
        if nao_associados_n
        else (
            "Município sem usina associada ≠ prova de ausência absoluta de "
            "empreendimentos (depende da cobertura do join espacial SIGA)."
        )
    )

    if not energy_source_available:
        return {
            "CD_MUN": cd_mun,
            "NM_MUN": nm_mun,
            "area_km2_ibge_2025": area_km2,
            "populacao_estimada_2026_hab": population,
            "populacao_referencia_data": "2026-07-01",
            "populacao_nao_e_censo": True,
            "densidade_demografica_estimada_2026_hab_km2": dens,
            "densidade_note_pt": DENSITY_NOTE_PT,
            "status_energia_siga": STATUS_ENERGIA_INDISPONIVEL,
            "n_empreendimentos_siga_operacao": None,
            "potencia_fiscalizada_conhecida_mw": None,
            "potencia_fiscalizada_completa": None,
            "potencia_fiscalizada_conhecida_kw_por_habitante": None,
            "kw_por_habitante_note_pt": ENERGIA_INDISPONIVEL_NOTE_PT,
            "potencia_fiscalizada_conhecida_mw_por_km2": None,
            "mw_por_km2_note_pt": ENERGIA_INDISPONIVEL_NOTE_PT,
            "usinas_por_100mil_hab": None,
            "energy_scope_pt": ENERGIA_INDISPONIVEL_NOTE_PT,
            "unassociated_plants_limitation_pt": limitation,
            "zero_vinculado": False,
        }

    if energy is None:
        raise ValueError(
            f"energy obrigatório para {cd_mun} quando SIGA está disponível"
        )

    status_energy = str(energy.get("status_dados") or "").strip()
    if status_energy not in {STATUS_SEM_EMPREENDIMENTO, STATUS_AGREGADO}:
        raise ValueError(
            f"status_dados energético inválido para {cd_mun}: {status_energy!r}"
        )

    n_raw = energy.get("n_empreendimentos")
    if n_raw is None:
        raise ValueError(f"n_empreendimentos ausente para {cd_mun}")
    n_plants = int(n_raw)
    mw = energy.get("potencia_fiscalizada_mw")
    if mw is None:
        raise ValueError(f"potencia_fiscalizada_mw ausente para {cd_mun}")
    mw_f = float(mw)
    completa = bool(energy.get("potencia_fiscalizada_completa", True))

    if status_energy == STATUS_SEM_EMPREENDIMENTO:
        # Zero vinculado conhecido (painel SIGA presente), não inventado.
        if n_plants != 0:
            raise ValueError(
                f"{cd_mun}: sem_empreendimento com n_empreendimentos={n_plants}"
            )
        kw_hab = 0.0 if population and population > 0 else None
        kw_note = (
            f"{ZERO_VINCULADO_NOTE_PT} {KW_PER_HAB_NOTE_PT}"
            if kw_hab is not None
            else "população estimada ausente ou ≤ 0"
        )
        mw_km2 = 0.0 if area_km2 and area_km2 > 0 else None
        mw_km2_note = (
            f"{ZERO_VINCULADO_NOTE_PT} {MW_PER_KM2_NOTE_PT}"
            if mw_km2 is not None
            else "área ausente ou ≤ 0"
        )
        return {
            "CD_MUN": cd_mun,
            "NM_MUN": nm_mun,
            "area_km2_ibge_2025": area_km2,
            "populacao_estimada_2026_hab": population,
            "populacao_referencia_data": "2026-07-01",
            "populacao_nao_e_censo": True,
            "densidade_demografica_estimada_2026_hab_km2": dens,
            "densidade_note_pt": DENSITY_NOTE_PT,
            "status_energia_siga": STATUS_SEM_EMPREENDIMENTO,
            "n_empreendimentos_siga_operacao": 0,
            "potencia_fiscalizada_conhecida_mw": 0.0,
            "potencia_fiscalizada_completa": completa,
            "potencia_fiscalizada_conhecida_kw_por_habitante": kw_hab,
            "kw_por_habitante_note_pt": kw_note,
            "potencia_fiscalizada_conhecida_mw_por_km2": mw_km2,
            "mw_por_km2_note_pt": mw_km2_note,
            "usinas_por_100mil_hab": plants_per_100k_hab(0, population),
            "energy_scope_pt": (
                "SIGA/ANEEL geração centralizada, fase Operação; MMGD excluído; "
                "MW ≠ MWh. Zero = usinas georreferenciadas associadas."
            ),
            "unassociated_plants_limitation_pt": limitation,
            "zero_vinculado": True,
        }

    kw_hab, kw_note = kw_per_inhabitant(
        mw_f, population, potencia_completa=completa
    )
    mw_km2, mw_km2_note = mw_per_km2(
        mw_f, area_km2, potencia_completa=completa
    )
    return {
        "CD_MUN": cd_mun,
        "NM_MUN": nm_mun,
        "area_km2_ibge_2025": area_km2,
        "populacao_estimada_2026_hab": population,
        "populacao_referencia_data": "2026-07-01",
        "populacao_nao_e_censo": True,
        "densidade_demografica_estimada_2026_hab_km2": dens,
        "densidade_note_pt": DENSITY_NOTE_PT,
        "status_energia_siga": STATUS_AGREGADO,
        "n_empreendimentos_siga_operacao": n_plants,
        "potencia_fiscalizada_conhecida_mw": mw_f,
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
        "unassociated_plants_limitation_pt": limitation,
        "zero_vinculado": False,
    }
