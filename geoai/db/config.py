"""Configuração de conexão PostgreSQL (somente variáveis locais / CI)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """Parâmetros de conexão e schema de aplicação."""

    database_url: str
    schema: str = "geoai"

    @classmethod
    def from_env(cls) -> DatabaseConfig | None:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            return None
        schema = os.environ.get("GEOAI_DB_SCHEMA", "geoai").strip() or "geoai"
        return cls(database_url=url, schema=schema)


def require_database_url() -> DatabaseConfig:
    """Exige DATABASE_URL; falha com mensagem clara se ausente."""
    cfg = DatabaseConfig.from_env()
    if cfg is None:
        raise RuntimeError(
            "DATABASE_URL não definida. Use `.env.example` + Docker Compose local "
            "ou o serviço PostGIS do CI. Não use a conta Supabase remota neste MVP."
        )
    return cfg
