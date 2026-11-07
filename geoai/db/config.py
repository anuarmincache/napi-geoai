"""Configuração de conexão PostgreSQL (somente variáveis locais / CI)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv_file(path: Path | None = None) -> Path | None:
    """
    Carrega pares KEY=VALUE de um arquivo ``.env`` em ``os.environ``.

    Não sobrescreve variáveis já definidas no ambiente. Retorna o caminho
    lido ou ``None`` se o arquivo não existir. Copiar ``.env.example`` para
    ``.env`` **não** basta sozinho: é preciso chamar esta função (via
    scripts/importador) ou exportar ``DATABASE_URL`` no shell.
    """
    env_path = path or Path.cwd() / ".env"
    if not env_path.is_file():
        # fallback: raiz do repositório (dois níveis acima de geoai/db/)
        repo_env = Path(__file__).resolve().parents[2] / ".env"
        if repo_env.is_file():
            env_path = repo_env
        else:
            return None

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


@dataclass(frozen=True)
class DatabaseConfig:
    """Parâmetros de conexão e schema de aplicação."""

    database_url: str
    schema: str = "geoai"

    @classmethod
    def from_env(cls, *, load_dotenv: bool = True) -> DatabaseConfig | None:
        if load_dotenv:
            load_dotenv_file()
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            return None
        schema = os.environ.get("GEOAI_DB_SCHEMA", "geoai").strip() or "geoai"
        return cls(database_url=url, schema=schema)


def require_database_url(*, load_dotenv: bool = True) -> DatabaseConfig:
    """Exige DATABASE_URL; falha com mensagem clara se ausente."""
    cfg = DatabaseConfig.from_env(load_dotenv=load_dotenv)
    if cfg is None:
        raise RuntimeError(
            "DATABASE_URL não definida. Exporte no shell, defina no CI, ou crie "
            "`.env` a partir de `.env.example` e execute via scripts que chamam "
            "load_dotenv_file(). Não use a conta Supabase remota neste MVP."
        )
    return cfg
