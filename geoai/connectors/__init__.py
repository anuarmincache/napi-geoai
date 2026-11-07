"""Adaptadores de fontes oficiais de dados geoespaciais e tabulares."""

from __future__ import annotations

from geoai.connectors.aneel import (
    ANEEL_SIGA_CSV_URL,
    download_siga_csv,
    parse_siga_csv,
    parse_siga_file,
)
from geoai.connectors.catalog import SOURCE_CATALOG, get_source, list_sources
from geoai.connectors.contracts import (
    AccessMode,
    IngestResult,
    ProvenanceRecord,
    SourceSpec,
    SourceStatus,
)
from geoai.connectors.errors import (
    CacheConnectorError,
    ConnectorError,
    NetworkConnectorError,
    ValidationConnectorError,
)
from geoai.connectors.ibge import (
    IBGE_PR_UF_2025,
    IbgeMalhaSource,
    download_ibge_zip,
)

__all__ = [
    "ANEEL_SIGA_CSV_URL",
    "AccessMode",
    "CacheConnectorError",
    "ConnectorError",
    "IBGE_PR_UF_2025",
    "IngestResult",
    "IbgeMalhaSource",
    "NetworkConnectorError",
    "ProvenanceRecord",
    "SOURCE_CATALOG",
    "SourceSpec",
    "SourceStatus",
    "ValidationConnectorError",
    "download_ibge_zip",
    "download_siga_csv",
    "get_source",
    "list_sources",
    "parse_siga_csv",
    "parse_siga_file",
]
