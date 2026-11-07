"""Testes de validação geométrica e preparação do limite do Paraná."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest
from geoai.boundaries.parana import read_ibge_uf_zip
from geoai.boundaries.validate import validate_polygon_layer
from geoai.connectors.ibge import EXPECTED_SOURCE_CRS
from shapely.geometry import Polygon

FIXTURE = Path(__file__).parent / "fixtures" / "parana_mini.geojson"


def test_validate_fixture_polygon_is_valid() -> None:
    gdf = gpd.read_file(FIXTURE)
    assert gdf.crs is not None
    validated, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=False
    )
    assert len(validated) == 1
    assert report.all_valid
    assert report.invalid_count == 0
    assert report.empty_count == 0
    assert report.non_polygon_count == 0
    assert report.feature_count == 1


def test_validate_repairs_bowtie() -> None:
    # Polígono auto-intersectante (bowtie) — inválido até make_valid.
    bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bowtie], crs=EXPECTED_SOURCE_CRS)
    _, before = validate_polygon_layer(gdf, repair=False)
    assert before.invalid_count == 1
    repaired, after = validate_polygon_layer(gdf, repair=True)
    assert after.invalid_count == 0
    assert repaired.geometry.is_valid.all()


def test_fixture_is_marked_synthetic() -> None:
    gdf = gpd.read_file(FIXTURE)
    note = str(gdf.iloc[0]["note"])
    assert "não é a malha ibge oficial" in note.lower()


@pytest.mark.integration
def test_read_downloaded_ibge_zip_if_present() -> None:
    zip_path = (
        Path(__file__).resolve().parents[1] / "data" / "raw" / "ibge" / "PR_UF_2025.zip"
    )
    if not zip_path.exists():
        pytest.skip("ZIP IBGE ausente — execute scripts/prepare_parana_boundary.py")
    gdf = read_ibge_uf_zip(zip_path)
    assert len(gdf) >= 1
    assert gdf.crs is not None
    _, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=True
    )
    assert report.feature_count >= 1
    assert report.non_polygon_count == 0
