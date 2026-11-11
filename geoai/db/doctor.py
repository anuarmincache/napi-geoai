"""Diagnóstico não destrutivo do banco PostGIS (db doctor)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from geoai.db.config import DatabaseConfig
from geoai.db.postgis import configure_search_path, resolve_postgis_schema
from geoai.db.url_safety import redact_database_url

Severity = Literal["ok", "warn", "crit"]


@dataclass
class DoctorCheck:
    name: str
    severity: Severity
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DoctorReport:
    database_url_redacted: str
    overall: Severity
    checks: list[DoctorCheck]
    exit_code: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_url": self.database_url_redacted,
            "overall": self.overall,
            "exit_code": self.exit_code,
            "checks": [asdict(c) for c in self.checks],
        }


def _rank(sev: Severity) -> int:
    return {"ok": 0, "warn": 1, "crit": 2}[sev]


def run_doctor(cfg: DatabaseConfig) -> DoctorReport:
    """Coleta estado do banco sem escrever dados."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg não instalado; pip install -e '.[db]'") from exc

    checks: list[DoctorCheck] = []
    redacted = redact_database_url(cfg.database_url)

    try:
        with psycopg.connect(cfg.database_url) as conn:
            configure_search_path(conn, app_schema=cfg.schema)
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                pg_version = str(cur.fetchone()[0])
                checks.append(
                    DoctorCheck(
                        "postgresql_version",
                        "ok" if "PostgreSQL 16" in pg_version else "warn",
                        pg_version.split(",")[0],
                        {"full": pg_version},
                    )
                )

                cur.execute("SELECT PostGIS_Version()")
                postgis = str(cur.fetchone()[0])
                sev: Severity = "ok" if postgis.startswith("3.") else "warn"
                checks.append(
                    DoctorCheck(
                        "postgis_version",
                        sev,
                        postgis,
                    )
                )

                pgis_schema = resolve_postgis_schema(conn)
                checks.append(
                    DoctorCheck(
                        "postgis_schema",
                        "ok" if pgis_schema in {"public", "extensions"} else "warn",
                        f"extensão em schema {pgis_schema}",
                        {"schema": pgis_schema},
                    )
                )

                cur.execute(
                    f"""
                    SELECT version FROM {cfg.schema}.schema_migrations
                    ORDER BY version
                    """
                )
                migrations = [r[0] for r in cur.fetchall()]
                checks.append(
                    DoctorCheck(
                        "schema_migrations",
                        "ok" if "0001_init_postgis" in migrations else "crit",
                        f"{len(migrations)} migração(ões)",
                        {"versions": migrations},
                    )
                )

                cur.execute(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = %s AND tablename = 'territorial_units'
                      AND indexdef ILIKE '%%USING gist%%'
                    """,
                    (cfg.schema,),
                )
                gist = [r[0] for r in cur.fetchall()]
                checks.append(
                    DoctorCheck(
                        "gist_index",
                        "ok" if gist else "crit",
                        "GiST presente" if gist else "GiST ausente",
                        {"indexes": gist},
                    )
                )

                cur.execute(
                    f"""
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE ST_SRID(geom) = 4674),
                           COUNT(*) FILTER (WHERE ST_IsValid(geom)),
                           COUNT(*) FILTER (
                             WHERE GeometryType(geom) = 'MULTIPOLYGON'
                           )
                    FROM {cfg.schema}.territorial_units
                    """
                )
                total, srid_ok, valid_ok, multi_ok = cur.fetchone()
                total_i = int(total)
                if total_i == 0:
                    checks.append(
                        DoctorCheck(
                            "territorial_units",
                            "warn",
                            "nenhuma unidade territorial carregada",
                            {"count": 0},
                        )
                    )
                elif (
                    int(srid_ok) == total_i
                    and int(valid_ok) == total_i
                    and int(multi_ok) == total_i
                ):
                    checks.append(
                        DoctorCheck(
                            "territorial_units",
                            "ok",
                            f"{total_i} unidade(s); SRID 4674; válidas; MultiPolygon",
                            {
                                "count": total_i,
                                "srid_4674": int(srid_ok),
                                "valid": int(valid_ok),
                                "multipolygon": int(multi_ok),
                            },
                        )
                    )
                else:
                    checks.append(
                        DoctorCheck(
                            "territorial_units",
                            "crit",
                            "integridade geométrica inconsistente",
                            {
                                "count": total_i,
                                "srid_4674": int(srid_ok),
                                "valid": int(valid_ok),
                                "multipolygon": int(multi_ok),
                            },
                        )
                    )

                cur.execute(
                    f"""
                    SELECT source_id, organization, product, status
                    FROM {cfg.schema}.data_sources
                    ORDER BY source_id
                    """
                )
                sources = [
                    {
                        "source_id": r[0],
                        "organization": r[1],
                        "product": r[2],
                        "status": r[3],
                    }
                    for r in cur.fetchall()
                ]
                checks.append(
                    DoctorCheck(
                        "data_sources",
                        "ok" if sources else "warn",
                        f"{len(sources)} fonte(s)",
                        {"sources": sources},
                    )
                )

                cur.execute(
                    f"""
                    SELECT COUNT(*), COUNT(DISTINCT content_sha256)
                    FROM {cfg.schema}.data_artifacts
                    """
                )
                art_count, art_sha = cur.fetchone()
                checks.append(
                    DoctorCheck(
                        "data_artifacts",
                        "ok",
                        f"{int(art_count)} artefato(s)",
                        {
                            "count": int(art_count),
                            "distinct_sha256": int(art_sha),
                        },
                    )
                )

                cur.execute(
                    f"""
                    SELECT status, COUNT(*)
                    FROM {cfg.schema}.ingestion_runs
                    GROUP BY status
                    ORDER BY status
                    """
                )
                runs = {r[0]: int(r[1]) for r in cur.fetchall()}
                checks.append(
                    DoctorCheck(
                        "ingestion_runs",
                        "ok",
                        f"runs por status: {runs or '{}'}",
                        {"by_status": runs},
                    )
                )

                cur.execute(
                    """
                    SELECT 1 FROM pg_database
                    WHERE datname = 'template_napi_postgis'
                    """
                )
                has_tpl = cur.fetchone() is not None
                checks.append(
                    DoctorCheck(
                        "postgis_restore_template",
                        "ok" if has_tpl else "warn",
                        (
                            "template_napi_postgis presente"
                            if has_tpl
                            else "template ausente — restore isolado local limitado"
                        ),
                        {
                            "hint": (
                                None
                                if has_tpl
                                else "bash scripts/ensure_postgis_template.sh"
                            )
                        },
                    )
                )

    except Exception as exc:  # noqa: BLE001 — relatório de diagnóstico
        checks.append(
            DoctorCheck(
                "connection",
                "crit",
                f"falha ao conectar/consultar: {type(exc).__name__}",
                {"error": str(exc)[:300]},
            )
        )

    overall: Severity = "ok"
    for c in checks:
        if _rank(c.severity) > _rank(overall):
            overall = c.severity
    exit_code = {"ok": 0, "warn": 1, "crit": 2}[overall]
    return DoctorReport(
        database_url_redacted=redacted,
        overall=overall,
        checks=checks,
        exit_code=exit_code,
    )


def format_doctor_report(report: DoctorReport, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    lines = [
        f"db doctor — {report.overall.upper()} (exit {report.exit_code})",
        f"database: {report.database_url_redacted}",
        "",
    ]
    for c in report.checks:
        lines.append(f"[{c.severity}] {c.name}: {c.message}")
    return "\n".join(lines)
