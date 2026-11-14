"""Grade, publicação e redirecionamento sem rede e sem segredo."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import pytest
from geoai.sentinel.assets import https_band_urls, official_asset_url
from geoai.sentinel.cdse_auth import (
    RedirectRefused,
    _AssetRedirect,
    _complete_download,
)
from geoai.sentinel.grid import (
    nearest_sample,
    place_array,
    snap_aoi_grid,
    source_window_for_output,
)
from geoai.sentinel.publish import publication_allowed

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
