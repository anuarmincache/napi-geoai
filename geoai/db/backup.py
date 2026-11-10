"""Backup (pg_dump -Fc) e restauração verificada em banco temporário isolado."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass
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
    manifest_path: Path
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
    units_fingerprint: str
    artifacts_fingerprint: str
    runs_fingerprint: str


@dataclass(frozen=True)
class RestoreVerifyResult:
    temp_db: str
    dump_path: Path
    dump_sha256: str
    reference: SnapshotMetrics
    restored: SnapshotMetrics
    match: bool
    differences: tuple[str, ...]
    reference_kind: str  # "manifest" | "live_source"


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

            # Fingerprints determinísticos (ordem fixa) — além de contagens.
            cur.execute(
                f"""
                SELECT COALESCE(
                  md5(string_agg(
                    ibge_code || '|' || mesh_edition || '|' ||
                    ST_AsText(ST_Normalize(geom)),
                    E'\\n' ORDER BY ibge_code, mesh_edition, id
                  )),
                  md5('')
                )
                FROM {cfg.schema}.territorial_units
                """
            )
            units_fp = str(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT COALESCE(
                  md5(string_agg(
                    source_id || '|' || version_label || '|' || content_sha256,
                    E'\\n' ORDER BY source_id, version_label, content_sha256, id
                  )),
                  md5('')
                )
                FROM {cfg.schema}.data_artifacts
                """
            )
            artifacts_fp = str(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT COALESCE(
                  md5(string_agg(
                    source_id || '|' || status || '|' ||
                    records_processed::text || '|' ||
                    COALESCE(error_summary, ''),
                    E'\\n' ORDER BY id
                  )),
                  md5('')
                )
                FROM {cfg.schema}.ingestion_runs
                """
            )
            runs_fp = str(cur.fetchone()[0])

    return SnapshotMetrics(
        territorial_units=units,
        data_sources=sources,
        data_artifacts=artifacts,
        ingestion_runs=runs,
        srid_4674=int(srid_ok),
        valid_geoms=int(valid_ok),
        artifact_sha_set=shas,
        migration_versions=migrations,
        units_fingerprint=units_fp,
        artifacts_fingerprint=artifacts_fp,
        runs_fingerprint=runs_fp,
    )


def snapshot_to_manifest(snapshot: SnapshotMetrics) -> dict:
    data = asdict(snapshot)
    data["artifact_sha_set"] = sorted(snapshot.artifact_sha_set)
    data["migration_versions"] = list(snapshot.migration_versions)
    return data


def snapshot_from_manifest(data: dict) -> SnapshotMetrics:
    return SnapshotMetrics(
        territorial_units=int(data["territorial_units"]),
        data_sources=int(data["data_sources"]),
        data_artifacts=int(data["data_artifacts"]),
        ingestion_runs=int(data["ingestion_runs"]),
        srid_4674=int(data["srid_4674"]),
        valid_geoms=int(data["valid_geoms"]),
        artifact_sha_set=frozenset(data.get("artifact_sha_set") or []),
        migration_versions=tuple(data.get("migration_versions") or ()),
        units_fingerprint=str(data["units_fingerprint"]),
        artifacts_fingerprint=str(data["artifacts_fingerprint"]),
        runs_fingerprint=str(data["runs_fingerprint"]),
    )


def manifest_path_for(dump_path: Path) -> Path:
    return dump_path.with_suffix(dump_path.suffix + ".manifest.json")


def write_backup_manifest(
    dump_path: Path,
    *,
    snapshot: SnapshotMetrics,
    dump_sha256: str,
    source_db: str,
    created_at: str,
) -> Path:
    path = manifest_path_for(dump_path)
    payload = {
        "format": "napi_geoai_backup_manifest_v1",
        "created_at": created_at,
        "source_db": source_db,
        "dump_path": dump_path.name,
        "dump_sha256": dump_sha256,
        "snapshot": snapshot_to_manifest(snapshot),
        "note": (
            "restore-verify compara o banco restaurado a este manifesto "
            "(estado no momento do dump), não a um snapshot live posterior."
        ),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_backup_manifest(dump_path: Path) -> dict | None:
    path = manifest_path_for(dump_path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_backup(
    cfg: DatabaseConfig,
    *,
    output_dir: Path,
    filename: str | None = None,
) -> BackupResult:
    """Gera dump custom (-Fc) + manifesto JSON acoplado."""
    parts = parse_database_url(cfg.database_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        output_dir.chmod(0o700)
    except OSError:
        pass

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = filename or f"{parts.dbname}_{stamp}.dump"
    dump_path = (output_dir / name).resolve()
    if dump_path.exists():
        raise FileExistsError(f"dump já existe: {dump_path}")

    # Snapshot ANTES do dump — referência para restore-verify via manifesto.
    snapshot = collect_snapshot(cfg)

    tool = require_pg_tool("pg_dump")
    env = {}
    if parts.password is not None:
        env["PGPASSWORD"] = parts.password
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
    manifest = write_backup_manifest(
        dump_path,
        snapshot=snapshot,
        dump_sha256=digest,
        source_db=parts.dbname,
        created_at=stamp,
    )
    return BackupResult(
        dump_path=dump_path,
        manifest_path=manifest,
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


def target_has_postgis(cfg: DatabaseConfig, dbname: str) -> bool:
    import psycopg

    url = database_url_with_dbname(cfg.database_url, dbname)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'postgis'")
            return cur.fetchone() is not None


def create_temp_database(cfg: DatabaseConfig, *, suffix: str | None = None) -> str:
    """
    Cria DB temporário apenas com prefixo ``napi_geoai_tmp_``.

    Preferência: ``TEMPLATE template_napi_postgis`` (PostGIS já habilitado).
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
    except Exception:  # noqa: BLE001
        pass


def os_getpid() -> int:
    import os

    return os.getpid()


def drop_temp_database(cfg: DatabaseConfig, name: str, *, confirm: bool) -> None:
    """Remove somente bancos ``napi_geoai_tmp_*`` (exige confirm=True)."""
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


# Objetos já materializados pela extensão PostGIS no template/alvo.
_POSTGIS_TOC_SKIP_MARKERS = (
    " EXTENSION ",
    " SPATIAL_REF_SYS",
    " GEOMETRY_COLUMNS",
    " GEOGRAPHY_COLUMNS",
)


def filter_restore_toc_exclude_extensions(toc_text: str) -> str:
    """
    Remove do TOC entradas da extensão PostGIS e tabelas/views dela.

    Usado quando o alvo já tem PostGIS (template ou CREATE prévio), para
    evitar conflito em CREATE EXTENSION / COPY spatial_ref_sys sem engolir
    outros erros do restore.
    """
    kept: list[str] = []
    for line in toc_text.splitlines():
        upper = f" {line.upper()} "
        if any(marker in upper for marker in _POSTGIS_TOC_SKIP_MARKERS):
            continue
        if "COMMENT" in upper and "EXTENSION" in upper:
            continue
        kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def restore_dump_to_database(
    cfg: DatabaseConfig,
    *,
    dump_path: Path,
    target_dbname: str,
) -> None:
    """
    Restaura dump em banco temporário já criado.

    Exige exit code 0 do ``pg_restore`` (com ``--exit-on-error``).
    Se o alvo já possui PostGIS, exclui EXTENSION do TOC antes do restore.
    """
    assert_safe_temp_dbname(target_dbname)
    if not dump_path.is_file():
        raise FileNotFoundError(dump_path)
    parts = parse_database_url(cfg.database_url)
    tool = require_pg_tool("pg_restore")
    env = {}
    if parts.password is not None:
        env["PGPASSWORD"] = parts.password

    remote_tmp: str | None = None
    list_path: Path | None = None
    remote_list: str | None = None
    try:
        if tool.via_wsl:
            from geoai.db.pg_tools import wsl_rm, wsl_write_bytes

            remote_tmp = f"/tmp/napi_restore_{target_dbname}.dump"
            wsl_write_bytes(remote_tmp, dump_path.read_bytes())
            dump_arg = remote_tmp
        else:
            dump_arg = str(dump_path)

        has_pgis = target_has_postgis(cfg, target_dbname)
        restore_args = [
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
            "--exit-on-error",
        ]

        if has_pgis:
            # Lista TOC e remove EXTENSION (já presente via template/superuser).
            list_result = run_pg_tool(
                tool, ["-l", dump_arg], env=env, check=True
            )
            toc = list_result.stdout or ""
            filtered = filter_restore_toc_exclude_extensions(toc)
            fd, tmp_name = tempfile.mkstemp(suffix=".toc.list")
            os.close(fd)
            list_path = Path(tmp_name)
            list_path.write_text(filtered, encoding="utf-8")
            try:
                list_path.chmod(0o600)
            except OSError:
                pass
            if tool.via_wsl:
                from geoai.db.pg_tools import wsl_write_bytes as _ww

                remote_list = f"/tmp/napi_restore_{target_dbname}.list"
                _ww(remote_list, list_path.read_bytes())
                restore_args.extend(["-L", remote_list])
            else:
                restore_args.extend(["-L", str(list_path)])

        restore_args.append(dump_arg)
        result = run_pg_tool(tool, restore_args, env=env, check=False)
        if result.returncode != 0:
            raw = result.stderr or result.stdout or ""
            err = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
            # Nunca incluir senha; DATABASE_URL já não está no stderr típico.
            raise RuntimeError(
                f"pg_restore falhou (exit {result.returncode}): {err.strip()[:800]}"
            )
    finally:
        if remote_tmp is not None:
            from geoai.db.pg_tools import wsl_rm

            wsl_rm(remote_tmp)
        if remote_list is not None:
            from geoai.db.pg_tools import wsl_rm

            wsl_rm(remote_list)
        if list_path is not None:
            try:
                list_path.unlink(missing_ok=True)
            except OSError:
                pass


def compare_snapshots(
    reference: SnapshotMetrics, restored: SnapshotMetrics
) -> list[str]:
    differences: list[str] = []
    fields = [
        ("territorial_units", reference.territorial_units, restored.territorial_units),
        ("data_sources", reference.data_sources, restored.data_sources),
        ("data_artifacts", reference.data_artifacts, restored.data_artifacts),
        ("ingestion_runs", reference.ingestion_runs, restored.ingestion_runs),
        ("srid_4674", reference.srid_4674, restored.srid_4674),
        ("valid_geoms", reference.valid_geoms, restored.valid_geoms),
        (
            "units_fingerprint",
            reference.units_fingerprint,
            restored.units_fingerprint,
        ),
        (
            "artifacts_fingerprint",
            reference.artifacts_fingerprint,
            restored.artifacts_fingerprint,
        ),
        (
            "runs_fingerprint",
            reference.runs_fingerprint,
            restored.runs_fingerprint,
        ),
    ]
    for name, left, right in fields:
        if left != right:
            differences.append(f"{name} {right!r}!={left!r}")
    if restored.artifact_sha_set != reference.artifact_sha_set:
        differences.append("artifact_sha_set diverge")
    if restored.migration_versions != reference.migration_versions:
        differences.append("schema_migrations diverge")
    return differences


def verify_restore(
    cfg: DatabaseConfig,
    *,
    dump_path: Path,
    keep_temp: bool = False,
    temp_suffix: str | None = None,
) -> RestoreVerifyResult:
    """
    Restaura dump em DB temporário, compara com manifesto (ou live) e limpa temp.

    Preferência de referência: ``*.dump.manifest.json`` gerado no backup.
    Sem manifesto, cai no snapshot live atual e registra ``reference_kind``.
    Nunca altera ``napi_geoai`` além de leitura; drop só de ``napi_geoai_tmp_*``.
    """
    digest = sha256_file(dump_path)
    manifest = load_backup_manifest(dump_path)
    if manifest is not None:
        expected_sha = manifest.get("dump_sha256")
        if expected_sha and expected_sha != digest:
            raise RuntimeError(
                "SHA-256 do dump diverge do manifesto acoplado — "
                f"arquivo={digest} manifesto={expected_sha}"
            )
        reference = snapshot_from_manifest(manifest["snapshot"])
        reference_kind = "manifest"
    else:
        reference = collect_snapshot(cfg)
        reference_kind = "live_source"

    temp_db: str | None = None
    try:
        temp_db = create_temp_database(cfg, suffix=temp_suffix)
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
                    "(senha sudo; script idempotente). No CI a role superuser "
                    "cria a extensão automaticamente."
                ) from exc
            raise
        differences = compare_snapshots(reference, restored)
        return RestoreVerifyResult(
            temp_db=temp_db,
            dump_path=dump_path,
            dump_sha256=digest,
            reference=reference,
            restored=restored,
            match=not differences,
            differences=tuple(differences),
            reference_kind=reference_kind,
        )
    finally:
        if temp_db is not None and not keep_temp:
            drop_temp_database(cfg, temp_db, confirm=True)


def summarize_restore(
    result: RestoreVerifyResult, *, primary_url: str | None = None
) -> dict:
    def _snap(s: SnapshotMetrics) -> dict:
        return {
            "territorial_units": s.territorial_units,
            "data_sources": s.data_sources,
            "data_artifacts": s.data_artifacts,
            "ingestion_runs": s.ingestion_runs,
            "srid_4674": s.srid_4674,
            "valid_geoms": s.valid_geoms,
            "units_fingerprint": s.units_fingerprint,
            "artifacts_fingerprint": s.artifacts_fingerprint,
            "runs_fingerprint": s.runs_fingerprint,
            "migrations": list(s.migration_versions),
        }

    payload = {
        "temp_db": result.temp_db,
        "dump_path": str(result.dump_path),
        "dump_sha256": result.dump_sha256,
        "match": result.match,
        "reference_kind": result.reference_kind,
        "differences": list(result.differences),
        "reference": _snap(result.reference),
        "restored": _snap(result.restored),
    }
    if primary_url:
        payload["primary_url"] = redact_database_url(primary_url)
    return payload
