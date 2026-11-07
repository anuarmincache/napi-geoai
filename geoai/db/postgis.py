"""Resolução portátil do schema da extensão PostGIS (public ou extensions)."""

from __future__ import annotations

import re

_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def resolve_postgis_schema(conn) -> str:
    """
    Retorna o schema onde a extensão ``postgis`` está instalada.

    Imagens Docker costumam instalar em ``public``; Supabase prefere
    ``extensions``. A migração aceita ambos.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT n.nspname
            FROM pg_extension e
            JOIN pg_namespace n ON n.oid = e.extnamespace
            WHERE e.extname = 'postgis'
            """
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            "Extensão PostGIS não encontrada. Aplique as migrações ou "
            "CREATE EXTENSION postgis."
        )
    schema = str(row[0])
    if not _SCHEMA_NAME_RE.fullmatch(schema):
        raise RuntimeError(f"Nome de schema PostGIS inválido: {schema!r}")
    return schema


def configure_search_path(conn, *, app_schema: str = "geoai") -> str:
    """
    Define ``search_path`` da conexão: app → postgis → public.

    Retorna o schema PostGIS detectado. Identificadores vêm só do catálogo
    do servidor (não de input do usuário).
    """
    if not _SCHEMA_NAME_RE.fullmatch(app_schema):
        raise ValueError(f"schema de aplicação inválido: {app_schema!r}")
    pgis = resolve_postgis_schema(conn)
    with conn.cursor() as cur:
        cur.execute(f'SET search_path TO "{app_schema}", "{pgis}", public')
    return pgis
