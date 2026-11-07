"""Testes de validação geométrica e preparação do limite do Paraná."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest
from geoai.boundaries.parana import prepare_parana_boundary, read_ibge_uf_zip
from geoai.boundaries.validate import (
    BoundaryValidationError,
    assert_exportable,
    validate_polygon_layer,
)
from geoai.connectors.ibge import EXPECTED_SOURCE_CRS
from shapely.geometry import LineString, Point, Polygon

FIXTURE = Path(__file__).parent / "fixtures" / "parana_mini.geojson"
REPO = Path(__file__).resolve().parents[1]


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
    assert report.is_exportable
    assert_exportable(report)


def test_validate_repairs_bowtie() -> None:
    bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bowtie], crs=EXPECTED_SOURCE_CRS)
    _, before = validate_polygon_layer(gdf, repair=False)
    assert before.invalid_count == 1
    assert not before.is_exportable
    repaired, after = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=True
    )
    assert after.invalid_count == 0
    assert after.non_polygon_count == 0
    assert repaired.geometry.is_valid.all()
    assert after.is_exportable


def test_reject_missing_crs() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs=None,
    )
    _, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=False
    )
    assert report.crs_missing
    assert report.crs_mismatch
    assert not report.is_exportable
    with pytest.raises(BoundaryValidationError):
        assert_exportable(report)


def test_reject_divergent_crs() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    _, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=False
    )
    assert report.crs_mismatch
    assert not report.is_exportable
    with pytest.raises(BoundaryValidationError):
        assert_exportable(report)


def test_reject_empty_geometry() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[Polygon()],
        crs=EXPECTED_SOURCE_CRS,
    )
    _, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=False
    )
    assert report.empty_count == 1
    assert not report.is_exportable
    with pytest.raises(BoundaryValidationError):
        assert_exportable(report)


def test_reject_non_polygon() -> None:
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[Point(0, 0), LineString([(0, 0), (1, 1)])],
        crs=EXPECTED_SOURCE_CRS,
    )
    _, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=False
    )
    assert report.non_polygon_count == 2
    assert not report.is_exportable
    with pytest.raises(BoundaryValidationError):
        assert_exportable(report)


def test_read_ibge_uf_zip_rejects_missing_crs_without_assume(
    tmp_path: Path,
) -> None:
    import zipfile

    # Shapefile sem .prj → CRS ausente na leitura.
    gdf = gpd.GeoDataFrame(
        {"SIGLA_UF": ["PR"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    )
    assert gdf.crs is None
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    shp_path = shp_dir / "PR_UF_fake.shp"
    gdf.to_file(shp_path)
    for prj in shp_dir.glob("*.prj"):
        prj.unlink()

    zip_path = tmp_path / "fake.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for part in shp_dir.iterdir():
            archive.write(part, arcname=part.name)

    with pytest.raises(BoundaryValidationError, match="CRS ausente"):
        read_ibge_uf_zip(zip_path)

    assumed = read_ibge_uf_zip(zip_path, assume_crs=EXPECTED_SOURCE_CRS)
    assert assumed.crs is not None


def test_fixture_is_marked_synthetic() -> None:
    gdf = gpd.read_file(FIXTURE)
    note = str(gdf.iloc[0]["note"])
    assert "não é a malha ibge oficial" in note.lower()


@pytest.mark.integration
def test_read_downloaded_ibge_zip_if_present() -> None:
    """Integração local Windows: requer ZIP baixado; CI usa mocks/fixtures."""

    zip_path = REPO / "data" / "raw" / "ibge" / "PR_UF_2025.zip"
    if not zip_path.exists():
        pytest.skip("ZIP IBGE ausente — execute scripts/prepare_parana_boundary.py")
    gdf = read_ibge_uf_zip(zip_path)
    assert len(gdf) >= 1
    assert gdf.crs is not None
    _, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=True
    )
    assert_exportable(report)


@pytest.mark.integration
def test_prepare_parana_boundary_success_on_windows(tmp_path: Path) -> None:
    zip_src = REPO / "data" / "raw" / "ibge" / "PR_UF_2025.zip"
    if not zip_src.exists():
        pytest.skip("ZIP IBGE ausente — integração local Windows não executada")

    # Reusa o ZIP já baixado sem novo HTTP: copia para raw_dir do tmp.
    import shutil

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    shutil.copy(zip_src, raw_dir / "PR_UF_2025.zip")

    # Monkeypatch download para não bater na rede.
    from geoai.boundaries import parana as parana_mod
    from geoai.connectors.ibge import IbgeMalhaSource

    def _fake_download(
        url: str, destination: Path, **kwargs: object
    ) -> IbgeMalhaSource:
        if not Path(destination).exists():
            shutil.copy(zip_src, destination)
        return IbgeMalhaSource(
            name="PR_UF_2025",
            url=url,
            edition="municipio_2025",
            territory="Paraná (UF)",
            license_note="test",
            expected_crs=EXPECTED_SOURCE_CRS,
            retrieved_at="test",
            content_sha256="x",
            content_length=1,
            http_etag=None,
            http_last_modified=None,
            local_zip=str(destination),
        )

    monkey_download = _fake_download
    original = parana_mod.download_ibge_zip
    parana_mod.download_ibge_zip = monkey_download  # type: ignore[assignment]
    try:
        out, _source, report = prepare_parana_boundary(
            tmp_path / "out.geojson",
            raw_dir=raw_dir,
            provenance_path=tmp_path / "prov.json",
            report_path=tmp_path / "val.json",
        )
    finally:
        parana_mod.download_ibge_zip = original  # type: ignore[assignment]

    assert out.exists()
    assert report.is_exportable
    val = (tmp_path / "val.json").read_text(encoding="utf-8")
    assert "validation_exportable" in val
    assert "map_crs_limitation" in val
