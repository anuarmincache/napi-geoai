"""Backup (pg_dump -Fc) e restauração verificada em banco temporário isolado."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from geoai.db.config import DatabaseConfig
from geoai.db.pg_tools import require_pg_tool, run_pg_tool
from geoai.db.postgis import configure_search_path
from geoai.db.url_safety import (
    database_url_with_dbname,
    parse_database_url,
    redact_database_url,
)

PROTECTED_DB_NAMES = frozenset(
    {
        "napi_geoai",
        "postgres",
        "template0",
        "template1",
        "template_napi_postgis",
    }
)
TEMP_DB_PREFIX = "napi_geoai_tmp_"
TEMP_DB_RE = re.compile(r"^napi_geoai_tmp_[a-z0-9_]+$")
POSTGIS_TEMPLATE = "template_napi_postgis"


@dataclass(frozen=True)
class BackupResult:
    dump_path: Path
    sha256: str
    bytes: int
    source_db: str
    created_at: str


@dataclass(frozen=True)
class SnapshotMetrics:
    territorial_units: int
    data_sources: int
    data_artifacts: int
    ingestion_runs: int
    srid_4674: int
    valid_geoms: int
    artifact_sha_set: frozenset[str]
    migration_versions: tuple[str, ...]


@dataclass(frozen=True)
class RestoreVerifyResult:
    temp_db: str
    dump_path: Path
    dump_sha256: str
    source: SnapshotMetrics
    restored: SnapshotMetrics
    match: bool
    differences: tuple[str, ...]


def assert_safe_temp_dbname(name: str) -> None:
    if name in PROTECTED_DB_NAMES:
        raise ValueError(f"banco protegido — operação recusada: {name}")
    if not TEMP_DB_RE.fullmatch(name):
        raise ValueError(
            f"nome temporário inválido: {name!r}. "
            f"Use prefixo {TEMP_DB_PREFIX} e apenas [a-z0-9_]."
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_snapshot(cfg: DatabaseConfig) -> SnapshotMetrics:
    import psycopg

    with psycopg.connect(cfg.database_url) as conn:
        configure_search_path(conn, app_schema=cfg.schema)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {cfg.schema}.territorial_units")
            units = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE ST_SRID(geom) = 4674),
                  COUNT(*) FILTER (WHERE ST_IsValid(geom))
                FROM {cfg.schema}.territorial_units
                """
            )
            srid_ok, valid_ok = cur.fetchone()
            cur.execute(f"SELECT COUNT(*) FROM {cfg.schema}.data_sources")
            sources = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*) FROM {cfg.schema}.data_artifacts")
            artifacts = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*) FROM {cfg.schema}.ingestion_runs")
            runs = int(cur.fetchone()[0])
            cur.execute(
                f"SELECT content_sha256 FROM {cfg.schema}.data_artifacts ORDER BY 1"
            )
            shas = frozenset(r[0] for r in cur.fetchall())
            cur.execute(
                f"SELECT version FROM {cfg.schema}.schema_migrations ORDER BY version"
            )
            migrations = tuple(r[0] for r in cur.fetchall())
    return SnapshotMetrics(
        territorial_units=units,
        data_sources=sources,
        data_artifacts=artifacts,
        ingestion_runs=runs,
        srid_4674=int(srid_ok),
        valid_geoms=int(valid_ok),
        artifact_sha_set=shas,
        migration_versions=migrations,
    )


