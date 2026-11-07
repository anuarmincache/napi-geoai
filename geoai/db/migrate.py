"""Aplicador de migrações SQL versionadas em db/migrations/."""

from __future__ import annotations

import re
from pathlib import Path

from geoai.db.config import DatabaseConfig

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"
VERSION_RE = re.compile(r"^(\d{4}_[a-z0-9_]+)\.sql$", re.IGNORECASE)


def discovery_migrations(directory: Path | None = None) -> list[tuple[str, Path]]:
    """Lista (version, path) ordenados pelo prefixo numérico do arquivo."""
    root = directory or MIGRATIONS_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"Diretório de migrações ausente: {root}")
    found: list[tuple[str, Path]] = []
    for path in sorted(root.glob("*.sql")):
        match = VERSION_RE.match(path.name)
        if not match:
            raise ValueError(
                f"Nome de migração inválido: {path.name}. "
                "Use NNNN_descricao.sql (ex.: 0001_init_postgis.sql)."
            )
        found.append((match.group(1), path))
    return found


def list_pending_migrations(
    conn,
    *,
    directory: Path | None = None,
    schema: str = "geoai",
) -> list[tuple[str, Path]]:
    """Retorna migrações ainda não registradas em schema_migrations."""
    all_migs = discovery_migrations(directory)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'schema_migrations'
            )
            """,
            (schema,),
        )
        exists = bool(cur.fetchone()[0])
        applied: set[str] = set()
        if exists:
            cur.execute(f"SELECT version FROM {schema}.schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
    return [(v, p) for v, p in all_migs if v not in applied]


def apply_migrations(
    cfg: DatabaseConfig, *, directory: Path | None = None
) -> list[str]:
    """
    Aplica migrações pendentes em ordem.

    Cada arquivo SQL deve ser autônomo (pode conter BEGIN/COMMIT).
    Retorna a lista de versões aplicadas nesta execução.
    """
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - ambiente sem extra [db]
        raise RuntimeError(
            "Pacote psycopg não instalado. Execute: pip install -e '.[db]'"
        ) from exc

    applied_now: list[str] = []
    with psycopg.connect(cfg.database_url, autocommit=True) as conn:
        pending = list_pending_migrations(conn, directory=directory, schema=cfg.schema)
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            applied_now.append(version)
            # Re-checa registro (migração 0001 cria a tabela e já insere a si mesma)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {cfg.schema}.schema_migrations (version, description)
                    VALUES (%s, %s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (version, path.name),
                )
    return applied_now
