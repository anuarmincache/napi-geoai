"""Contrato do relatório QGIS municipal (leitura/validação sem PyQGIS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.portal.paths import derived_dir, repo_root_from_here

EXPECTED_SOURCE_CRS = "EPSG:4674"
EXPECTED_FEATURE_COUNT = 399


def report_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_municipios_2025_qgis_report.json"


def load_qgis_municipal_report(
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    path = report_path(repo_root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_qgis_report_contract(report: dict[str, Any]) -> list[str]:
    """Retorna lista de problemas; vazia = contrato OK."""

    problems: list[str] = []
    engine = report.get("engine") or {}
    results = report.get("results") or {}
    inp = report.get("input") or {}
    if not engine.get("qgis_version"):
        problems.append("engine.qgis_version ausente")
    if not engine.get("gdal_version"):
        problems.append("engine.gdal_version ausente")
    if not engine.get("proj_version"):
        problems.append("engine.proj_version ausente")
    if "native:checkvalidity" not in str(engine.get("algorithms")):
        problems.append("algoritmo native:checkvalidity não registrado")
    if inp.get("crs_authid") != EXPECTED_SOURCE_CRS:
        problems.append(
            f"CRS input {inp.get('crs_authid')!r} != {EXPECTED_SOURCE_CRS}"
        )
    if int(inp.get("feature_count", -1)) != EXPECTED_FEATURE_COUNT:
        problems.append("feature_count != 399")
    if int(results.get("valid_count", -1)) != EXPECTED_FEATURE_COUNT:
        problems.append("valid_count != 399")
    if "invalid_count" not in results or int(results["invalid_count"]) != 0:
        problems.append("invalid_count != 0")
    if results.get("cd_mun_prefix_41_ok") is not True:
        problems.append("cd_mun_prefix_41_ok falso")
    if results.get("area_km2_finite_positive_ok") is not True:
        problems.append("area_km2_finite_positive_ok falso")
    if not inp.get("sha256"):
        problems.append("input.sha256 ausente")
    if "scope_note" not in report:
        problems.append("scope_note ausente (SHA vs validação geométrica)")
    return problems


def default_report_template_note(repo_root: Path | None = None) -> str:
    root = repo_root or repo_root_from_here()
    return (
        f"Gere o relatório com QGIS Desktop/MCP ou "
        f"`python-qgis-ltr.bat scripts/_qgis_mun_worker.py` em {root}."
    )
