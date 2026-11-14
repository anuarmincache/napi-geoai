"""Piloto Sentinel-2: reflectância, triagem e catálogo sem cena publicada."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from geoai.sentinel.access import describe_asset_response
from geoai.sentinel.aoi import load_official_municipality, sirgas_utm_epsg
from geoai.sentinel.catalog import load_pilot_catalog, show_ndvi
from geoai.sentinel.reflectance import ReflectanceMetadataError, reflectance_dn
from geoai.sentinel.selection import (
    footprint_coverage,
    rank_full_coverage,
    scene_is_accepted,
)
from geoai.sentinel.windows import choose_search_window, parse_as_of, search_windows
from shapely.geometry import box, mapping

REPO = Path(__file__).resolve().parents[1]


def test_nodata_does_not_receive_offset() -> None:
    assert reflectance_dn(0, scale=0.0001, offset=-0.1, nodata=0) is None
    dark = reflectance_dn(1000, scale=0.0001, offset=-0.1, nodata=0)
    bright = reflectance_dn(2000, scale=0.0001, offset=-0.1, nodata=0)
    assert dark == pytest.approx(0.0)
    assert bright == pytest.approx(0.1)


def test_missing_scale_is_not_assumed() -> None:
    with pytest.raises(ReflectanceMetadataError):
        reflectance_dn(1000, scale=None, offset=-0.1, nodata=0)


def test_full_coverage_outranks_partial_low_cloud() -> None:
    aoi = mapping(box(0, 0, 2, 2))
    full = mapping(box(-1, -1, 3, 3))
    partial = mapping(box(0, 0, 1, 1))
    candidates = [
        {
            "product_id": "parcial-pouca-nuvem",
            "datetime": "2026-11-14T00:00:00Z",
            "eo_cloud_cover": 5,
            "aoi_coverage": footprint_coverage(partial, aoi),
        },
        {
            "product_id": "total-mais-nuvem",
            "datetime": "2026-11-09T00:00:00Z",
            "eo_cloud_cover": 40,
            "aoi_coverage": footprint_coverage(full, aoi),
        },
    ]
    ranked = rank_full_coverage(candidates)
    assert [item["product_id"] for item in ranked] == ["total-mais-nuvem"]
    assert scene_is_accepted(None) is False
    assert scene_is_accepted(0.7) is True
    assert scene_is_accepted(0.69) is False


def test_catalog_is_maringa_and_does_not_publish_ndvi() -> None:
    catalog = load_pilot_catalog(REPO)
    assert catalog["ndvi_published"] is False
    assert show_ndvi(catalog) is False
    assert catalog["status"] != "ready"
    assert catalog["aoi"]["cd_mun"] == "4115200"
    assert catalog["aoi"]["name"] == "Maringá"
    assert catalog["aoi"]["geometry_source"] == "data/raw/ibge/PR_Municipios_2025.zip"
    assert catalog["downloaded_bytes"] == 0
    assert catalog["status"] == "no_adequate_footprint"
    assert catalog["candidate"] is None
    assert catalog["mosaic_required"] is True
    assert catalog["criteria"]["window_used"] == "30d"
    assert catalog["n_full_coverage_7d"] == 0
    probe_scene = catalog["access_probe_scene"]
    assert probe_scene["accepted"] is False
    assert probe_scene["valid_pixel_fraction"] is None
    assert probe_scene["role"] == "access_probe_only"
    assert probe_scene["downloaded_bytes"] == 0
    probe = catalog["asset_access"]["probe"]
    assert probe["authorization_sent"] is False
    assert probe["body_stored"] is False
    assert probe["http_status"] == 401
    text = json.dumps(catalog)
    assert "4119152" not in text
    assert "Pinhais" not in text
    assert "C:/" not in text
    assert "access_token" not in text


def test_missing_catalog_is_not_zero_ndvi(tmp_path: Path) -> None:
    catalog = load_pilot_catalog(tmp_path)
    assert catalog["ndvi_published"] is False
    assert "Nenhum NDVI" in catalog["public_message_pt"]


def test_streamlit_pilot_does_not_process() -> None:
    text = (REPO / "app" / "pages" / "8_Sentinel_Piloto.py").read_text(encoding="utf-8")
    for token in ("import qgis", "from osgeo", "execute_job", "urlopen", "gdal.Warp"):
        assert token not in text
    assert "Pinhais" not in text
    assert "4119152" not in text


def test_gdal_nearest_evidence_is_not_a_sentinel_scene() -> None:
    path = REPO / "docs" / "evidence" / "sentinel" / "gdal_nearest_synthetic.json"
    if not path.is_file():
        pytest.skip("evidência GDAL local ainda não gerada")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["sentinel_scene"] is False
    assert payload["method"] == "gdal_warp_nearest"
    assert payload["classes_not_blended"] is True
    assert set(payload["values_out"]) <= {4, 8, 9}


def test_windows_follow_as_of_and_widen_when_week_lacks_coverage() -> None:
    as_of = parse_as_of("2026-11-14T18:00:00Z")
    windows = search_windows(as_of)
    assert windows["7d"] == "2026-11-07T18:00:00Z/2026-11-14T18:00:00Z"
    assert windows["30d"].startswith("2026-10-15T18:00:00Z/")
    assert choose_search_window(1) == "7d"
    assert choose_search_window(0) == "30d"
    with pytest.raises(ValueError):
        parse_as_of("2026-11-14T18:00:00")
    source = (REPO / "scripts" / "search_sentinel_pilot.py").read_text(encoding="utf-8")
    assert "--as-of" in source
    assert "2026-11-07T00:00:00Z/2026-11-14T23:59:59Z" not in source


def test_http_401_does_not_name_a_missing_scheme() -> None:
    text = describe_asset_response(
        http_status=401,
        authorization_sent=False,
        scheme_names=["oidc", "s3"],
    )
    assert "401" in text
    assert "oidc" in text
    assert "s3" in text
    assert "não separa os esquemas" in text


def test_maringa_zone_and_mesh_when_present() -> None:
    assert sirgas_utm_epsg(-51.93, -23.42) == 31982
    mesh = REPO / "data" / "raw" / "ibge" / "PR_Municipios_2025.zip"
    if not mesh.is_file():
        pytest.skip("malha IBGE ausente")
    municipality = load_official_municipality(mesh, "4115200")
    catalog = load_pilot_catalog(REPO)
    assert municipality.name == "Maringá"
    assert municipality.cd_mun == "4115200"
    assert municipality.crs == "EPSG:4674"
    assert municipality.geometry_valid is True
    assert municipality.area_km2_official != pytest.approx(61.008)
    assert catalog["aoi"]["area_km2_official"] == pytest.approx(
        municipality.area_km2_official
    )
    assert catalog["aoi"]["bbox"] == pytest.approx(municipality.bbox)
    assert catalog["aoi"]["coverage_crs"] == municipality.coverage_crs


def test_prepare_does_not_publish_even_with_local_files(tmp_path: Path) -> None:
    paths = []
    for name in ("b04.jp2", "b08.jp2", "scl.jp2"):
        path = tmp_path / name
        path.write_bytes(b"not-a-real-jp2")
        paths.append(str(path))
    script = REPO / "scripts" / "prepare_sentinel_pilot.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--b04",
            paths[0],
            "--b08",
            paths[1],
            "--scl",
            paths[2],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "não publica raster" in proc.stderr
    assert "ndvi_published False" in proc.stdout


def test_pinhais_file_is_only_labeled_history() -> None:
    path = (
        REPO
        / "docs"
        / "evidence"
        / "sentinel"
        / "exploracao_pinhais_2026-11-14.json"
    )
    if not path.is_file():
        pytest.skip("diagnóstico histórico de Pinhais não arquivado")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["role"] == "exploracao_anterior"
    assert payload["pilot_aoi"] is False
    assert payload["aoi"]["cd_mun"] == "4119152"
    live = REPO / "data" / "derived" / "sentinel_pinhais_pilot.json"
    assert not live.is_file()
