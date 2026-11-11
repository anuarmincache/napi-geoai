"""Contratos de metadados didáticos e requisitos de expansão (sem UI).

Suportam UX futura em 3 níveis (básico / intermediário / técnico),
mapa interativo e acessibilidade — apenas como especificação.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class AudienceLevel(StrEnum):
    """Níveis de profundidade para interface futura."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    TECHNICAL = "technical"


@dataclass(frozen=True, slots=True)
class DidacticCopy:
    """Textos por nível de audiência (pt-BR neste MVP)."""

    level: AudienceLevel
    title: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["level"] = self.level.value
        return data


@dataclass(frozen=True, slots=True)
class DidacticMetadata:
    """Metadados suficientes para renderizar camada/indicador no futuro site.

    Não implementa mapa, acessibilidade nem i18n runtime — só o contrato.
    """

    resource_id: str
    copies: tuple[DidacticCopy, ...]
    unit: str | None
    legend_pt: str
    source_attribution_pt: str
    updated_at: str
    uncertainty_pt: str
    methodology_url: str | None = None
    accessibility_notes_pt: str = (
        "Contraste AA; textos alternativos para mapas; "
        "não depender só de cor na legenda."
    )
    interactive_map_requirements: tuple[str, ...] = (
        "camada vetorial com CRS declarado",
        "popup com fonte + data + limitações",
        "controle de opacidade",
    )
    extra: dict[str, Any] = field(default_factory=dict)

    def copy_for(self, level: AudienceLevel) -> DidacticCopy:
        for item in self.copies:
            if item.level == level:
                return item
        raise KeyError(f"nível ausente em {self.resource_id}: {level}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["copies"] = [c.to_dict() for c in self.copies]
        payload["interactive_map_requirements"] = list(
            self.interactive_map_requirements
        )
        return payload


@dataclass(frozen=True, slots=True)
class ExpansionRequirement:
    """Requisito explícito de expansão (o que falta para o próximo incremento)."""

    requirement_id: str
    domain_hint: str
    description_pt: str
    depends_on: tuple[str, ...] = ()
    blocked_by: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["depends_on"] = list(self.depends_on)
        data["blocked_by"] = list(self.blocked_by)
        return data


EXPANSION_REQUIREMENTS: tuple[ExpansionRequirement, ...] = (
    ExpansionRequirement(
        requirement_id="ux.three_levels",
        domain_hint="entrepreneurship",
        description_pt=(
            "Renderizar DidacticMetadata nos níveis basic/intermediate/technical."
        ),
        depends_on=("presentation.DidacticMetadata",),
        blocked_by=("site não iniciado",),
    ),
    ExpansionRequirement(
        requirement_id="ux.interactive_map",
        domain_hint="shared",
        description_pt="Mapa interativo com proveniência e limitações no popup.",
        depends_on=("geoai.db.territorial_units", "presentation.DidacticMetadata"),
        blocked_by=("FastAPI/Streamlit fora do MVP 06",),
    ),
    ExpansionRequirement(
        requirement_id="quality.persist_reports",
        domain_hint="shared",
        description_pt=(
            "Migração aditiva opcional para persistir QualityReport "
            "(somente se necessário operacionalmente)."
        ),
        depends_on=("geoai.quality.QualityReport", "geoai.db"),
        blocked_by=("ainda não justificado — relatórios in-memory bastam"),
    ),
)


def list_expansion_requirements() -> tuple[ExpansionRequirement, ...]:
    return EXPANSION_REQUIREMENTS


def didactic_metadata_for_territorial_pr() -> DidacticMetadata:
    """Exemplo concreto ligado ao dataset territorial PR existente."""

    return DidacticMetadata(
        resource_id="geoai.territorial_units.pr_uf",
        copies=(
            DidacticCopy(
                level=AudienceLevel.BASIC,
                title="Mapa do Paraná",
                description=(
                    "Contorno oficial do estado usado como base dos mapas. "
                    "Não diz onde instalar energia solar."
                ),
            ),
            DidacticCopy(
                level=AudienceLevel.INTERMEDIATE,
                title="Limite territorial da UF Paraná (IBGE)",
                description=(
                    "Geometria da malha municipal/UF do IBGE, reprojetada "
                    "para SIRGAS 2000 (EPSG:4674) no banco PostGIS."
                ),
            ),
            DidacticCopy(
                level=AudienceLevel.TECHNICAL,
                title="territorial_units — PR UF / mesh_edition documentada",
                description=(
                    "Tabela geoai.territorial_units; MultiPolygon 4674; "
                    "proveniência via data_artifacts + SourceSpec "
                    "ibge.malhas_municipais.pr_uf_2025."
                ),
            ),
        ),
        unit=None,
        legend_pt="Contorno administrativo da UF",
        source_attribution_pt="IBGE — Malhas territoriais",
        updated_at="conforme edição da malha / ingestion_runs",
        uncertainty_pt=(
            "Limites administrativos mudam com novas edições IBGE; "
            "não inferir aptidão nem restrição ambiental a partir deste contorno."
        ),
        methodology_url=None,
    )
