"""Adaptadores de fontes oficiais de dados geoespaciais."""

from __future__ import annotations

from geoai.connectors.ibge import IBGE_PR_UF_2025, IbgeMalhaSource, download_ibge_zip

__all__ = ["IBGE_PR_UF_2025", "IbgeMalhaSource", "download_ibge_zip"]
