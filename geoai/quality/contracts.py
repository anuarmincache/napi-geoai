"""Contratos de qualidade e schema de datasets (MVP 06).

Desacoplados de domínio e de UI. Complementam ``ProvenanceRecord`` /
``SourceSpec`` do MVP 03 — não os substituem.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class QualityStatus(StrEnum):
    """Resultado agregado de uma avaliação de qualidade."""

    VALID = "valid"
    WARNING = "warning"
    REJECTED = "rejected"


class GeometryKind(StrEnum):
    """Tipo geométrico esperado (quando aplicável)."""

    NONE = "none"
    POINT = "point"
    LINESTRING = "linestring"
    POLYGON = "polygon"
    MULTIPOLYGON = "multipolygon"
    RASTER = "raster"
    TABULAR = "tabular"


class EnergyQuantityKind(StrEnum):
    """Grandezas energéticas tipadas **por campo/indicador**.

    Um dataset tabular **pode** ter colunas distintas (ex.: potência em kW e
    geração em MWh) desde que cada coluna declare ``energy_quantity`` +
    unidade canônica. Não combinar grandezas distintas no *mesmo* campo nem
    em um único indicador sem tipagem explícita.

    Unidades canônicas: ver ``CANONICAL_ENERGY_UNITS``.
    """

    NOT_APPLICABLE = "not_applicable"
    INSTALLED_CAPACITY_KW = "installed_capacity_kw"
    GENERATION_MWH = "generation_mwh"
    IRRADIANCE_KWH_M2 = "irradiance_kwh_m2"
    OTHER = "other"


# Unidades aceitas por grandeza (comparação case-sensitive nas formas listadas).
CANONICAL_ENERGY_UNITS: dict[EnergyQuantityKind, frozenset[str]] = {
    EnergyQuantityKind.INSTALLED_CAPACITY_KW: frozenset({"kW"}),
    EnergyQuantityKind.GENERATION_MWH: frozenset({"MWh"}),
    EnergyQuantityKind.IRRADIANCE_KWH_M2: frozenset({"kWh/m²", "kWh/m2"}),
}


@dataclass(frozen=True, slots=True)
class FieldConstraint:
    """Restrição testável sobre um campo tabular/atributo."""

    name: str
    required: bool = True
    unit: str | None = None
    nullable: bool = False
    energy_quantity: EnergyQuantityKind = EnergyQuantityKind.NOT_APPLICABLE
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: tuple[str, ...] | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["energy_quantity"] = self.energy_quantity.value
        data["allowed_values"] = (
            list(self.allowed_values) if self.allowed_values is not None else None
        )
        return data


@dataclass(frozen=True, slots=True)
class DatasetSchema:
    """Schema explícito de um dataset tabular/espacial.

    Piloto MVP 06: descreve o recorte territorial PR já persistido
    (sem inventar atributos publicados).
    """

    dataset_id: str
    source_id: str
    title: str
    geometry_kind: GeometryKind
    crs: str
    spatial_resolution: str
    temporal_periodicity: str
    edition: str
    license_note: str
    update_policy: str
    fields: tuple[FieldConstraint, ...]
    integrity_notes: str = ""
    content_sha256_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["geometry_kind"] = self.geometry_kind.value
        data["fields"] = [f.to_dict() for f in self.fields]
        return data


@dataclass(frozen=True, slots=True)
class QualityFinding:
    """Achado individual de validação (campo ou dataset)."""

    code: str
    message: str
    severity: QualityStatus
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Relatório de qualidade por fonte/dataset.

    Pronto para persistência futura (migração aditiva) sem exigir
    alteração de schema neste MVP.
    """

    dataset_id: str
    source_id: str
    status: QualityStatus
    version_label: str
    collected_at: str
    limitations: tuple[str, ...] = ()
    findings: tuple[QualityFinding, ...] = ()
    content_sha256: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["limitations"] = list(self.limitations)
        payload["findings"] = [f.to_dict() for f in self.findings]
        return payload
