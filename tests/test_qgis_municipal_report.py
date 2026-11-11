"""Contrato do relatório QGIS + fail-closed negativo no loader municipal."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import geopandas as gpd
import pytest
from geoai.connectors.ibge import EXPECTED_SOURCE_CRS
from geoai.portal.municipal_explorer import load_municipality_layer
from geoai.portal.paths import (
    municipalities_geojson_path,
    municipalities_provenance_path,
    municipalities_validation_path,
)
from geoai.qgis.municipal_report import (
    load_qgis_municipal_report,
    validate_qgis_report_contract,
)
from shapely.geometry import Polygon

REPO = Path(__file__).resolve().parents[1]


def test_qgis_report_contract_committed() -> None:
    report = load_qgis_municipal_report(REPO)
    if report is None:
        pytest.skip("relatório QGIS ainda não versionado")
    problems = validate_qgis_report_contract(report)
    assert problems == [], problems
    engine = report["engine"]
    assert "3.44" in str(engine["qgis_version"])
    assert engine["gdal_version"]
    assert engine["proj_version"]
    assert report["results"]["valid_count"] == 399
    assert report["results"]["invalid_count"] == 0
    assert "scope_note" in report
    assert report["input"]["crs_authid"] == EXPECTED_SOURCE_CRS


def test_qgis_report_rejects_tampered_contract() -> None:
    report = load_qgis_municipal_report(REPO)
    if report is None:
        pytest.skip("relatório QGIS ainda não versionado")
    bad = json.loads(json.dumps(report))
    bad["results"]["invalid_count"] = 3
    bad["input"]["crs_authid"] = "EPSG:4326"
    problems = validate_qgis_report_contract(bad)
    assert any("invalid_count" in p for p in problems)
    assert any("CRS" in p for p in problems)


def _seed_repo_copy(tmp_path: Path) -> Path:
    """Cópia mínima dos artefatos municipais para mutação fail-closed."""

    root = tmp_path / "repo"
    derived = root / "data" / "derived"
    derived.mkdir(parents=True)
    for fn in (
        municipalities_geojson_path(REPO),
        municipalities_provenance_path(REPO),
        municipalities_validation_path(REPO),
        REPO / "data" / "derived" / "parana_municipios_2025_qgis_report.json",
    ):
        if not fn.is_file():
            pytest.skip(f"artefato ausente: {fn.name}")
        shutil.copy2(fn, derived / fn.name)
    return root


def test_fail_closed_crs_mismatch(tmp_path: Path) -> None:
    root = _seed_repo_copy(tmp_path)
    geo = municipalities_geojson_path(root)
    gdf = gpd.read_file(geo)
    gdf = gdf.set_crs(4326, allow_override=True)
    gdf.to_file(geo, driver="GeoJSON")
    # Atualiza SHA na proveniência para isolar o motivo CRS.
    prov_path = municipalities_provenance_path(root)
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    import hashlib

    provenance["derived_geojson_sha256"] = hashlib.sha256(geo.read_bytes()).hexdigest()
    prov_path.write_text(json.dumps(provenance), encoding="utf-8")
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert bundle.missing_reason_pt is not None
    assert "CRS" in (bundle.missing_reason_pt or "")
    assert "4326" in (bundle.missing_reason_pt or "")


def test_fail_closed_non_pr_code(tmp_path: Path) -> None:
    root = _seed_repo_copy(tmp_path)
    geo = municipalities_geojson_path(root)
    gdf = gpd.read_file(geo)
    gdf.loc[gdf.index[0], "CD_MUN"] = "3550308"  # São Paulo
    gdf.to_file(geo, driver="GeoJSON")
    prov_path = municipalities_provenance_path(root)
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    import hashlib

    provenance["derived_geojson_sha256"] = hashlib.sha256(geo.read_bytes()).hexdigest()
    prov_path.write_text(json.dumps(provenance), encoding="utf-8")
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert "41xxxxx" in (bundle.missing_reason_pt or "")


def test_fail_closed_bad_area(tmp_path: Path) -> None:
    root = _seed_repo_copy(tmp_path)
    geo = municipalities_geojson_path(root)
    gdf = gpd.read_file(geo)
    gdf.loc[gdf.index[0], "AREA_KM2"] = -1.0
    gdf.to_file(geo, driver="GeoJSON")
    prov_path = municipalities_provenance_path(root)
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    import hashlib

    provenance["derived_geojson_sha256"] = hashlib.sha256(geo.read_bytes()).hexdigest()
    prov_path.write_text(json.dumps(provenance), encoding="utf-8")
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert "AREA_KM2" in (bundle.missing_reason_pt or "")


def test_fail_closed_empty_geometry(tmp_path: Path) -> None:
    root = _seed_repo_copy(tmp_path)
    geo = municipalities_geojson_path(root)
    gdf = gpd.read_file(geo)
    gdf.loc[gdf.index[0], "geometry"] = Polygon()
    gdf.to_file(geo, driver="GeoJSON")
    prov_path = municipalities_provenance_path(root)
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    import hashlib

    provenance["derived_geojson_sha256"] = hashlib.sha256(geo.read_bytes()).hexdigest()
    prov_path.write_text(json.dumps(provenance), encoding="utf-8")
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert "geometr" in (bundle.missing_reason_pt or "").casefold()

def test_area_km2_values_ok_rejects_inf_nan() -> None:
    from geoai.portal.municipal_explorer import area_km2_values_ok

    assert area_km2_values_ok([1.0, 2.5, 10]) is True
    assert area_km2_values_ok([1.0, float("inf")]) is False
    assert area_km2_values_ok([1.0, float("-inf")]) is False
    assert area_km2_values_ok([1.0, float("nan")]) is False
    assert area_km2_values_ok([1.0, 0.0]) is False
    assert area_km2_values_ok([1.0, -3.0]) is False


def test_fail_closed_area_inf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seed_repo_copy(tmp_path)
    real_read = gpd.read_file

    def _read_with_inf(path, *args, **kwargs):  # noqa: ANN001
        gdf = real_read(path, *args, **kwargs)
        out = gdf.copy()
        out.loc[out.index[0], "AREA_KM2"] = float("inf")
        return out

    monkeypatch.setattr(gpd, "read_file", _read_with_inf)
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert "AREA_KM2" in (bundle.missing_reason_pt or "")


def test_fail_closed_validation_source_crs_mismatch(tmp_path: Path) -> None:
    root = _seed_repo_copy(tmp_path)
    val_path = municipalities_validation_path(root)
    validation = json.loads(val_path.read_text(encoding="utf-8"))
    validation["source_crs"] = "EPSG:4326"
    val_path.write_text(json.dumps(validation), encoding="utf-8")
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert "source_crs" in (bundle.missing_reason_pt or "")


def test_fail_closed_stale_qgis_zip_hash(tmp_path: Path) -> None:
    root = _seed_repo_copy(tmp_path)
    qgis_path = root / "data" / "derived" / "parana_municipios_2025_qgis_report.json"
    assert qgis_path.is_file()
    report = json.loads(qgis_path.read_text(encoding="utf-8"))
    report["input"]["sha256"] = "0" * 64
    qgis_path.write_text(json.dumps(report), encoding="utf-8")
    bundle = load_municipality_layer(root)
    assert bundle.available is False
    assert "QGIS" in (bundle.missing_reason_pt or "")
    assert "SHA" in (bundle.missing_reason_pt or "")


def test_cross_check_qgis_report_ok_with_committed_artifacts() -> None:
    from geoai.qgis.municipal_report import (
        cross_check_qgis_report,
        load_qgis_municipal_report,
    )

    report = load_qgis_municipal_report(REPO)
    if report is None:
        pytest.skip("relatório QGIS ausente")
    provenance = json.loads(
        municipalities_provenance_path(REPO).read_text(encoding="utf-8")
    )
    validation = json.loads(
        municipalities_validation_path(REPO).read_text(encoding="utf-8")
    )
    problems = cross_check_qgis_report(
        report, provenance, validation=validation
    )
    assert problems == [], problems

