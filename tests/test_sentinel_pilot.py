"""Piloto Sentinel-2: reflectância, triagem e catálogo sem cena publicada."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.sentinel.catalog import load_pilot_catalog, show_ndvi
from geoai.sentinel.reflectance import ReflectanceMetadataError, reflectance_dn
from geoai.sentinel.selection import (
    footprint_coverage,
    rank_full_coverage,
    scene_is_accepted,
)
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


def test_catalog_does_not_publish_ndvi_without_scene() -> None:
    catalog = load_pilot_catalog(REPO)
    assert catalog["ndvi_published"] is False
    assert show_ndvi(catalog) is False
    assert catalog["status"] == "blocked_credentials"


def test_missing_catalog_is_not_zero_ndvi(tmp_path: Path) -> None:
    catalog = load_pilot_catalog(tmp_path)
    assert catalog["ndvi_published"] is False
    assert "Nenhum NDVI" in catalog["public_message_pt"]


def test_streamlit_pilot_does_not_process() -> None:
    text = (REPO / "app" / "pages" / "8_Sentinel_Piloto.py").read_text(encoding="utf-8")
    for token in ("import qgis", "from osgeo", "execute_job", "urlopen", "gdal.Warp"):
        assert token not in text


def test_gdal_nearest_evidence_is_not_a_sentinel_scene() -> None:
    path = REPO / "docs" / "evidence" / "sentinel" / "gdal_nearest_synthetic.json"
    if not path.is_file():
        pytest.skip("evidência GDAL local ainda não gerada")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["sentinel_scene"] is False
    assert payload["method"] == "gdal_warp_nearest"
    assert payload["classes_not_blended"] is True
    assert set(payload["values_out"]) <= {4, 8, 9}
