"""PNG do NDVI sem rede, sem alterar o GeoTIFF e sem download público."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from geoai.catalog.integrity import verify_integrity
from geoai.catalog.style import ndvi_style
from geoai.preview.ndvi_png import (
    colorize_ndvi,
    compose_legend,
    legend_panel,
    read_rgba_png,
    write_preview_pair,
    write_rgba_png,
)

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "catalog" / "public" / "4115200.json"
INTEGRITY = REPO / "catalog" / "integrity" / "4115200.json"
YELLOW = (244, 224, 77)
GREEN = (27, 94, 32)
GRAY = (122, 122, 122)


def _rgb(image: np.ndarray, row: int = 0, col: int = 0) -> tuple[int, int, int]:
    pixel = image[row, col]
    return (int(pixel[0]), int(pixel[1]), int(pixel[2]))


def test_reference_stops_use_the_catalog_ramp() -> None:
    style = ndvi_style()
    values = np.array([[0.0, 0.2, 0.4, 0.6, 0.8]], dtype=np.float64)
    image, counts = colorize_ndvi(values, style)
    expected = [
        tuple(int(item["hex"][index : index + 2], 16) for index in (1, 3, 5))
        for item in style["stops"]
    ]
    for column, color in enumerate(expected):
        assert _rgb(image, 0, column) == color
        assert image[0, column, 3] == 255
    assert counts["ramp"] == 5
    assert counts["anomalous"] == 0


def test_intervals_and_nodata_follow_the_approved_rules() -> None:
    values = np.array(
        [[-9999.0, -1.0, -0.2, 0.1, 0.9, 1.0, -37.0, 15.8]],
        dtype=np.float32,
    )
    untouched = values.copy()
    image, counts = colorize_ndvi(values)
    assert np.array_equal(values, untouched)
    assert image[0, 0, 3] == 0
    assert _rgb(image, 0, 1) == YELLOW
    assert _rgb(image, 0, 2) == YELLOW
    assert image[0, 3, 3] == 255
    assert _rgb(image, 0, 4) == GREEN
    assert _rgb(image, 0, 5) == GREEN
    assert _rgb(image, 0, 6) == GRAY
    assert _rgb(image, 0, 7) == GRAY
    assert counts["nodata"] == 1
    assert counts["anomalous"] == 2


def test_midpoint_between_the_first_stops_is_deterministic() -> None:
    image, _ = colorize_ndvi(np.array([[0.1]], dtype=np.float64))
    assert _rgb(image) == (220, 219, 69)
    again, _ = colorize_ndvi(np.array([[0.1]], dtype=np.float64))
    assert np.array_equal(image, again)


def test_png_keeps_north_row_first_and_repeats_the_bytes(tmp_path: Path) -> None:
    values = np.array(
        [[0.8, -9999.0], [-1.0, 2.0]],
        dtype=np.float32,
    )
    image, _ = colorize_ndvi(values)
    target = tmp_path / "preview.png"
    write_rgba_png(target, image)
    write_rgba_png(tmp_path / "again.png", image)
    assert (tmp_path / "again.png").read_bytes() == target.read_bytes()
    decoded = read_rgba_png(target)
    assert decoded.shape == (2, 2, 4)
    assert _rgb(decoded, 0, 0) == GREEN
    assert decoded[0, 1, 3] == 0
    assert _rgb(decoded, 1, 0) == YELLOW
    assert _rgb(decoded, 1, 1) == GRAY


def test_legend_adds_a_panel_without_resampling_the_map() -> None:
    style = ndvi_style()
    values = np.full((520, 2), -9999.0, dtype=np.float32)
    values[0, 0] = 0.0
    values[0, 1] = 0.8
    values[-1, 1] = 4.0
    preview, _ = colorize_ndvi(values, style)
    panel = legend_panel(preview.shape[0], style, ("NDVI", "Maringá"))
    framed = compose_legend(preview, panel)
    assert framed.shape[0] == preview.shape[0]
    assert framed.shape[1] == preview.shape[1] + panel.shape[1]
    assert np.array_equal(framed[:, : preview.shape[1]], preview)
    assert np.any(panel[:, :, 0] < 250)


def test_manifest_blocks_publication_and_local_paths(tmp_path: Path) -> None:
    style = ndvi_style()
    column = np.full((520, 1), -9999.0, dtype=np.float32)
    column[0, 0] = 0.4
    preview, counts = colorize_ndvi(column, style)
    manifest = write_preview_pair(
        preview,
        tmp_path / "out",
        style=style,
        identity={
            "ibge": "4115200",
            "name": "Maringá",
            "acquisition_id": "S2B_20261112T133149_R081",
            "image_date": "2026-11-12",
            "image_date_label": "12/11/2026",
            "satellite": "Sentinel-2B",
        },
        source={"filename": "ndvi-demo.tif", "sha256": "abc", "bytes": 4},
        counts=counts,
        orientation="norte_na_primeira_linha",
    )
    assert manifest["ndvi_published"] is False
    assert manifest["public_download"] is False
    assert manifest["source_values_modified"] is False
    text = json.dumps(manifest).lower()
    assert "c:\\" not in text
    assert "onedrive" not in text
    with pytest.raises(FileExistsError, match="destino_ocupado"):
        write_preview_pair(
            preview,
            tmp_path / "out",
            style=style,
            identity={
                "ibge": "4115200",
                "name": "Maringá",
                "acquisition_id": "S2B_20261112T133149_R081",
                "image_date": "2026-11-12",
                "image_date_label": "12/11/2026",
                "satellite": "Sentinel-2B",
            },
            source={"filename": "ndvi-demo.tif", "sha256": "abc", "bytes": 4},
            counts=counts,
            orientation="norte_na_primeira_linha",
        )


def test_catalog_public_downloads_remain_blocked() -> None:
    entry = json.loads(PUBLIC.read_text(encoding="utf-8"))
    record = json.loads(INTEGRITY.read_text(encoding="utf-8"))
    verify_integrity(PUBLIC, record)
    assert entry["ndvi_published"] is False
    assert entry["downloads"]["png"]["available"] is False
    assert entry["downloads"]["geotiff"]["public_download"] is False
    assert entry["downloads"]["json"]["public_download"] is False
