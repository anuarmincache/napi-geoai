"""Agregações municipais MMGD. Contagem primária = empreendimentos."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.mmgd_normalize import NormalizedMmgdPlant

KW_PER_MW = 1000.0


@dataclass(slots=True)
class _MunBucket:
    n_empreendimentos: int = 0
    potencia_kw: float = 0.0
    n_potencia_ausente: int = 0
    qtd_uc_credito: int = 0
    n_uc_credito_ausente: int = 0
    by_tipo: dict[str, int] | None = None
    by_classe: dict[str, int] | None = None
    by_porte: dict[str, int] | None = None
    by_cadastral_year: dict[str, int] | None = None
    nome: str = ""

    def __post_init__(self) -> None:
        self.by_tipo = {}
        self.by_classe = {}
        self.by_porte = {}
        self.by_cadastral_year = {}


def _inc(counter: dict[str, int], key: str) -> None:
    label = key if key else "(vazio)"
    counter[label] = counter.get(label, 0) + 1


def aggregate_mmgd_by_municipality(
    plants: Iterable[NormalizedMmgdPlant],
    *,
    ibge_codes: set[str],
) -> dict[str, Any]:
    """Agrega empreendimentos válidos por CD_MUN.

    - ``n_empreendimentos``: contagem de registros (1 por CodEmpreendimento).
    - ``qtd_uc_recebe_credito``: soma do campo oficial de UCs beneficiárias;
      **não** substitui a contagem de empreendimentos.
    - Município sem registros no cadastro filtrado: zero confirmado se o
      código está na malha IBGE e a carga PR fechou; ausências de associação
      ficam em ``unmatched``.
    """

    buckets: dict[str, _MunBucket] = {}
    rejected: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    duplicate_codes = 0
    n_valid = 0
    n_rejected = 0
    potencia_kw_total = 0.0
    qtd_uc_total = 0
    by_tipo: dict[str, int] = {}
    by_classe: dict[str, int] = {}
    dat_conjunto = ""
    periodo = ""

    for plant in plants:
        if plant.reject_reason:
            n_rejected += 1
            rejected.append(
                {
                    "cod_empreendimento": plant.cod_empreendimento or "(vazio)",
                    "reason": plant.reject_reason,
                    "cd_mun": plant.cd_mun or "",
                }
            )
            continue
        assert plant.cd_mun is not None
        if plant.cod_empreendimento in seen_codes:
            duplicate_codes += 1
            n_rejected += 1
            rejected.append(
                {
                    "cod_empreendimento": plant.cod_empreendimento,
                    "reason": "CodEmpreendimento duplicado",
                    "cd_mun": plant.cd_mun,
                }
            )
            continue
        seen_codes.add(plant.cod_empreendimento)
        if plant.cd_mun not in ibge_codes:
            n_rejected += 1
            rejected.append(
                {
                    "cod_empreendimento": plant.cod_empreendimento,
                    "reason": "CD_MUN ausente da malha IBGE 399",
                    "cd_mun": plant.cd_mun,
                }
            )
            continue

        n_valid += 1
        bucket = buckets.get(plant.cd_mun)
        if bucket is None:
            bucket = _MunBucket(nome=plant.municipio_nome)
            buckets[plant.cd_mun] = bucket
        elif plant.municipio_nome and not bucket.nome:
            bucket.nome = plant.municipio_nome

        bucket.n_empreendimentos += 1
        if plant.potencia_instalada_kw is None:
            bucket.n_potencia_ausente += 1
        else:
            bucket.potencia_kw += plant.potencia_instalada_kw
            potencia_kw_total += plant.potencia_instalada_kw
        if plant.qtd_uc_recebe_credito is None:
            bucket.n_uc_credito_ausente += 1
        else:
            bucket.qtd_uc_credito += plant.qtd_uc_recebe_credito
            qtd_uc_total += plant.qtd_uc_recebe_credito
        assert bucket.by_tipo is not None
        assert bucket.by_classe is not None
        assert bucket.by_porte is not None
        assert bucket.by_cadastral_year is not None
        _inc(bucket.by_tipo, plant.tipo_geracao)
        _inc(bucket.by_classe, plant.classe_consumo)
        _inc(bucket.by_porte, plant.porte)
        year_key = (
            str(plant.cadastral_update_year)
            if plant.cadastral_update_year is not None
            else "(sem_ano)"
        )
        _inc(bucket.by_cadastral_year, year_key)
        _inc(by_tipo, plant.tipo_geracao)
        _inc(by_classe, plant.classe_consumo)
        if plant.dat_conjunto and not dat_conjunto:
            dat_conjunto = plant.dat_conjunto
        if plant.periodo_referencia and not periodo:
            periodo = plant.periodo_referencia

    municipalities: dict[str, dict[str, Any]] = {}
    for code in sorted(ibge_codes):
        bucket = buckets.get(code)
        if bucket is None:
            municipalities[code] = {
                "cd_mun": code,
                "n_empreendimentos": 0,
                "potencia_instalada_kw_conhecida": 0.0,
                "potencia_instalada_mw_conhecida": 0.0,
                "n_potencia_ausente": 0,
                "qtd_uc_recebe_credito": 0,
                "n_uc_credito_ausente": 0,
                "zero_confirmado_no_recorte": True,
                "by_tipo": {},
                "by_classe": {},
                "by_porte": {},
                "by_cadastral_update_year": {},
                "coverage": "zero_no_cadastro_pr",
            }
            continue
        municipalities[code] = {
            "cd_mun": code,
            "nome_fonte": bucket.nome,
            "n_empreendimentos": bucket.n_empreendimentos,
            "potencia_instalada_kw_conhecida": round(bucket.potencia_kw, 6),
            "potencia_instalada_mw_conhecida": round(
                bucket.potencia_kw / KW_PER_MW, 6
            ),
            "n_potencia_ausente": bucket.n_potencia_ausente,
            "qtd_uc_recebe_credito": bucket.qtd_uc_credito,
            "n_uc_credito_ausente": bucket.n_uc_credito_ausente,
            "zero_confirmado_no_recorte": False,
            "by_tipo": dict(sorted((bucket.by_tipo or {}).items())),
            "by_classe": dict(sorted((bucket.by_classe or {}).items())),
            "by_porte": dict(sorted((bucket.by_porte or {}).items())),
            "by_cadastral_update_year": dict(
                sorted((bucket.by_cadastral_year or {}).items())
            ),
            "coverage": "com_registros",
        }

    reasons: dict[str, int] = defaultdict(int)
    for item in rejected:
        reasons[item["reason"]] += 1

    return {
        "unit_primary": "empreendimento (CodEmpreendimento)",
        "unit_secondary_uc_credito": (
            "QtdUCRecebeCredito — unidades consumidoras que recebem créditos; "
            "não confundir com número de empreendimentos"
        ),
        "dat_conjunto": dat_conjunto,
        "periodo_referencia": periodo,
        "ibge_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "ibge_codes": len(ibge_codes),
        "n_valid": n_valid,
        "n_rejected": n_rejected,
        "duplicate_cod_empreendimento": duplicate_codes,
        "municipios_com_registros": sum(
            1 for row in municipalities.values() if row["n_empreendimentos"] > 0
        ),
        "municipios_zero_confirmado": sum(
            1
            for row in municipalities.values()
            if row["n_empreendimentos"] == 0
        ),
        "potencia_instalada_kw_conhecida": round(potencia_kw_total, 6),
        "potencia_instalada_mw_conhecida": round(potencia_kw_total / KW_PER_MW, 6),
        "qtd_uc_recebe_credito_total": qtd_uc_total,
        "by_tipo": dict(sorted(by_tipo.items())),
        "by_classe": dict(sorted(by_classe.items())),
        "reject_reasons": dict(sorted(reasons.items())),
        "rejected_sample": rejected[:50],
        "municipalities": municipalities,
        "temporal_note_pt": (
            "DthAtualizaCadastralEmpreend é atualização cadastral, "
            "não data de conexão. AnmPeriodoReferencia é o período do snapshot. "
            "Não interpretar anos cadastrais como crescimento histórico de conexões."
        ),
    }
