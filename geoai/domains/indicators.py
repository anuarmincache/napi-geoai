"""Contratos de indicadores orientados a decisão (sem cálculo neste MVP)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from geoai.domains.registry import DomainId


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Metadados de um indicador futuro — contrato, não implementação.

    Cada indicador declara a pergunta prática que responde, o público,
    fontes, cobertura e limitações. Não executa ML nem rankings.
    """

    indicator_id: str
    domain_id: DomainId
    question_pt: str
    audience_pt: str
    source_ids: tuple[str, ...]
    coverage_pt: str
    limitations_pt: tuple[str, ...]
    unit: str | None = None
    related_dataset_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["domain_id"] = self.domain_id.value
        data["source_ids"] = list(self.source_ids)
        data["limitations_pt"] = list(self.limitations_pt)
        data["related_dataset_ids"] = list(self.related_dataset_ids)
        return data


# Exemplos de contrato (não calculados). Pilotam a forma esperada.
INDICATOR_CATALOG: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        indicator_id="energy.territorial_boundary.pr_uf",
        domain_id=DomainId.ENERGY,
        question_pt=(
            "Qual é o contorno oficial do Paraná para recortar análises "
            "energéticas territoriais?"
        ),
        audience_pt="pesquisador / analista técnico (base para leigos via UX)",
        source_ids=("ibge.malhas_municipais.pr_uf_2025",),
        coverage_pt="Estado do Paraná (UF), edição de malha documentada",
        limitations_pt=(
            "Não indica aptidão solar nem capacidade instalada.",
            "Não substitui consulta a órgãos licenciadores.",
        ),
        related_dataset_ids=("geoai.territorial_units.pr_uf",),
    ),
    IndicatorSpec(
        indicator_id="entrepreneurship.site_readiness.metadata",
        domain_id=DomainId.ENTREPRENEURSHIP,
        question_pt=(
            "Quais metadados didáticos um mapa/indicador precisa expor "
            "para um empreendedor leigo decidir com cautela?"
        ),
        audience_pt="empreendedor / público leigo / mediador técnico",
        source_ids=(),
        coverage_pt="contrato transversal a todos os domínios",
        limitations_pt=(
            "Não renderiza interface neste MVP.",
            "Não classifica oportunidades comerciais.",
        ),
    ),
)


def list_indicators(
    *,
    domain_id: DomainId | str | None = None,
) -> tuple[IndicatorSpec, ...]:
    if domain_id is None:
        return INDICATOR_CATALOG
    key = DomainId(domain_id) if not isinstance(domain_id, DomainId) else domain_id
    return tuple(i for i in INDICATOR_CATALOG if i.domain_id == key)


def get_indicator(indicator_id: str) -> IndicatorSpec:
    for item in INDICATOR_CATALOG:
        if item.indicator_id == indicator_id:
            return item
    raise KeyError(f"indicador desconhecido: {indicator_id}")
