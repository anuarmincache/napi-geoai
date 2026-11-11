"""Contratos de metadados didáticos e requisitos de expansão (sem UI).

Suportam UX futura em 3 níveis (básico / intermediário / técnico),
mapa interativo e acessibilidade — apenas como especificação.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
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

    ``updated_at``: ISO-8601 quando conhecido; ``None`` até apuração.
    ``update_policy``: nota textual de como/quando atualizar (não é data).
    """

    resource_id: str
    copies: tuple[DidacticCopy, ...]
    unit: str | None
    legend_pt: str
    source_attribution_pt: str
    updated_at: str | None
    uncertainty_pt: str
    update_policy: str = ""
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


def _default_repo_root() -> Path:
    # geoai/presentation/contracts.py → repo root
    return Path(__file__).resolve().parents[2]


def didactic_metadata_for_territorial_pr(
    *,
    updated_at: str | None = None,
    edition: str | None = None,
    repo_root: Path | None = None,
) -> DidacticMetadata:
    """Metadados didáticos do limite PR; datas vêm da proveniência real se houver.

    Não afirma reprojeção: a malha IBGE do piloto já está em EPSG:4674
    (validação MVP 02).
    """

    root = repo_root or _default_repo_root()
    prov_path = root / "data" / "derived" / "parana_uf_2025.provenance.json"
    resolved_updated = updated_at
    resolved_edition = edition
    if prov_path.is_file():
        payload = json.loads(prov_path.read_text(encoding="utf-8"))
        if resolved_updated is None:
            raw = payload.get("retrieved_at")
            resolved_updated = str(raw) if raw else None
        if resolved_edition is None:
            raw_ed = payload.get("edition")
            resolved_edition = str(raw_ed) if raw_ed else None

    edition_note = resolved_edition or "edição da malha IBGE documentada"
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
                    "Geometria da malha municipal/UF do IBGE já referenciada "
                    "em SIRGAS 2000 (EPSG:4674), conforme validação do artefato; "
                    "persistida no PostGIS sem afirmar reprojeção adicional."
                ),
            ),
            DidacticCopy(
                level=AudienceLevel.TECHNICAL,
                title="territorial_units — PR UF / mesh_edition documentada",
                description=(
                    "Tabela geoai.territorial_units; MultiPolygon 4674; "
                    "proveniência via data_artifacts + SourceSpec "
                    "ibge.malhas_municipais.pr_uf_2025; "
                    f"edição consultada: {edition_note}."
                ),
            ),
        ),
        unit=None,
        legend_pt="Contorno administrativo da UF",
        source_attribution_pt="IBGE — Malhas territoriais",
        updated_at=resolved_updated,
        update_policy=(
            "Atualizar quando houver nova edição da malha IBGE; "
            "consultar ingestion_runs / data_artifacts para carimbo operacional."
        ),
        uncertainty_pt=(
            "Limites administrativos mudam com novas edições IBGE; "
            "não inferir aptidão nem restrição ambiental a partir deste contorno."
        ),
        methodology_url=None,
        extra={
            "edition": resolved_edition,
            "provenance_path": (
                str(prov_path.as_posix()) if prov_path.is_file() else None
            ),
        },
    )
