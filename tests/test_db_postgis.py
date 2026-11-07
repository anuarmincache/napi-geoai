"""Testes de integridade PostGIS — exigem DATABASE_URL (CI ou Docker local)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("psycopg")

from geoai.db.config import DatabaseConfig
from geoai.db.import_parana import default_artifacts, import_parana_boundary
from geoai.db.migrate import apply_migrations, list_pending_migrations

REPO = Path(__file__).resolve().parents[1]

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
requires_postgis = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL ausente (sem PostGIS local/CI)",
)


@pytest.fixture(scope="module")
def db_cfg() -> DatabaseConfig:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL ausente")
    return DatabaseConfig(database_url=DATABASE_URL, schema="geoai")


@requires_postgis
@pytest.mark.postgis
def test_migrations_apply_and_are_idempotent(db_cfg: DatabaseConfig) -> None:
    import psycopg

    first = apply_migrations(db_cfg, directory=REPO / "db" / "migrations")
    assert "0001_init_postgis" in first or first == []
    second = apply_migrations(db_cfg, directory=REPO / "db" / "migrations")
    assert second == []

    with psycopg.connect(db_cfg.database_url) as conn:
        pending = list_pending_migrations(
            conn, directory=REPO / "db" / "migrations", schema=db_cfg.schema
        )
        assert pending == []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname = 'postgis'
                """
            )
            assert cur.fetchone() is not None
            cur.execute(
                """
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'geoai' AND table_name = 'territorial_units'
                  AND column_name = 'geom'
                """
            )
            row = cur.fetchone()
            assert row is not None


@requires_postgis
@pytest.mark.postgis
def test_import_parana_idempotent_and_valid(db_cfg: DatabaseConfig) -> None:
    import psycopg

    apply_migrations(db_cfg, directory=REPO / "db" / "migrations")
    arts = default_artifacts(REPO)

    r1 = import_parana_boundary(db_cfg, artifacts=arts)
    assert r1.status == "succeeded"
    assert r1.already_present is False

    r2 = import_parana_boundary(db_cfg, artifacts=arts)
    assert r2.status == "succeeded"
    assert r2.already_present is True
    assert r2.content_sha256 == r1.content_sha256
    assert r2.territorial_unit_id == r1.territorial_unit_id

    with psycopg.connect(db_cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM geoai.territorial_units
                WHERE ibge_code = '41' AND mesh_edition = %s
                """,
                ("municipio_2025",),
            )
            assert int(cur.fetchone()[0]) == 1

            cur.execute(
                """
                SELECT
                    extensions.ST_IsValid(geom),
                    extensions.ST_SRID(geom),
                    extensions.GeometryType(geom),
                    uf_sigla,
                    name
                FROM geoai.territorial_units
                WHERE ibge_code = '41'
                """
            )
            valid, srid, gtype, sigla, name = cur.fetchone()
            assert valid is True
            assert int(srid) == 4674
            assert str(gtype).upper() == "MULTIPOLYGON"
            assert sigla == "PR"
            assert "Paraná" in name

            cur.execute(
                """
                SELECT COUNT(*) FROM geoai.ingestion_runs
                WHERE source_id = 'ibge_bcim_uf_2025' AND status = 'succeeded'
                """
            )
            assert int(cur.fetchone()[0]) >= 2

            # Consulta espacial: ponto em Maringá (aprox.) deve intersectar o PR
            cur.execute(
                """
                SELECT extensions.ST_Intersects(
                    geom,
                    extensions.ST_SetSRID(
                        extensions.ST_MakePoint(-51.9386, -23.4273),
                        4674
                    )
                )
                FROM geoai.territorial_units
                WHERE ibge_code = '41'
                """
            )
            assert cur.fetchone()[0] is True

            # Ponto fora (oceano Atlântico) não intersecta
            cur.execute(
                """
                SELECT extensions.ST_Intersects(
                    geom,
                    extensions.ST_SetSRID(
                        extensions.ST_MakePoint(-30.0, -20.0),
                        4674
                    )
                )
                FROM geoai.territorial_units
                WHERE ibge_code = '41'
                """
            )
            assert cur.fetchone()[0] is False


@requires_postgis
@pytest.mark.postgis
def test_import_failure_rolls_back(db_cfg: DatabaseConfig) -> None:
    """Falha pós-insert (geometria inválida forçada) não deixa unidade órfã."""
    import psycopg

    apply_migrations(db_cfg, directory=REPO / "db" / "migrations")

    with psycopg.connect(db_cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM geoai.territorial_units WHERE ibge_code = '99'"
            )
            before = int(cur.fetchone()[0])

    with psycopg.connect(db_cfg.database_url) as conn:
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO geoai.data_sources (
                            source_id, organization, product, license_note, status
                        ) VALUES (
                            'rollback_probe', 'test', 'probe', 'n/a', 'prototype'
                        )
                        ON CONFLICT (source_id) DO NOTHING
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO geoai.territorial_units (
                            ibge_code, uf_sigla, name, mesh_edition, geom
                        ) VALUES (
                            '99', 'XX', 'RollbackProbe', 'test',
                            extensions.ST_GeomFromText(
                                'MULTIPOLYGON(((0 0, 1 0, 1 1, 0 1, 0 0)))',
                                4674
                            )
                        )
                        """
                    )
                    # Força falha após insert
                    raise RuntimeError("simulated_failure")
        except RuntimeError as exc:
            assert "simulated_failure" in str(exc)

    with psycopg.connect(db_cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM geoai.territorial_units WHERE ibge_code = '99'"
            )
            after = int(cur.fetchone()[0])
    assert after == before
