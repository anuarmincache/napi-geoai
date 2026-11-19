"""Visualizador local: catálogo real, arquivos conferidos e downloads fechados."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from geoai.catalog.entry import download_menu
from geoai.catalog.integrity import canonical_json, sha256_file
from geoai.preview.ndvi_png import write_rgba_png
from geoai.viewer.config import load_config
from geoai.viewer.map_html import build_map_html
from geoai.viewer.policy import local_downloads_enabled, public_downloads_enabled
from geoai.viewer.session import build_product, load_index, scientific_panel

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "catalog" / "public" / "4115200.json"
VIEWER_ROOT = REPO / "geoai" / "viewer"
EXAMPLE = REPO / "config" / "viewer.local.example.json"


def _sha(path: Path) -> str:
    return sha256_file(path)


def test_versioned_viewer_has_no_local_machine_path() -> None:
    sources = list(VIEWER_ROOT.glob("*.py"))
    sources.append(REPO / "local_viewer" / "app.py")
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources).lower()
    assert "c:\\" not in text
    assert "onedrive" not in text
    assert "área de trabalho" not in text
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert example["science_dir"] == ""
    assert example["preview_dir"] == ""
    assert example["local_test_downloads"] is False


def test_catalog_lists_only_maringa_and_blocks_public_downloads() -> None:
    before = _sha(PUBLIC)
    index = load_index(REPO, None, None)
    assert _sha(PUBLIC) == before
    assert index.errors == ()
    assert [(item.ibge, item.name, item.image_date) for item in index.products] == [
        ("4115200", "Maringá", "2026-11-12")
    ]
    product = index.products[0]
    panel = scientific_panel(product)
    assert panel["n_aoi"] == 4_876_416
    assert panel["n_valid"] == 3_565_350
    assert panel["anomalous"] == 686
    assert panel["quality_status"] == "approved_with_reservations"
    assert panel["ndvi_published"] is False
    assert panel["public_downloads"] == []
    assert download_menu(product.entry) == []
    assert public_downloads_enabled() is False
    assert product.catalog_files["png"].exists is False
    assert product.catalog_files["png"].published is False
    assert product.catalog_files["geotiff"].published is False
    assert product.map_ready is False
    assert "configuracao_ausente" in product.block_reasons
    assert [item.image_date for item in product.dates] == ["2026-11-12"]


def test_download_policy_requires_loopback_and_explicit_flag() -> None:
    assert local_downloads_enabled(False, "127.0.0.1") is False
    assert local_downloads_enabled(True, "0.0.0.0") is False
    assert local_downloads_enabled(True, "localhost") is False
    assert local_downloads_enabled(True, None) is False
    assert local_downloads_enabled(True, "127.0.0.1") is True


def test_config_reads_environment_without_a_default_path() -> None:
    assert load_config({}) is None
    with pytest.raises(ValueError, match="configuracao_incompleta"):
        load_config({"NAPI_NDVI_SCIENCE_DIR": "science"})


def test_map_html_keeps_north_up_and_uses_no_network(tmp_path: Path) -> None:
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    image[0, 0] = (244, 224, 77, 255)
    target = tmp_path / "preview.png"
    write_rgba_png(target, image)
    page = build_map_html(
        target.read_bytes(),
        {
            "width": 2,
            "height": 2,
            "geotransform": (0.0, 10.0, 0.0, 100.0, 0.0, -10.0),
            "epsg": "32722",
            "stops": (
                {"value": 0.0, "hex": "#F4E04D", "label": "0,0"},
                {"value": 0.8, "hex": "#1B5E20", "label": "0,8"},
            ),
            "gray": "#7A7A7A",
            "note": "Escala de visualização.",
            "title": "NDVI",
            "place": "Maringá — PR",
            "date_label": "12/11/2026",
            "acquisition": "S2B_20261112T133149_R081",
            "resolution": "10 m",
        },
    )
    head = page.split("base64,", 1)[0]
    assert "http://" not in head
    assert "https://" not in head
    assert "function fit()" in page
    assert "imageSmoothingEnabled = false" in page
    assert "setTransform(view.scale, 0, 0, view.scale, view.x, view.y)" in page
    assert "387690" not in page
    assert '"-10.0"' in page or "-10.0" in page
    assert "#F4E04D" in page
    assert "#1B5E20" in page
    assert "pouca vegetação" in page
    assert "valor anômalo" in page
    assert "sem dado" in page
    assert "zoom-in" in page


def test_legend_keeps_the_official_colors_and_plain_labels(tmp_path: Path) -> None:
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    target = tmp_path / "preview.png"
    write_rgba_png(target, image)
    stops = (
        {"value": 0.0, "hex": "#F4E04D", "label": "0,0"},
        {"value": 0.2, "hex": "#C5D63D", "label": "0,2"},
        {"value": 0.4, "hex": "#7CB342", "label": "0,4"},
        {"value": 0.6, "hex": "#2E7D32", "label": "0,6"},
        {"value": 0.8, "hex": "#1B5E20", "label": "0,8"},
    )
    page = build_map_html(
        target.read_bytes(),
        {
            "width": 2,
            "height": 2,
            "geotransform": (0.0, 10.0, 0.0, 100.0, 0.0, -10.0),
            "epsg": "32722",
            "stops": stops,
            "gray": "#7A7A7A",
            "note": "nota técnica que não deve dominar a legenda",
            "title": "NDVI",
            "place": "Maringá — PR",
            "date_label": "12/11/2026",
            "acquisition": "S2B_20261112T133149_R081",
            "resolution": "10 m",
        },
    )
    for stop in stops:
        assert stop["hex"] in page
    assert "NDVI muito baixo" in page
    assert "NDVI baixo" in page
    assert "NDVI intermediário" in page
    assert "NDVI elevado" in page
    assert "NDVI muito elevado" in page
    assert "amarelo inicial" in page
    assert "verde final" in page
    assert "não classifica" in page
    sources = (REPO / "local_viewer" / "app.py").read_text(encoding="utf-8")
    sources += (REPO / "geoai" / "viewer" / "map_html.py").read_text(encoding="utf-8")
    assert "73,11% de cobertura vegetal" not in sources
    assert "Dados utilizáveis" in sources
    with pytest.raises(ValueError, match="orientacao_recusada"):
        build_map_html(
            target.read_bytes(),
            {
                "width": 2,
                "height": 2,
                "geotransform": (0.0, 10.0, 0.0, 100.0, 0.0, 10.0),
                "epsg": "32722",
                "stops": ({"value": 0.0, "hex": "#F4E04D", "label": "0,0"},),
                "gray": "#7A7A7A",
                "note": "nota",
                "title": "NDVI",
                "place": "Maringá — PR",
                "date_label": "12/11/2026",
                "acquisition": "S2B",
                "resolution": "10 m",
            },
        )


def _product_fixture(
    tmp_path: Path, *, south_up: bool = False, corrupt_png: bool = False
):
    entry = json.loads(PUBLIC.read_text(encoding="utf-8"))
    entry = copy.deepcopy(entry)
    preview = np.zeros((2, 2, 4), dtype=np.uint8)
    legend = np.zeros((2, 6, 4), dtype=np.uint8)
    preview_path = tmp_path / "preview" / "ndvi-preview.png"
    legend_path = tmp_path / "preview" / "ndvi-preview-with-legend.png"
    preview_path.parent.mkdir(parents=True)
    write_rgba_png(preview_path, preview)
    write_rgba_png(legend_path, legend)
    preview_bytes = preview_path.read_bytes()
    legend_bytes = legend_path.read_bytes()
    if corrupt_png:
        preview_path.write_bytes(preview_bytes + b"\x00")
    cog = tmp_path / "science" / "ndvi-demo.tif"
    provenance = tmp_path / "science" / "provenance-demo.tif"
    cog.parent.mkdir(parents=True)
    cog.write_bytes(b"cog")
    provenance.write_bytes(b"prov")
    transform = [0.0, 10.0, 0.0, 100.0, 0.0, 10.0 if south_up else -10.0]
    entry["grid"] = {"rows": 2, "cols": 2, "geotransform": transform}
    entry["counts"]["n_aoi"] = 4
    entry["counts"]["n_valid"] = 3
    entry["counts"]["pixel_equation"] = "2 + 1 = 3"
    entry["quality"]["outside_unit_interval"]["count"] = 0
    entry["downloads"]["geotiff"]["filename"] = cog.name
    entry["downloads"]["geotiff"]["sha256"] = hashlib.sha256(b"cog").hexdigest()
    entry["downloads"]["geotiff"]["bytes"] = 3
    entry["acquisitions"].append(
        {
            "acquisition_id": "S2A_20200101T000000_R001",
            "image_date": "2020-01-01",
            "role": "historico",
            "quality_status": "approved_with_reservations",
            "algorithm_version": entry["algorithm"]["version"],
            "publication_state": "nao_publicado",
            "valid_pixel_fraction": 0.0,
        }
    )
    science = {
        "schema": "napi-ndvi-local-manifest-1",
        "ndvi_published": False,
        "algorithm": entry["algorithm"]["version"],
        "rows": 2,
        "cols": 2,
        "geotransform": transform,
        "epsg": 32722,
        "counts": {"n_aoi": 4, "n_valid": 3, "pixel_equation": "2 + 1 = 3"},
        "products": {
            "ndvi": {
                "name": cog.name,
                "sha256": hashlib.sha256(b"cog").hexdigest(),
                "bytes": 3,
            },
            "provenance": {
                "name": provenance.name,
                "sha256": hashlib.sha256(b"prov").hexdigest(),
                "bytes": 4,
            },
        },
    }
    png_manifest = {
        "schema": "napi-ndvi-png-preview-1",
        "ndvi_published": False,
        "public_download": False,
        "source_values_modified": False,
        "orientation": "norte_na_primeira_linha",
        "style_id": "ndvi-yellow-green-v1",
        "stops": entry["style"]["stops"],
        "acquisition_id": entry["acquisition_id"],
        "image_date": entry["image_date"],
        "municipality": {"ibge": entry["municipality"]["ibge"]},
        "counts": {"anomalous": 0},
        "source_cog": {
            "sha256": science["products"]["ndvi"]["sha256"],
            "bytes": 3,
            "width": 2,
            "height": 2,
            "geotransform": transform,
            "epsg": "32722",
        },
        "images": {
            "ndvi-preview.png": {
                "sha256": hashlib.sha256(preview_bytes).hexdigest(),
                "bytes": len(preview_bytes),
                "width": 2,
                "height": 2,
            },
            "ndvi-preview-with-legend.png": {
                "sha256": hashlib.sha256(legend_bytes).hexdigest(),
                "bytes": len(legend_bytes),
                "width": 6,
                "height": 2,
            },
        },
    }
    (tmp_path / "science" / "ndvi_local_manifest.json").write_bytes(
        canonical_json(science)
    )
    (tmp_path / "preview" / "ndvi_png_manifest.json").write_bytes(
        canonical_json(png_manifest)
    )
    return entry, tmp_path / "science", tmp_path / "preview"


def test_local_product_uses_manifest_numbers_and_lists_no_extra_city(
    tmp_path: Path,
) -> None:
    entry, science, preview = _product_fixture(tmp_path)
    before = _sha(PUBLIC)
    product = build_product(
        entry, catalog_path=PUBLIC, science_dir=science, preview_dir=preview
    )
    assert _sha(PUBLIC) == before
    assert product.map_ready is True
    assert product.numbers_confirmed is True
    assert scientific_panel(product)["n_valid"] == 3
    assert scientific_panel(product)["image_date"] == "2026-11-12"
    assert [item.image_date for item in product.dates] == ["2026-11-12", "2020-01-01"]
    assert product.dates[1].loaded is False
    assert product.name == "Maringá"
    assert product.local_files["csv"].exists is False
    assert product.local_files["png"].validated is True
    assert product.local_files["png"].published is False
    assert "png" in product.download_paths
    assert product.catalog_files["png"].exists is False


def test_corrupt_png_and_south_up_grid_block_the_map(tmp_path: Path) -> None:
    entry, science, preview = _product_fixture(tmp_path, corrupt_png=True)
    product = build_product(
        entry, catalog_path=PUBLIC, science_dir=science, preview_dir=preview
    )
    assert product.map_ready is False
    assert "png_nao_validado" in product.block_reasons
    assert "png" not in product.download_paths

    south_entry, south_science, south_preview = _product_fixture(
        tmp_path / "south", south_up=True
    )
    south = build_product(
        south_entry,
        catalog_path=PUBLIC,
        science_dir=south_science,
        preview_dir=south_preview,
    )
    assert south.map_ready is False
    assert "orientacao_divergente" in south.block_reasons


def test_real_maringa_files_match_and_remain_unchanged() -> None:
    science = os.environ.get("NAPI_NDVI_SCIENCE_DIR", "").strip()
    preview = os.environ.get("NAPI_NDVI_PREVIEW_DIR", "").strip()
    if not science or not preview:
        pytest.skip("produtos locais não configurados")
    science_dir = Path(science)
    preview_dir = Path(preview)
    catalog = json.loads(PUBLIC.read_text(encoding="utf-8"))
    watched = [
        PUBLIC,
        science_dir / "ndvi_local_manifest.json",
        preview_dir / "ndvi_png_manifest.json",
        science_dir / catalog["downloads"]["geotiff"]["filename"],
        preview_dir / "ndvi-preview.png",
        preview_dir / "ndvi-preview-with-legend.png",
    ]
    before = {path.name: _sha(path) for path in watched}
    index = load_index(REPO, science_dir, preview_dir)
    assert {path.name: _sha(path) for path in watched} == before
    product = index.products[0]
    assert product.map_ready is True
    assert product.map_spec is not None
    assert (product.map_spec.width, product.map_spec.height) == (2686, 3373)
    assert product.map_spec.geotransform[5] < 0
    panel = scientific_panel(product)
    assert panel["n_aoi"] == 4_876_416
    assert panel["n_valid"] == 3_565_350
    assert panel["anomalous"] == 686
    assert panel["ndvi_published"] is False
    assert panel["public_downloads"] == []
    assert product.local_files["csv"].reason == "nao_gerado"
    assert product.catalog_files["png"].exists is False
    assert product.numbers_confirmed is True


def test_streamlit_page_renders_maringa_without_local_files() -> None:
    streamlit = pytest.importorskip("streamlit.testing.v1")
    names = (
        "NAPI_NDVI_VIEWER_CONFIG",
        "NAPI_NDVI_SCIENCE_DIR",
        "NAPI_NDVI_PREVIEW_DIR",
        "NAPI_NDVI_LOCAL_TEST_DOWNLOADS",
    )
    saved = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ.pop(name, None)
    try:
        app = streamlit.AppTest.from_file(str(REPO / "local_viewer" / "app.py"))
        app.run(timeout=30)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    assert not app.exception
    text = " ".join(item.value for item in app.markdown)
    assert "Observatório de Vegetação" in text
    assert "Ambiente local de testes" in text
    notices = " ".join(item.value for item in app.info)
    assert "não estão disponíveis para download" in notices
    assert "Catálogo público" not in text
    assert "Arquivos nesta máquina" not in text
    assert "ndvi_published" not in text
    assert "ndvi_published" not in notices
    assert app.download_button == []
    captions = " ".join(item.value for item in app.caption)
    assert "dados utilizáveis, não de vegetação" in captions
    warnings = " ".join(item.value for item in app.warning)
    assert "não indicam vegetação" in warnings
    titles = [item.label for item in app.expander]
    assert "Como interpretar o NDVI?" in titles
    assert "Nota científica do catálogo" not in titles
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Município"] == "Maringá — PR"
    assert metrics["Data"] == "12/11/2026"
    assert metrics["Satélite"] == "Sentinel-2B"
    assert metrics["Resolução"] == "10 m"
    assert metrics["Pixels válidos"] == "3.565.350"
    assert metrics["Dados utilizáveis"] == "73,11%"
    assert metrics["Qualidade"] == "Aprovado com ressalvas"
    assert app.sidebar.selectbox[0].options == ["Maringá — PR (4115200)"]
    assert app.sidebar.selectbox[2].options == ["NDVI"]
    sidebar = " ".join(item.value for item in app.sidebar.markdown)
    assert "Aprovado com ressalvas" in sidebar
    assert app.error
