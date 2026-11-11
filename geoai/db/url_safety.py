"""Utilitários para URLs de banco sem vazar credenciais em logs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class ParsedDatabaseUrl:
    scheme: str
    user: str | None
    password: str | None
    host: str | None
    port: int | None
    dbname: str


def parse_database_url(url: str) -> ParsedDatabaseUrl:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError(f"URL de banco não suportada: {parsed.scheme!r}")
    dbname = unquote(parsed.path.lstrip("/"))
    if not dbname:
        raise ValueError("DATABASE_URL sem nome de banco no path")
    return ParsedDatabaseUrl(
        scheme=parsed.scheme,
        user=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
        host=parsed.hostname,
        port=parsed.port,
        dbname=dbname,
    )


def redact_database_url(url: str) -> str:
    """Remove senha da URL para logs e relatórios."""
    try:
        parts = parse_database_url(url)
    except ValueError:
        return "<database-url-invalida>"
    user = parts.user or ""
    auth = f"{user}:***@" if parts.password else (f"{user}@" if user else "")
    host = parts.host or "localhost"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{auth}{host}{port}/{parts.dbname}"


def database_url_with_dbname(url: str, dbname: str) -> str:
    """Troca apenas o database name, preservando demais partes."""
    if not dbname or "/" in dbname or " " in dbname:
        raise ValueError(f"nome de banco inválido: {dbname!r}")
    parts = parse_database_url(url)
    user = parts.user or ""
    password = parts.password
    if password is not None:
        auth = f"{user}:{password}@"
    elif user:
        auth = f"{user}@"
    else:
        auth = ""
    host = parts.host or "localhost"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{auth}{host}{port}/{dbname}"
