"""Registro de domínios temáticos — infraestrutura compartilhada vs domínio."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class DomainId(StrEnum):
    """Identificadores estáveis dos domínios de negócio do NAPI GeoAI."""

    ENERGY = "energy"
    ENVIRONMENT = "environment"
    AGRICULTURE = "agriculture"
    ENTREPRENEURSHIP = "entrepreneurship"


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """Especificação de um domínio temático.

    Domínios são independentes na apresentação futura, mas compartilham
    conectores, proveniência, PostGIS e qualidade — sem banco dedicado.
    """

    domain_id: DomainId
    title_pt: str
    title_en: str
    summary_pt: str
    shared_infrastructure: tuple[str, ...]
    expansion_hooks: tuple[str, ...]
    out_of_scope_now: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["domain_id"] = self.domain_id.value
        data["shared_infrastructure"] = list(self.shared_infrastructure)
        data["expansion_hooks"] = list(self.expansion_hooks)
        data["out_of_scope_now"] = list(self.out_of_scope_now)
        return data


_SHARED = (
    "geoai.connectors",
    "geoai.quality",
    "geoai.db",
    "geoai.boundaries",
    "ProvenanceRecord",
    "SourceSpec",
)

DOMAIN_REGISTRY: dict[DomainId, DomainSpec] = {
    DomainId.ENERGY: DomainSpec(
        domain_id=DomainId.ENERGY,
        title_pt="Energia",
        title_en="Energy",
        summary_pt=(
            "Fontes e indicadores energéticos territoriais "
            "(capacidade, geração, irradiação — separados)."
        ),
        shared_infrastructure=_SHARED,
        expansion_hooks=(
            "connector:aneel.siga",
            "connector:inpe.labren (catalogued)",
            "connector:ons (catalogued)",
            "future:aptidao_solar_weights",
        ),
        out_of_scope_now=(
            "cálculo de aptidão solar",
            "ML",
            "rankings comerciais",
        ),
    ),
    DomainId.ENVIRONMENT: DomainSpec(
        domain_id=DomainId.ENVIRONMENT,
        title_pt="Meio ambiente",
        title_en="Environment",
        summary_pt=(
            "Cobertura/uso do solo e restrições ambientais para decisões "
            "territoriais sustentáveis."
        ),
        shared_infrastructure=_SHARED,
        expansion_hooks=(
            "connector:mapbiomas (catalogued)",
            "future:environmental_masks",
        ),
        out_of_scope_now=("ingestão massiva MapBiomas/Sentinel", "GEE pipeline"),
    ),
    DomainId.AGRICULTURE: DomainSpec(
        domain_id=DomainId.AGRICULTURE,
        title_pt="Agricultura",
        title_en="Agriculture",
        summary_pt=(
            "Camadas agrícolas e de uso da terra para análise espacial "
            "e apoio a decisões produtivas."
        ),
        shared_infrastructure=_SHARED,
        expansion_hooks=(
            "reuse:mapbiomas_lulc",
            "future:agro_indicators",
        ),
        out_of_scope_now=("modelos preditivos agrícolas", "IoT de campo"),
    ),
    DomainId.ENTREPRENEURSHIP: DomainSpec(
        domain_id=DomainId.ENTREPRENEURSHIP,
        title_pt="Empreendedorismo sustentável",
        title_en="Sustainable entrepreneurship",
        summary_pt=(
            "Perguntas práticas ao empreendedor: o que o indicador responde, "
            "para quem, com quais fontes e limitações."
        ),
        shared_infrastructure=_SHARED,
        expansion_hooks=(
            "presentation:didactic_metadata",
            "indicators:decision_oriented",
        ),
        out_of_scope_now=("site/dashboard", "CRM", "paywall"),
    ),
}


def get_domain(domain_id: DomainId | str) -> DomainSpec:
    key = DomainId(domain_id) if not isinstance(domain_id, DomainId) else domain_id
    try:
        return DOMAIN_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"domínio desconhecido: {domain_id}") from exc


def list_domains() -> tuple[DomainSpec, ...]:
    return tuple(DOMAIN_REGISTRY[k] for k in DomainId)