def create_backup(
    cfg: DatabaseConfig,
    *,
    output_dir: Path,
    filename: str | None = None,
) -> BackupResult:
    """Gera dump custom (-Fc) do banco apontado por DATABASE_URL."""
    parts = parse_database_url(cfg.database_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Restringe permissões no diretório de backups quando o SO permitir
    try:
        output_dir.chmod(0o700)
    except OSError:
        pass

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = filename or f"{parts.dbname}_{stamp}.dump"
    dump_path = (output_dir / name).resolve()
    if dump_path.exists():
        raise FileExistsError(f"dump já existe: {dump_path}")

    tool = require_pg_tool("pg_dump")
    env = {}
    if parts.password is not None:
        env["PGPASSWORD"] = parts.password
    # Via WSL: grava em /tmp (evita travar em /mnt/c OneDrive) e copia.
    remote_tmp: str | None = None
    if tool.via_wsl:
        from geoai.db.pg_tools import wsl_read_bytes, wsl_rm

        remote_tmp = f"/tmp/napi_geoai_{stamp}.dump"
        dump_arg = remote_tmp
    else:
        dump_arg = str(dump_path)
    args = [
        "-h",
        parts.host or "127.0.0.1",
        "-p",
        str(parts.port or 5432),
        "-U",
        parts.user or "napi",
        "-d",
        parts.dbname,
        "-Fc",
        "-f",
        dump_arg,
    ]
    try:
        run_pg_tool(tool, args, env=env)
        if remote_tmp is not None:
            dump_path.write_bytes(wsl_read_bytes(remote_tmp))
    finally:
        if remote_tmp is not None:
            wsl_rm(remote_tmp)
    try:
        dump_path.chmod(0o600)
    except OSError:
        pass
    digest = sha256_file(dump_path)
    return BackupResult(
        dump_path=dump_path,
        sha256=digest,
        bytes=dump_path.stat().st_size,
        source_db=parts.dbname,
        created_at=stamp,
    )


def _connect_admin(cfg: DatabaseConfig):
    """Conecta ao DB 'postgres' no mesmo servidor para CREATE/DROP DATABASE."""
    import psycopg

    admin_url = database_url_with_dbname(cfg.database_url, "postgres")
    return psycopg.connect(admin_url, autocommit=True)


def postgis_template_exists(cfg: DatabaseConfig) -> bool:
    import psycopg

    with psycopg.connect(cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (POSTGIS_TEMPLATE,),
            )
            return cur.fetchone() is not None


def create_temp_database(cfg: DatabaseConfig, *, suffix: str | None = None) -> str:
    """
    Cria DB temporário.

    Preferência: ``TEMPLATE template_napi_postgis`` (PostGIS já habilitado),
    porque a role ``napi`` normalmente não pode ``CREATE EXTENSION``.
    Em CI (role superuser), cria DB vazio e a extensão vem no pg_restore.
    """
    tag = suffix or f"{int(time.time())}_{os_getpid()}"
    tag = re.sub(r"[^a-z0-9_]", "_", tag.lower())
    name = f"{TEMP_DB_PREFIX}{tag}"[:63]
    assert_safe_temp_dbname(name)
    parts = parse_database_url(cfg.database_url)
    owner = parts.user or "napi"
    use_template = postgis_template_exists(cfg)
    with _connect_admin(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            if cur.fetchone():
                raise RuntimeError(f"banco temporário já existe: {name}")
            if use_template:
                cur.execute(
                    f'CREATE DATABASE "{name}" OWNER "{owner}" '
                    f'TEMPLATE "{POSTGIS_TEMPLATE}"'
                )
            else:
                cur.execute(f'CREATE DATABASE "{name}" OWNER "{owner}"')
                # Superuser (ex.: CI): habilita PostGIS antes do restore.
                try:
                    cur.execute(f'GRANT ALL ON DATABASE "{name}" TO "{owner}"')
                except Exception:  # noqa: BLE001
                    pass
    if not use_template:
        _try_create_postgis_on(cfg, name)
    return name


def _try_create_postgis_on(cfg: DatabaseConfig, dbname: str) -> None:
    """Tenta CREATE EXTENSION (funciona se a role for superuser, ex. CI)."""
    import psycopg

    url = database_url_with_dbname(cfg.database_url, dbname)
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    except Exception:  # noqa: BLE001 — template ou restore cuidará disso
        pass


def os_getpid() -> int:
    import os

    return os.getpid()


def drop_temp_database(cfg: DatabaseConfig, name: str, *, confirm: bool) -> None:
    assert_safe_temp_dbname(name)
    if not confirm:
        raise RuntimeError("drop de banco temporário exige confirm=True")
    with _connect_admin(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{name}"')


def restore_dump_to_database(
    cfg: DatabaseConfig,
    *,
    dump_path: Path,
    target_dbname: str,
) -> None:
    """Restaura dump em banco já criado. Recusa bancos protegidos."""
    assert_safe_temp_dbname(target_dbname)
    if not dump_path.is_file():
        raise FileNotFoundError(dump_path)
    parts = parse_database_url(cfg.database_url)
    tool = require_pg_tool("pg_restore")
    env = {}
    if parts.password is not None:
        env["PGPASSWORD"] = parts.password
    remote_tmp: str | None = None
    if tool.via_wsl:
        from geoai.db.pg_tools import wsl_rm, wsl_write_bytes

        remote_tmp = f"/tmp/napi_restore_{target_dbname}.dump"
        wsl_write_bytes(remote_tmp, dump_path.read_bytes())
        dump_arg = remote_tmp
    else:
        dump_arg = str(dump_path)
    # Sem --clean: banco temporário deve estar vazio.
    args = [
        "-h",
        parts.host or "127.0.0.1",
        "-p",
        str(parts.port or 5432),
        "-U",
        parts.user or "napi",
        "-d",
        target_dbname,
        "--no-owner",
        "--role",
        parts.user or "napi",
        dump_arg,
    ]
    try:
        # pg_restore pode retornar 1 com warnings; falhar só se >1
        result = run_pg_tool(tool, args, env=env, check=False)
        if result.returncode > 1:
            raw = result.stderr or result.stdout or ""
            err = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
            raise RuntimeError(f"pg_restore falhou: {err.strip()[:500]}")
    finally:
        if remote_tmp is not None:
            wsl_rm(remote_tmp)


def verify_restore(
    cfg: DatabaseConfig,
    *,
    dump_path: Path,
    keep_temp: bool = False,
    temp_suffix: str | None = None,
) -> RestoreVerifyResult:
    """
    Backup metrics da origem → restore em DB temporário → compara → drop temp.

    Nunca altera o banco principal além de leitura.
    """
    source = collect_snapshot(cfg)
    digest = sha256_file(dump_path)
    temp_db = create_temp_database(cfg, suffix=temp_suffix)
    differences: list[str] = []
    try:
        restore_dump_to_database(cfg, dump_path=dump_path, target_dbname=temp_db)
        restored_cfg = DatabaseConfig(
            database_url=database_url_with_dbname(cfg.database_url, temp_db),
            schema=cfg.schema,
        )
        try:
            restored = collect_snapshot(restored_cfg)
        except RuntimeError as exc:
            if "PostGIS" in str(exc):
                raise RuntimeError(
                    "PostGIS ausente no banco temporário. No WSL nativo execute "
                    "uma vez: bash scripts/ensure_postgis_template.sh "
                    "(senha sudo no terminal). No CI a role superuser cria a "
                    "extensão automaticamente."
                ) from exc
            raise
        if restored.territorial_units != source.territorial_units:
            differences.append(
                "territorial_units "
                f"{restored.territorial_units}!={source.territorial_units}"
            )
        if restored.data_sources != source.data_sources:
            differences.append("data_sources diverge")
        if restored.data_artifacts != source.data_artifacts:
            differences.append("data_artifacts diverge")
        if restored.srid_4674 != source.srid_4674:
            differences.append("srid_4674 diverge")
        if restored.valid_geoms != source.valid_geoms:
            differences.append("valid_geoms diverge")
        if restored.artifact_sha_set != source.artifact_sha_set:
            differences.append("artifact_sha_set diverge")
        if restored.migration_versions != source.migration_versions:
            differences.append("schema_migrations diverge")
        match = not differences
        return RestoreVerifyResult(
            temp_db=temp_db,
            dump_path=dump_path,
            dump_sha256=digest,
            source=source,
            restored=restored,
            match=match,
            differences=tuple(differences),
        )
    finally:
        if not keep_temp:
            drop_temp_database(cfg, temp_db, confirm=True)


def summarize_restore(
    result: RestoreVerifyResult, *, primary_url: str | None = None
) -> dict:
    payload = {
        "temp_db": result.temp_db,
        "dump_path": str(result.dump_path),
        "dump_sha256": result.dump_sha256,
        "match": result.match,
        "differences": list(result.differences),
        "source": {
            "territorial_units": result.source.territorial_units,
            "data_sources": result.source.data_sources,
            "data_artifacts": result.source.data_artifacts,
            "srid_4674": result.source.srid_4674,
            "valid_geoms": result.source.valid_geoms,
            "migrations": list(result.source.migration_versions),
        },
        "restored": {
            "territorial_units": result.restored.territorial_units,
            "data_sources": result.restored.data_sources,
            "data_artifacts": result.restored.data_artifacts,
            "srid_4674": result.restored.srid_4674,
            "valid_geoms": result.restored.valid_geoms,
            "migrations": list(result.restored.migration_versions),
        },
    }
    if primary_url:
        payload["primary_url"] = redact_database_url(primary_url)
    return payload
