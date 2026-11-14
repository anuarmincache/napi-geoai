"""Piloto Sentinel-2: reflectância, triagem e catálogo sem cena publicada."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pytest
from geoai.sentinel.access import describe_asset_response
from geoai.sentinel.aoi import load_official_municipality, sirgas_utm_epsg
from geoai.sentinel.catalog import load_pilot_catalog, show_ndvi
from geoai.sentinel.cdse_auth import (
    PROBE_BYTES,
    RedirectRefused,
    _GuardedRedirect,
    _NoRedirect,
    authorized_probe,
    classify_probe_response,
)
from geoai.sentinel.gdal_blocks import (
    compose_blocked,
    describe_future_gdal_windows,
    reflectance_block,
)
from geoai.sentinel.mosaic_rule import compose_first_valid
from geoai.sentinel.passes import minimal_covering_tiles, parse_product_id
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
    assert catalog["processing_status"] == "not_evaluated"
    assert catalog["candidate"] is None
    selected = catalog["selected_acquisition"]
    assert selected["dates_combined"] is False
    assert selected["composition"] == "single_acquisition"
    assert selected["covers_threshold"] is True
    assert catalog["quality_approved"] is False
    assert catalog["geometric_candidate_only"] is True
    assert catalog["quality_status"] == "not_evaluated"
    assert catalog["valid_pixel_fraction"] is None
    assert selected["acquisition_id"] == "S2B_20261112T133149_R081"
    assert catalog["fallback_acquisition_id"] == "S2A_20261109T133231_R081"
    assert catalog["overlap_rule"] == "first_valid_tile_in_declared_order"
    sensing = selected["sensing_time"]
    chosen = [tile for tile in selected["tiles"] if tile["selected"]]
    assert chosen
    assert all(sensing in tile["product_id"] for tile in chosen)
    assert len({tile["product_id"].split("_")[2] for tile in chosen}) == 1
    assert catalog["mosaic_required"] is (len(selected["selected_tiles"]) > 1)
    authorized = catalog["asset_access"]["authorized"]
    assert authorized["authorized_attempted"] is False
    assert authorized["bytes_read"] == 0
    assert authorized["body_stored"] is False
    anonymous = catalog["asset_access"]["anonymous_probe"]
    assert anonymous["authorization_sent"] is False
    assert anonymous["body_stored"] is False
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


def test_acquisition_id_does_not_mix_dates() -> None:
    same_a = parse_product_id(
        "S2A_MSIL2A_20261114T133231_N0513_R081_T22KCV_20261114T150000"
    )
    same_b = parse_product_id(
        "S2A_MSIL2A_20261114T133231_N0513_R081_T22KDV_20261114T150100"
    )
    other = parse_product_id(
        "S2B_MSIL2A_20261109T133229_N0513_R081_T22KCV_20261109T160000"
    )
    assert same_a is not None and same_b is not None and other is not None
    assert same_a["acquisition_id"] == same_b["acquisition_id"]
    assert same_a["acquisition_id"] != other["acquisition_id"]


def test_minimal_tile_set_is_one_acquisition_geometry() -> None:
    plan = minimal_covering_tiles(
        {
            "22KCV": box(0, 0, 9, 10),
            "22KDV": box(8, 0, 10, 10),
        },
        box(0, 0, 10, 10),
        0.999,
    )
    assert plan["covers_threshold"] is True
    assert plan["mosaic_required"] is True
    assert plan["selected_tiles"] == ["22KCV", "22KDV"]
    assert plan["union_coverage"] == pytest.approx(1)
    assert plan["overlap_coverage"] == pytest.approx(0.1)
    assert plan["gap"] == pytest.approx(0)


def test_missing_cdse_credentials_do_not_open_the_network(monkeypatch) -> None:
    for name in ("CDSE_USERNAME", "CDSE_PASSWORD", "CDSE_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*_args, **_kwargs):
        raise AssertionError("rede")

    monkeypatch.setattr("geoai.sentinel.cdse_auth.urllib.request.urlopen", refuse)
    report = authorized_probe(
        "https://download.dataspace.copernicus.eu/odata/v1/Products(x)/$value"
    )
    assert report["authorized_attempted"] is False
    assert report["bytes_read"] == 0
    assert report["access_status"] == "blocked_auth"
    assert "access_token" not in json.dumps(report)


def test_overlap_uses_first_valid_tile_once() -> None:
    valid = np.zeros((2, 2, 2), dtype=bool)
    values = np.full((2, 2, 2), np.nan)
    valid[:, :, :] = True
    valid[0, :, 1] = False
    values[0] = 0.2
    values[1] = 0.8
    aoi = np.ones((2, 2), dtype=bool)
    result = compose_first_valid(valid, values, aoi)
    assert result["n_aoi"] == 4
    assert result["n_valid"] == 4
    assert sum(result["pixels_per_tile"]) == result["n_valid"]
    assert result["pixels_per_tile"] == [2, 2]
    assert result["overlap_both_valid"] == 2
    assert result["provenance"][0, 0] == 1
    assert result["provenance"][0, 1] == 2
    assert result["ndvi"][0, 0] == pytest.approx(0.2)
    assert result["ndvi"][0, 1] == pytest.approx(0.8)


def test_blocked_windows_do_not_average_tiles() -> None:
    red = [np.full((2, 2), 0.1), np.full((2, 2), 0.1)]
    nir = [np.full((2, 2), 0.3), np.full((2, 2), 0.5)]
    scl = [np.full((2, 2), 4), np.full((2, 2), 4)]
    scl[0][:, 1] = 9
    aoi = np.ones((2, 2), dtype=bool)
    result = compose_blocked(red, nir, scl, aoi, block=1)
    assert result["pixels_per_tile"] == [2, 2]
    assert sum(result["pixels_per_tile"]) == result["n_valid"]
    assert result["ndvi"][0, 0] == pytest.approx((0.3 - 0.1) / (0.3 + 0.1))
    assert result["ndvi"][0, 1] == pytest.approx((0.5 - 0.1) / (0.5 + 0.1))


def test_nodata_does_not_receive_offset_in_block() -> None:
    out = reflectance_block(np.array([[0, 2000]]), scale=0.0001, offset=-0.1, nodata=0)
    assert np.isnan(out[0, 0])
    assert out[0, 1] == pytest.approx(0.1)


OFFICIAL_VALUE = (
    "https://download.dataspace.copernicus.eu/odata/v1/Products(a)/$value"
)


def _probe_request() -> urllib.request.Request:
    return urllib.request.Request(
        OFFICIAL_VALUE,
        headers={
            "Authorization": "Bearer local-test",
            "Range": "bytes=0-1023",
            "Cookie": "session=local",
        },
    )


def test_redirect_to_another_host_drops_authorization() -> None:
    with pytest.raises(RedirectRefused) as caught:
        _GuardedRedirect().redirect_request(
            _probe_request(),
            None,
            302,
            "found",
            {},
            "https://evil.example/odata/v1/Products(a)/$value",
        )
    assert str(caught.value) == "redirect_recusado"
    assert "local-test" not in str(caught.value)


@pytest.mark.parametrize(
    "code,destination",
    [
        (302, "https://evil.example/odata/v1/Products(a)/$value"),
        (302, OFFICIAL_VALUE + "?token=local-test"),
        (302, "http://download.dataspace.copernicus.eu/odata/v1/Products(a)/$value"),
        (302, "https://download.dataspace.copernicus.eu/odata/v1/Products(a)"),
        (302, OFFICIAL_VALUE + "#fragment"),
        (
            302,
            "https://user:local-test@download.dataspace.copernicus.eu"
            "/odata/v1/Products(a)/$value",
        ),
        (300, OFFICIAL_VALUE),
        (304, OFFICIAL_VALUE),
    ],
)
def test_unsafe_redirects_are_refused(code: int, destination: str) -> None:
    with pytest.raises(RedirectRefused) as caught:
        _GuardedRedirect().redirect_request(
            _probe_request(),
            None,
            code,
            "redirect",
            {},
            destination,
        )
    assert "local-test" not in str(caught.value)
    assert "Authorization" not in str(caught.value)


def test_official_redirect_forwards_only_authorization_and_range() -> None:
    redirected = _GuardedRedirect().redirect_request(
        _probe_request(),
        None,
        307,
        "temporary",
        {},
        OFFICIAL_VALUE,
    )
    assert redirected is not None
    assert redirected.full_url == OFFICIAL_VALUE
    assert redirected.get_header("Authorization") == "Bearer local-test"
    assert redirected.get_header("Range") == "bytes=0-1023"
    assert redirected.get_header("Cookie") is None
    assert redirected.get_method() == "GET"


def test_token_endpoint_refuses_every_redirect() -> None:
    with pytest.raises(RedirectRefused) as caught:
        _NoRedirect().redirect_request(
            urllib.request.Request(
                "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
                "protocol/openid-connect/token",
                headers={"Authorization": "Bearer local-test"},
                method="POST",
            ),
            None,
            302,
            "found",
            {},
            OFFICIAL_VALUE,
        )
    assert str(caught.value) == "redirect_recusado"


def test_range_response_must_stay_small() -> None:
    honored = classify_probe_response(
        http_status=206,
        content_range="bytes 0-1023/999999",
        content_length="1024",
        bytes_read=1024,
    )
    unknown_total = classify_probe_response(
        http_status=206,
        content_range="bytes 0-1023/*",
        content_length=None,
        bytes_read=PROBE_BYTES,
    )
    short_object = classify_probe_response(
        http_status=206,
        content_range="bytes 0-511/512",
        content_length="512",
        bytes_read=512,
    )
    ignored = classify_probe_response(
        http_status=200,
        content_range=None,
        content_length="120000000",
        bytes_read=1024,
    )
    assert honored["access_status"] == "authorized"
    assert honored["range_honored"] is True
    assert unknown_total["range_honored"] is True
    assert short_object["range_honored"] is True
    assert short_object["access_status"] == "authorized"
    assert ignored["access_status"] == "range_not_honored"
    assert ignored["range_honored"] is False
    assert ignored["bytes_read"] == 1024


@pytest.mark.parametrize(
    ("status", "content_range", "content_length", "bytes_read", "access", "honored"),
    [
        (206, "bytes 0-1023/1024", "1024", 1024, "authorized", True),
        (206, "bytes 0-1023/999999", "999999", 1024, "range_not_honored", False),
        (206, "bytes 0-1023/999999", "1024", 100, "range_not_honored", False),
        (206, "bytes 1-1024/999999", "1024", 1024, "range_not_honored", False),
        (206, "bytes 0-2047/999999", "2048", 1024, "range_not_honored", False),
        (206, "bytes 0-500/999999", "501", 501, "range_not_honored", False),
        (206, "bytes 0-1023/100", "1024", 1024, "range_not_honored", False),
        (206, "bytes 0-1023", "1024", 1024, "range_not_honored", False),
        (206, None, "1024", 1024, "range_not_honored", False),
        (206, "bytes 0-1023/999999", "1024abc", 1024, "range_not_honored", False),
        (200, "bytes 0-1023/999999", "1024", 1024, "range_not_honored", False),
        (200, None, "100", 100, "range_not_honored", False),
        (200, None, "1024", 0, "range_not_honored", False),
        (401, "bytes 0-1023/999999", "1024", 0, "blocked_auth", False),
        (403, None, None, 0, "blocked_auth", False),
        (416, "bytes */999999", None, 0, "blocked_auth", False),
    ],
)
def test_content_range_must_match_the_requested_interval(
    status: int,
    content_range: str | None,
    content_length: str | None,
    bytes_read: int,
    access: str,
    honored: bool,
) -> None:
    report = classify_probe_response(
        http_status=status,
        content_range=content_range,
        content_length=content_length,
        bytes_read=bytes_read,
    )
    assert report["access_status"] == access
    assert report["range_honored"] is honored
    assert report["bytes_read"] == bytes_read


def test_compose_blocked_still_holds_full_arrays() -> None:
    plan = describe_future_gdal_windows()
    assert plan["compose_blocked_memory"] == "full_arrays"
    assert plan["future_read"].startswith("ReadAsArray")
    assert plan["future_write"].startswith("WriteArray")
    assert plan["download"] == "not_executed"
    assert plan["ndvi_published"] == "false"
    assert "arrays já inteiros" in (compose_blocked.__doc__ or "")


def test_gdal_mosaic_evidence_is_not_a_sentinel_scene() -> None:
    path = REPO / "docs" / "evidence" / "sentinel" / "gdal_mosaic_synthetic.json"
    if not path.is_file():
        pytest.skip("evidência GDAL do mosaico ainda não gerada")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["sentinel_scene"] is False
    assert payload["ndvi_published"] is False
    assert payload["quality_approved_for_pilot"] is False
    assert sum(payload["pixels_per_tile"]) == payload["n_valid"]
    assert payload["n_valid"] <= payload["n_aoi"]


def test_odata_url_with_query_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("CDSE_ACCESS_TOKEN", "local-test-token")
    with pytest.raises(ValueError):
        authorized_probe(
            "https://download.dataspace.copernicus.eu/odata/v1/x?sig=secret"
        )
