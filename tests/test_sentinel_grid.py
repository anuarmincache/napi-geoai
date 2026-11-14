"""Grade, publicação e redirecionamento sem rede e sem segredo."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pytest
from geoai.sentinel.assets import https_band_urls, official_asset_url
from geoai.sentinel.budget import l2a_contract, plan_from_catalog
from geoai.sentinel.cdse_auth import (
    RedirectRefused,
    _AssetRedirect,
    _complete_download,
)
from geoai.sentinel.gdal_blocks import measure_blocks
from geoai.sentinel.gdal_scene import (
    municipality_bounds,
    ogr_mesh_path,
    rasterize_municipality,
)
from geoai.sentinel.grid import (
    clip_placement,
    nearest_sample,
    place_array,
    snap_aoi_grid,
    source_window_for_output,
)
from geoai.sentinel.publish import publication_allowed, publish_new_raster

OFFICIAL = "https://download.dataspace.copernicus.eu/odata/v1/Products(a)/$value"
REPO = Path(__file__).resolve().parents[1]


def test_snap_and_place_keep_source_values() -> None:
    reference = (100.0, 10.0, 0.0, 200.0, 0.0, -10.0)
    grid = snap_aoi_grid((95.0, 155.0, 125.0, 185.0), reference)
    assert grid["cols"] == 4
    assert grid["rows"] == 4
    source = (80.0, 10.0, 0.0, 210.0, 0.0, -10.0)
    window = source_window_for_output(source, 6, 6, grid["geotransform"], 4, 4)
    assert window is not None
    destination = np.zeros((4, 4), dtype=np.uint16)
    values = np.arange(window["ysize"] * window["xsize"], dtype=np.uint16).reshape(
        window["ysize"], window["xsize"]
    )
    place_array(destination, values, window)
    view = destination[
        window["dst_yoff"] : window["dst_yoff"] + window["ysize"],
        window["dst_xoff"] : window["dst_xoff"] + window["xsize"],
    ]
    assert np.array_equal(view, values)


def test_nearest_sample_uses_twenty_meter_parent() -> None:
    source = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    sampled = nearest_sample(
        source,
        (0.0, 20.0, 0.0, 40.0, 0.0, -20.0),
        (0.0, 10.0, 0.0, 40.0, 0.0, -10.0),
        4,
        4,
    )
    assert np.array_equal(sampled[0:2, 0:2], np.full((2, 2), 1))
    assert np.array_equal(sampled[0:2, 2:4], np.full((2, 2), 2))
    assert np.array_equal(sampled[2:4, 0:2], np.full((2, 2), 3))
    assert np.array_equal(sampled[2:4, 2:4], np.full((2, 2), 4))


def test_publication_requires_one_official_pass_at_the_threshold() -> None:
    assert publication_allowed(
        official_pixels=True,
        valid_fraction=0.70,
        acquisition_ids=("S2B_20261112T133149_R081",),
    )
    assert (
        publication_allowed(
            official_pixels=True,
            valid_fraction=0.699999,
            acquisition_ids=("S2B_20261112T133149_R081",),
        )
        is False
    )
    assert (
        publication_allowed(
            official_pixels=False,
            valid_fraction=0.99,
            acquisition_ids=("sintetico",),
        )
        is False
    )
    assert (
        publication_allowed(
            official_pixels=True,
            valid_fraction=0.9,
            acquisition_ids=(
                "S2B_20261112T133149_R081",
                "S2A_20261109T133231_R081",
            ),
        )
        is False
    )


def test_other_host_redirect_drops_authorization() -> None:
    request = urllib.request.Request(
        OFFICIAL,
        headers={"Authorization": "Bearer local-test", "Cookie": "session=local"},
    )
    redirected = _AssetRedirect().redirect_request(
        request,
        None,
        302,
        "found",
        {},
        "https://zipper.example/object",
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None
    assert redirected.get_header("Cookie") is None


def test_official_asset_redirect_keeps_only_authorization() -> None:
    request = urllib.request.Request(
        OFFICIAL,
        headers={"Authorization": "Bearer local-test", "Cookie": "session=local"},
    )
    redirected = _AssetRedirect().redirect_request(
        request,
        None,
        307,
        "temporary",
        {},
        OFFICIAL,
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") == "Bearer local-test"
    assert redirected.get_header("Cookie") is None


def test_insecure_redirect_is_refused() -> None:
    request = urllib.request.Request(
        OFFICIAL,
        headers={"Authorization": "Bearer local-test"},
    )
    with pytest.raises(RedirectRefused) as caught:
        _AssetRedirect().redirect_request(
            request,
            None,
            302,
            "found",
            {},
            "http://zipper.example/object",
        )
    assert "local-test" not in str(caught.value)


def test_complete_download_rejects_a_partial_object() -> None:
    assert _complete_download(200, None, 12) is True
    assert _complete_download(206, "bytes 0-11/12", 12) is True
    assert _complete_download(206, "bytes 0-1023/999999", 1024) is False
    assert _complete_download(200, None, 0) is False


def test_band_urls_reject_a_query_string() -> None:
    with pytest.raises(ValueError):
        official_asset_url("/odata/v1/Products(a)/$value?sig=local")
    feature = {
        "assets": {
            key: {
                "alternate": {
                    "https": {
                        "href": (
                            "https://download.dataspace.copernicus.eu"
                            f"/odata/v1/Products({key})/$value"
                        )
                    }
                }
            }
            for key in ("B04_10m", "B08_10m", "SCL_20m")
        }
    }
    urls = https_band_urls(feature)
    assert set(urls) == {"B04_10m", "B08_10m", "SCL_20m"}
    assert all(url.endswith("/$value") for url in urls.values())


def test_gdal_window_evidence_is_not_a_sentinel_scene() -> None:
    path = REPO / "docs" / "evidence" / "sentinel" / "gdal_window_synthetic.json"
    if not path.is_file():
        pytest.skip("evidência da janela GDAL ainda não gerada")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["sentinel_scene"] is False
    assert payload["official_pixels"] is False
    assert payload["ndvi_published"] is False
    assert payload["read"] == "ReadAsArray"
    assert payload["window_shape"] == [2, 2]
    assert payload["values_match"] is True
    assert payload["write"] == "WriteArray"
    assert payload["write_matches"] is True


def test_measure_blocks_keeps_only_the_window() -> None:
    red = [np.full((4, 4), 0.1), np.full((4, 4), 0.1)]
    nir = [np.full((4, 4), 0.3), np.full((4, 4), 0.5)]
    scl = [np.full((4, 4), 4), np.full((4, 4), 4)]
    scl[0][:, 2:] = 9
    aoi = np.ones((4, 4), dtype=bool)
    seen: list[tuple[int, int]] = []

    def reader(row0: int, row1: int, col0: int, col1: int):
        seen.append((row1 - row0, col1 - col0))
        return (
            [band[row0:row1, col0:col1] for band in red],
            [band[row0:row1, col0:col1] for band in nir],
            [band[row0:row1, col0:col1] for band in scl],
            aoi[row0:row1, col0:col1],
        )

    result = measure_blocks(reader, 4, 4, block=2)
    assert seen
    assert max(seen) == (2, 2)
    assert result["retained_grid"] is False
    assert result["n_aoi"] == 16
    assert sum(result["pixels_per_tile"]) == result["n_valid"]
    assert "ndvi" not in result


def test_clip_placement_is_relative_to_the_block() -> None:
    window = {
        "src_xoff": 10,
        "src_yoff": 20,
        "xsize": 6,
        "ysize": 6,
        "dst_xoff": 1,
        "dst_yoff": 1,
    }
    piece = clip_placement(window, 2, 4, 2, 4)
    assert piece is not None
    assert piece["dst_xoff"] == 0
    assert piece["dst_yoff"] == 0
    assert piece["xsize"] == 2
    assert piece["src_xoff"] == 11
    assert piece["src_yoff"] == 21
    assert clip_placement(None, 0, 1, 0, 1) is None


def test_l2a_metadata_rejects_a_different_offset() -> None:
    assert l2a_contract(0.0001, -0.1, 0, 513)["matches_official_l2a"] is True
    assert l2a_contract(0.0001, 0.0, 0, 513)["matches_official_l2a"] is False
    assert l2a_contract(0.0001, -0.1, 0, 213)["matches_official_l2a"] is False


def test_dry_run_plan_does_not_start_a_download() -> None:
    catalog = json.loads(
        (REPO / "data" / "derived" / "sentinel_maringa_pilot.json").read_text(
            encoding="utf-8"
        )
    )
    plan = plan_from_catalog(catalog, free_bytes=20_000_000_000)
    assert plan["acquisition_id"] == "S2B_20261112T133149_R081"
    assert plan["fallback_acquisition_id"] == "S2A_20261109T133231_R081"
    assert plan["tiles"] == ["22KCV", "22KDV"]
    assert plan["n_bands"] == 6
    assert plan["full_jp2_known_bytes"] == 49709444
    assert plan["full_jp2_ceiling_bytes"] == 49709444 * 6
    assert plan["full_jp2_download"] == "complete_file"
    assert plan["clipped_read"] == "gdal_window"
    assert plan["download_started"] is False
    assert plan["ndvi_published"] is False
    assert plan["metadata_ok"] is True
    assert plan["download_allowed"] is True
    assert plan["block_working_bytes"] < plan["full_matrix_bytes"]
    assert plan["block_working_bytes"] < plan["max_memory_bytes"]
    assert "access_token" not in json.dumps(plan)
    tight = plan_from_catalog(catalog, free_bytes=1_000_000)
    assert tight["download_allowed"] is False


def test_catalog_failure_keeps_the_previous_raster(tmp_path: Path) -> None:
    previous = tmp_path / "ndvi.tif"
    previous.write_bytes(b"raster-anterior")
    staging = tmp_path / "ndvi.tif.staging"
    catalog = {"ndvi_published": False}

    def produce(path: Path) -> None:
        path.write_bytes(b"raster-novo-maior")

    def commit() -> None:
        catalog["ndvi_published"] = True
        raise RuntimeError("catalogo")

    def restore() -> None:
        catalog["ndvi_published"] = False

    with pytest.raises(RuntimeError, match="catalogo"):
        publish_new_raster(previous, staging, produce, commit, restore)
    assert previous.read_bytes() == b"raster-anterior"
    assert not staging.exists()
    assert catalog["ndvi_published"] is False


def test_raster_generation_failure_keeps_the_previous_raster(tmp_path: Path) -> None:
    previous = tmp_path / "ndvi.tif"
    previous.write_bytes(b"raster-anterior")
    staging = tmp_path / "ndvi.tif.staging"

    def produce(path: Path) -> None:
        path.write_bytes(b"parcial")
        previous.write_bytes(b"corrompido")
        raise RuntimeError("gdal")

    with pytest.raises(RuntimeError, match="gdal"):
        publish_new_raster(previous, staging, produce, lambda: None, lambda: None)
    assert previous.read_bytes() == b"raster-anterior"
    assert not staging.exists()


def test_dry_run_cli_does_not_publish(tmp_path: Path) -> None:
    script = REPO / "scripts" / "run_maringa_sentinel.py"
    evidence = tmp_path / "dry.json"
    proc = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--evidence", str(evidence)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "ndvi_published False" in proc.stdout
    assert "download_started False" in proc.stdout
    assert "access_token" not in proc.stdout
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["download_started"] is False
    assert payload["ndvi_published"] is False


def _zip_with(path: Path, names: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as handle:
        for name in names:
            handle.writestr(name, b"")


def test_ogr_mesh_path_uses_vsizip(tmp_path: Path) -> None:
    archive = tmp_path / "PR_Municipios_2025.zip"
    _zip_with(archive, ["PR_Municipios_2025.shp"])
    opened = ogr_mesh_path(archive)
    posix = archive.resolve().as_posix()
    assert opened == f"/vsizip/{posix}/PR_Municipios_2025.shp"
    assert "\\" not in opened


def test_ogr_mesh_path_rejects_a_missing_or_ambiguous_shapefile(tmp_path: Path) -> None:
    empty = tmp_path / "empty.zip"
    _zip_with(empty, ["LEIA-ME.txt"])
    with pytest.raises(FileNotFoundError, match="ausente"):
        ogr_mesh_path(empty)
    ambiguous = tmp_path / "two.zip"
    _zip_with(ambiguous, ["PR_Municipios_2025.shp", "outro_municipio.shp"])
    with pytest.raises(FileNotFoundError, match="ambíguo"):
        ogr_mesh_path(ambiguous)


def test_municipality_code_is_rejected_before_gdal(tmp_path: Path) -> None:
    mesh = tmp_path / "ausente.zip"
    with pytest.raises(ValueError, match="CD_MUN"):
        municipality_bounds(mesh, "41A", "WKT")
    with pytest.raises(ValueError, match="CD_MUN"):
        rasterize_municipality(mesh, "4115200 ", (0, 1, 0, 0, 0, -1), 1, 1, "WKT")


def test_real_ibge_mesh_path_uses_vsizip_when_present() -> None:
    mesh = REPO / "data" / "raw" / "ibge" / "PR_Municipios_2025.zip"
    if not mesh.is_file():
        pytest.skip("malha IBGE ausente")
    opened = ogr_mesh_path(mesh)
    assert opened.startswith("/vsizip/")
    assert "\\" not in opened
    assert opened.endswith("/PR_Municipios_2025.shp")
    assert mesh.resolve().as_posix() in opened


def test_ibge_mesh_gdal_evidence_reads_maringa() -> None:
    path = REPO / "docs" / "evidence" / "sentinel" / "ibge_mesh_gdal.json"
    if not path.is_file():
        pytest.skip("evidência da malha GDAL ainda não gerada")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["cd_mun"] == "4115200"
    assert payload["name"] == "Maringá"
    assert payload["area_km2_official"] == pytest.approx(487.912)
    assert payload["crs_same_as_epsg_4674"] is True
    assert payload["geometry_valid"] is True
    assert payload["geometry_type"] == "Polygon"
    assert payload["bbox"] == pytest.approx(
        [-52.1000868, -23.5583336, -51.8358064999999, -23.2539786999999]
    )
    assert payload["member"] == "PR_Municipios_2025.shp"
    assert payload["open_path"] == "vsizip"
    assert payload["path_has_backslash"] is False
    assert payload["mask_shape"] == [64, 64]
    assert payload["mask_true"] > 0
    assert payload["mask_false"] > 0
    assert payload["point_on_surface_inside"] is True
    assert payload["sentinel_scene"] is False
    assert payload["official_pixels"] is False
    assert payload["ndvi_published"] is False
    assert payload["download_started"] is False
