"""Visões de domínio para UI — montadas a partir dos contratos MVP 06."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from geoai.domains import (
    DomainId,
    DomainSpec,
    IndicatorSpec,
    get_domain,
    list_domains,
    list_indicators,
)


@dataclass(frozen=True, slots=True)
class DomainAvailability:
    """Disponibilidade honesta de seções na interface."""

    domain_id: DomainId
    status: str  # available | partial | planned
    available_now_pt: tuple[str, ...]
    planned_pt: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["domain_id"] = self.domain_id.value
        data["available_now_pt"] = list(self.available_now_pt)
        data["planned_pt"] = list(self.planned_pt)
        return data


_AVAILABILITY: dict[DomainId, DomainAvailability] = {
    DomainId.ENERGY: DomainAvailability(
        domain_id=DomainId.ENERGY,
        status="partial",
        available_now_pt=(
            "Painel SIGA/ANEEL: capacidade fiscalizada (MW) por município.",
            "População IBGE 2026 + densidade e kW/hab (ficha municipal).",
            "Join espacial QGIS + agregados dos 399 municípios IBGE.",
            "Mapa do contorno oficial do Paraná (base territorial).",
            "Catálogo ANEEL/INPE/ONS (MMGD e aptidão solar ainda fora).",
        ),
        planned_pt=(
            "Aptidão solar com pesos e restrições explícitos.",
            "Geração efetiva (MWh) e MMGD em MVP separados.",
        ),
    ),
    DomainId.ENVIRONMENT: DomainAvailability(
        domain_id=DomainId.ENVIRONMENT,
        status="planned",
        available_now_pt=(
            "Registro de domínio e hooks MapBiomas (catalogado).",
        ),
        planned_pt=(
            "Camadas de uso/cobertura e máscaras ambientais.",
            "Ingestão operacional MapBiomas/Sentinel.",
        ),
    ),
    DomainId.AGRICULTURE: DomainAvailability(
        domain_id=DomainId.AGRICULTURE,
        status="planned",
        available_now_pt=("Registro de domínio e reuso futuro de LULC.",),
        planned_pt=("Indicadores agrícolas territoriais.",),
    ),
    DomainId.ENTREPRENEURSHIP: DomainAvailability(
        domain_id=DomainId.ENTREPRENEURSHIP,
        status="partial",
        available_now_pt=(
            "Metadados didáticos em 3 níveis.",
            "Perguntas práticas dos IndicatorSpec.",
            "Navegação clara do que está pronto vs planejado.",
        ),
        planned_pt=(
            "Fontes Sebrae/IPARDES/Invest Paraná (#20).",
            "Painéis de oportunidade (sem rankings inventados).",
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class DomainCard:
    spec: DomainSpec
    availability: DomainAvailability
    indicators: tuple[IndicatorSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "availability": self.availability.to_dict(),
            "indicators": [i.to_dict() for i in self.indicators],
        }


def build_domain_card(domain_id: DomainId | str) -> DomainCard:
    key = DomainId(domain_id) if not isinstance(domain_id, DomainId) else domain_id
    return DomainCard(
        spec=get_domain(key),
        availability=_AVAILABILITY[key],
        indicators=list_indicators(domain_id=key),
    )


def list_domain_cards() -> tuple[DomainCard, ...]:
    return tuple(build_domain_card(d.domain_id) for d in list_domains())


def status_label_pt(status: str) -> str:
    return {
        "available": "Disponível",
        "partial": "Parcialmente disponível",
        "planned": "Planejado",
    }.get(status, status)
