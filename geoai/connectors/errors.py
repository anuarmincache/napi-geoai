"""Erros padronizados de ingestão de fontes oficiais."""

from __future__ import annotations


class ConnectorError(Exception):
    """Erro base dos conectores NAPI GeoAI."""


class NetworkConnectorError(ConnectorError):
    """Falha de rede, timeout ou HTTP não recuperável."""


class ValidationConnectorError(ConnectorError):
    """Payload inválido, schema incompleto ou checksum divergente."""


class CacheConnectorError(ConnectorError):
    """Falha ao ler/gravar cache local de artefatos."""
