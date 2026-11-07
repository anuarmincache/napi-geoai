"""Contratos de metadados, proveniência e resultado de ingestão.

Nesta fase os contratos descrevem *como* obter e validar dados oficiais.
Não incluem cálculos de aptidão solar nem publicação web.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class AccessMode(StrEnum):
    """Mecanismo real de acesso (não pressupõe REST para todas as fontes)."""

    HTTP_FILE = "http_file"
    CKAN_RESOURCE = "ckan_resource"
    FTP_OR_HTTP_INDEX = "ftp_or_http_index"
    GEE_ASSET = "gee_asset"
    WEB_PLATFORM = "web_platform"
    ARCGIS_REST = "arcgis_rest"
    MANUAL = "manual"


class SourceStatus(StrEnum):
    """Maturidade do conector no repositório."""

    CATALOGUED = "catalogued"
    PROTOTYPE = "prototype"
    STABLE = "stable"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Especificação auditável de uma fonte oficial."""

    source_id: str
    organization: str
    product: str
    access_mode: AccessMode
    entry_url: str
    download_url: str | None
    formats: tuple[str, ...]
    license_note: str
    update_cadence: str
    spatial_coverage: str
    crs_or_coords: str
    granularity: str
    auth_required: bool
    status: SourceStatus
    notes: str = ""
    connector_module: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["access_mode"] = self.access_mode.value
        data["status"] = self.status.value
        data["formats"] = list(self.formats)
        return data


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Metadados obrigatórios de proveniência de um artefato baixado."""

    source_id: str
    url: str
    retrieved_at: str
    content_sha256: str
    content_length: int
    http_etag: str | None = None
    http_last_modified: str | None = None
    license_note: str = ""
    local_path: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Resultado de uma ingestão bem-sucedida (arquivo local + proveniência)."""

    source_id: str
    local_path: str
    provenance: ProvenanceRecord
    records_parsed: int | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


REQUIRED_PROVENANCE_FIELDS: tuple[str, ...] = (
    "source_id",
    "url",
    "retrieved_at",
    "content_sha256",
    "content_length",
    "license_note",
)
