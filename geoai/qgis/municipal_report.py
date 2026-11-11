"""Contrato do relatório QGIS municipal (leitura/validação sem PyQGIS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.boundaries.validate import crs_equals
from geoai.portal.paths import derived_dir, repo_root_from_here

EXPECTED_SOURCE_CRS = "EPSG:4674"
EXPECTED_FEATURE_COUNT = 399
EXPECTED_ZIP_REL = "data/raw/ibge/PR_Municipios_2025.zip"


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


def cross_check_qgis_report(
    report: dict[str, Any],
    provenance: dict[str, Any],
    *,
    validation: dict[str, Any] | None = None,
) -> list[str]:
    """Cruza relatório QGIS com proveniência IBGE / validação (fail-closed)."""

    problems = validate_qgis_report_contract(report)
    inp = report.get("input") or {}
    zip_sha = provenance.get("content_sha256")
    report_sha = inp.get("sha256")
    if not isinstance(zip_sha, str) or not zip_sha:
        problems.append("proveniência sem content_sha256 do ZIP IBGE")
    elif report_sha != zip_sha:
        problems.append(
            "SHA do input QGIS diverge de content_sha256 da proveniência IBGE"
        )

    local_zip = str(provenance.get("local_zip") or "").replace("\\", "/")
    report_path_rel = str(inp.get("path") or "").replace("\\", "/")
    if local_zip and report_path_rel and local_zip != report_path_rel:
        problems.append(
            f"path QGIS {report_path_rel!r} != local_zip {local_zip!r}"
        )
    elif report_path_rel and report_path_rel != EXPECTED_ZIP_REL:
        problems.append(f"path QGIS inesperado: {report_path_rel!r}")

    derived_sha = provenance.get("derived_geojson_sha256")
    presentation = report.get("presentation_artifact") or {}
    pres_sha = presentation.get("sha256")
    if isinstance(derived_sha, str) and derived_sha and isinstance(pres_sha, str):
        if pres_sha != derived_sha:
            problems.append(
                "SHA presentation_artifact QGIS diverge de derived_geojson_sha256"
            )

    if validation:
        declared = validation.get("source_crs")
        if declared and not crs_equals(declared, EXPECTED_SOURCE_CRS):
            problems.append(
                f"validation.source_crs {declared!r} != {EXPECTED_SOURCE_CRS}"
            )
        if declared and inp.get("crs_authid") and not crs_equals(
            declared, inp.get("crs_authid")
        ):
            problems.append(
                "CRS do relatório QGIS diverge de validation.source_crs"
            )

    expected_prov = provenance.get("expected_crs")
    if expected_prov and not crs_equals(expected_prov, EXPECTED_SOURCE_CRS):
        problems.append(
            f"proveniência expected_crs {expected_prov!r} != {EXPECTED_SOURCE_CRS}"
        )

    return problems


def default_report_template_note(repo_root: Path | None = None) -> str:
    root = repo_root or repo_root_from_here()
    return (
        f"Gere o relatório com QGIS Desktop/MCP ou "
        f"`python-qgis-ltr.bat scripts/_qgis_mun_worker.py` em {root}."
    )
