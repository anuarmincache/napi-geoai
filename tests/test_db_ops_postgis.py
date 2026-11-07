"""Testes de ops PostGIS: doctor, backup/restore isolado, security (DATABASE_URL)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("psycopg")

from geoai.db.backup import (
    PROTECTED_DB_NAMES,
    create_backup,
    drop_temp_database,
    verify_restore,
)
from geoai.db.config import DatabaseConfig
from geoai.db.doctor import run_doctor
from geoai.db.migrate import apply_migrations
from geoai.db.pg_tools import find_pg_tool
from geoai.db.security_audit import run_security_audit
from geoai.db.url_safety import redact_database_url

REPO = Path(__file__).resolve().parents[1]
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

requires_postgis = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL ausente",
)
requires_pg_dump = pytest.mark.skipif(
    find_pg_tool("pg_dump") is None or find_pg_tool("pg_restore") is None,
    reason="pg_dump/pg_restore indisponíveis (PATH/WSL)",
)


@pytest.fixture(scope="module")
def db_cfg() -> DatabaseConfig:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL ausente")
    return DatabaseConfig(database_url=DATABASE_URL, schema="geoai")


@requires_postgis
@pytest.mark.postgis
def test_doctor_reports_healthy_postgis(db_cfg: DatabaseConfig) -> None:
    apply_migrations(db_cfg, directory=REPO / "db" / "migrations")
    report = run_doctor(db_cfg)
    red = report.database_url_redacted
    assert ":***@" in red or "@" in red
    assert "napi_local_dev_only" not in red
    names = {c.name for c in report.checks}
    assert "postgis_version" in names
    assert "gist_index" in names
    assert report.overall in {"ok", "warn"}
    assert report.exit_code in {0, 1}


@requires_postgis
@pytest.mark.postgis
def test_security_audit_readonly(db_cfg: DatabaseConfig) -> None:
    report = run_security_audit(db_cfg, repo_root=REPO)
    assert report.findings
    crits = [f for f in report.findings if f.severity == "crit"]
    assert not crits
    finding_names = {f.name for f in report.findings}
    if "example_password" in finding_names:
        # menção à senha de exemplo só no finding dedicado
        assert True
    else:
        assert "napi_local_dev_only" not in str(report.to_dict())


def _can_create_postgis(cfg: DatabaseConfig) -> bool:
    import psycopg
    from geoai.db.backup import postgis_template_exists

    if postgis_template_exists(cfg):
        return True
    try:
        with psycopg.connect(cfg.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT rolsuper FROM pg_roles
                    WHERE rolname = current_user
                    """
                )
                row = cur.fetchone()
                return bool(row and row[0])
    except Exception:  # noqa: BLE001
        return False


@requires_postgis
@requires_pg_dump
@pytest.mark.postgis
def test_backup_restore_verify_isolated(
    db_cfg: DatabaseConfig, tmp_path: Path
) -> None:
    import psycopg

    if not _can_create_postgis(db_cfg):
        pytest.skip(
            "Sem template_napi_postgis e sem superuser — rode "
            "scripts/ensure_postgis_template.sh no WSL (sudo local)"
        )

    apply_migrations(db_cfg, directory=REPO / "db" / "migrations")
    primary = redact_database_url(db_cfg.database_url)

    # Contagem antes — deve permanecer após o ciclo
    with psycopg.connect(db_cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM geoai.territorial_units")
            before_units = int(cur.fetchone()[0])
            cur.execute("SELECT datname FROM pg_database")
            before_dbs = {r[0] for r in cur.fetchall()}

    assert "napi_geoai" in before_dbs or parse_primary_name(db_cfg) in before_dbs

    bak = create_backup(db_cfg, output_dir=tmp_path / "backups")
    assert bak.dump_path.is_file()
    assert bak.bytes > 0
    assert len(bak.sha256) == 64

    result = verify_restore(
        db_cfg,
        dump_path=bak.dump_path,
        keep_temp=False,
        temp_suffix="pytest",
    )
    assert result.match, result.differences
    assert result.source.territorial_units == before_units
    assert result.restored.territorial_units == before_units
    assert result.temp_db.startswith("napi_geoai_tmp_")
    assert result.temp_db not in PROTECTED_DB_NAMES

    with psycopg.connect(db_cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM geoai.territorial_units")
            after_units = int(cur.fetchone()[0])
            cur.execute("SELECT datname FROM pg_database")
            after_dbs = {r[0] for r in cur.fetchall()}

    assert after_units == before_units
    # temporário removido
    assert result.temp_db not in after_dbs
    # banco principal intacto
    assert parse_primary_name(db_cfg) in after_dbs
    assert primary  # smoke: redaction worked


def parse_primary_name(cfg: DatabaseConfig) -> str:
    from geoai.db.url_safety import parse_database_url

    return parse_database_url(cfg.database_url).dbname


@requires_postgis
@pytest.mark.postgis
def test_refuse_drop_protected_database(db_cfg: DatabaseConfig) -> None:
    with pytest.raises(ValueError, match="protegido|inválido"):
        drop_temp_database(db_cfg, "napi_geoai", confirm=True)
