"""Gravador NDVI sintético. Não abre JP2 nem o catálogo de Maringá."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import numpy as np
import pytest
from geoai.processing.ndvi import SCL_INVALID
from geoai.sentinel.budget import MAX_MEMORY_BYTES
from geoai.sentinel.gdal_blocks import (
    compose_blocked,
    ndvi_pair,
    reflectance_block,
    scl_is_valid,
)
from geoai.sentinel.mosaic_rule import compose_first_valid
from geoai.sentinel.ndvi_writer import (
    ALGORITHM,
    IncrementalDiskWriter,
    _sha256,
    assert_window_array_budget,
    place_immutable,
    reject_invalid_inputs,
    run_blocked_ndvi,
    write_local_ndvi_products,
)

REPO = Path(__file__).resolve().parents[1]
GT = (300000.0, 10.0, 0.0, 7500040.0, 0.0, -10.0)


def test_module_stays_local_and_does_not_allocate_a_full_grid() -> None:
    text = (REPO / "geoai" / "sentinel" / "ndvi_writer.py").read_text(encoding="utf-8")
    for token in (
        "urlopen",
        "httpx",
        "requests",
        "socket",
        "write_raster",
        "sentinel_maringa_pilot",
        "run_maringa_sentinel",
    ):
        assert token not in text
    assert "np.full((" not in text
    assert "np.zeros((" not in text
    assert '"ndvi_published": False' in text


def test_window_budget_stays_under_the_array_ceiling() -> None:
    needed = assert_window_array_budget(256)
    assert needed < MAX_MEMORY_BYTES
    assert needed == assert_window_array_budget(256, 2)


def test_window_budget_rejects_a_block_above_512_mib() -> None:
    with pytest.raises(MemoryError, match="orcamento_de_arrays_excedido"):
        assert_window_array_budget(8192)


def test_known_ndvi_zero_dn_and_invalid_scl() -> None:
    red = np.array([[0.1, 0.2]], dtype=np.float64)
    nir = np.array([[0.3, -0.2]], dtype=np.float64)
    values, valid = ndvi_pair(red, nir)
    assert valid[0, 0] and values[0, 0] == pytest.approx(0.5)
    assert not valid[0, 1]
    reflected = reflectance_block(
        np.array([[0, 2000]]),
        scale=0.0001,
        offset=-0.1,
        nodata=0,
    )
    assert np.isnan(reflected[0, 0])
    classes = np.array(sorted(SCL_INVALID) + [4, 5, 6])
    mask = scl_is_valid(classes)
    assert not mask[: len(SCL_INVALID)].any()
    assert mask[-3:].all()


def test_float32_cast_keeps_the_valid_count() -> None:
    values, valid = ndvi_pair(
        np.array([[0.1, 0.0]]),
        np.array([[0.3, 0.2]]),
    )
    stored = np.array(values, dtype=np.float32, copy=True)
    stored[~np.isfinite(stored)] = np.float32(-9999.0)
    assert int(valid.sum()) == int((stored != np.float32(-9999.0)).sum())


def _scene() -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], np.ndarray]:
    red = [np.full((4, 4), 0.1), np.full((4, 4), 0.1)]
    nir = [np.full((4, 4), 0.3), np.full((4, 4), 0.9)]
    scl = [np.full((4, 4), 4), np.full((4, 4), 4)]
    scl[0][0, 1] = 8
    aoi = np.ones((4, 4), dtype=bool)
    aoi[0, 0] = False
    return red, nir, scl, aoi


def _reader(red, nir, scl, aoi, seen: list[tuple[int, int]]):
    def read(row0: int, row1: int, col0: int, col1: int):
        seen.append((row1 - row0, col1 - col0))
        return (
            [band[row0:row1, col0:col1] for band in red],
            [band[row0:row1, col0:col1] for band in nir],
            [band[row0:row1, col0:col1] for band in scl],
            aoi[row0:row1, col0:col1],
        )

    return read


def test_blocked_windows_match_the_reference_and_do_not_double_count() -> None:
    red, nir, scl, aoi = _scene()
    reference = compose_blocked(red, nir, scl, aoi, block=2)
    direct = compose_first_valid(
        np.stack(
            [
                scl_is_valid(scl[0]) & ndvi_pair(red[0], nir[0])[1],
                scl_is_valid(scl[1]) & ndvi_pair(red[1], nir[1])[1],
            ]
        ),
        np.stack([ndvi_pair(red[0], nir[0])[0], ndvi_pair(red[1], nir[1])[0]]),
        aoi,
    )
    pasted = np.full(aoi.shape, np.nan)
    codes = np.zeros(aoi.shape, dtype=np.uint8)
    seen: list[tuple[int, int]] = []

    def writer(row0: int, col0: int, ndvi: np.ndarray, provenance: np.ndarray) -> None:
        pasted[row0 : row0 + ndvi.shape[0], col0 : col0 + ndvi.shape[1]] = ndvi
        codes[row0 : row0 + provenance.shape[0], col0 : col0 + provenance.shape[1]] = (
            provenance
        )

    counts = run_blocked_ndvi(
        _reader(red, nir, scl, aoi, seen),
        4,
        4,
        block=2,
        writer=writer,
    )
    assert max(seen) == (2, 2)
    assert counts["retained_grid"] is False
    assert np.allclose(pasted, reference["ndvi"], equal_nan=True)
    assert np.array_equal(codes, reference["provenance"])
    assert counts["pixels_per_tile"] == direct["pixels_per_tile"] == [14, 1]
    assert counts["n_aoi"] == 15
    assert counts["n_valid"] == 15
    assert sum(counts["pixels_per_tile"]) == counts["n_valid"]
    overlap = counts["overlap_both_valid"]
    assert overlap == 14
    assert sum(counts["pixels_per_tile"]) - overlap != counts["n_valid"]
    assert codes[0, 0] == 0
    assert codes[0, 1] == 2
    assert set(np.unique(codes)).issubset({0, 1, 2})


def test_place_immutable_does_not_replace_an_existing_file(tmp_path: Path) -> None:
    existing = tmp_path / "ndvi-existente.tif"
    existing.write_bytes(b"original")
    partial = tmp_path / "parcial.tif"
    partial.write_bytes(b"novo")
    created = place_immutable(partial, existing)
    assert created is False
    assert existing.read_bytes() == b"original"
    assert not partial.exists()
    fresh = tmp_path / "ndvi-novo.tif"
    arriving = tmp_path / "chegando.tif"
    arriving.write_bytes(b"dados")
    assert place_immutable(arriving, fresh) is True
    assert fresh.read_bytes() == b"dados"
    assert not arriving.exists()


def test_checksum_failure_removes_the_new_product_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    products = tmp_path / "products"
    products.mkdir()
    previous = products / "ndvi-anterior.tif"
    previous.write_bytes(b"anterior")
    writer = IncrementalDiskWriter(
        products,
        rows=2,
        cols=2,
        geotransform=GT,
        projection="LOCAL",
        epsg=32722,
        manifest_path=tmp_path / "ndvi_local_manifest.json",
        block=2,
    )
    partial = products / "parcial.tif"
    partial.write_bytes(b"novo-produto")
    new_name = f"ndvi-{_sha256(partial)}.tif"
    calls = {"n": 0}
    real = _sha256

    def diverge_on_confirmation(path: Path) -> str:
        calls["n"] += 1
        if calls["n"] >= 2:
            return "f" * 64
        return real(path)

    monkeypatch.setattr(
        "geoai.sentinel.ndvi_writer._sha256",
        diverge_on_confirmation,
    )
    with pytest.raises(RuntimeError, match="produto_imutavel_divergente"):
        writer._seal(partial, "ndvi")
    writer.abort()
    assert previous.read_bytes() == b"anterior"
    assert not (products / new_name).exists()
    assert not (tmp_path / "ndvi_local_manifest.json").exists()


def test_missing_or_empty_input_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "ausente.jp2"
    empty = tmp_path / "vazio.jp2"
    empty.write_bytes(b"")
    with pytest.raises(FileNotFoundError):
        reject_invalid_inputs([missing])
    with pytest.raises(ValueError, match="raster_invalido"):
        reject_invalid_inputs([empty])


def _projection() -> str:
    pytest.importorskip("osgeo")
    from osgeo import osr

    osr.UseExceptions()
    spatial = osr.SpatialReference()
    spatial.ImportFromEPSG(32722)
    spatial.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return spatial.ExportToWkt()


def _write(tmp_path: Path, red, nir, scl, aoi, **kwargs):
    seen: list[tuple[int, int]] = []
    return write_local_ndvi_products(
        tmp_path / "products",
        rows=int(aoi.shape[0]),
        cols=int(aoi.shape[1]),
        geotransform=GT,
        projection=_projection(),
        epsg=32722,
        reader=_reader(red, nir, scl, aoi, seen),
        manifest_path=tmp_path / "ndvi_local_manifest.json",
        **kwargs,
    )


def test_synthetic_cog_pair_is_readable_and_keeps_the_previous_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("osgeo")
    from osgeo import gdal

    def refuse_network(*_args, **_kwargs):
        raise AssertionError("rede")

    monkeypatch.setattr(socket, "socket", refuse_network)
    red, nir, scl, aoi = _scene()
    manifest = _write(tmp_path, red, nir, scl, aoi, block=2)
    assert manifest["ndvi_published"] is False
    assert manifest["peak_rss_mb"] is None
    assert manifest["peak_rss_status"] == "not_measured"
    assert manifest["algorithm"] == ALGORITHM
    assert manifest["array_budget_bytes"] == assert_window_array_budget(2)
    assert manifest["array_budget_bytes"] < MAX_MEMORY_BYTES
    assert manifest["counts"]["pixel_equation"] == "14 + 1 = 15"
    assert manifest["counts"]["finite_ndvi_pixels"] == manifest["counts"]["n_valid"]
    assert manifest["counts"]["counters_from"] == "mascara_antes_do_float32"
    products = tmp_path / "products"
    ndvi_path = products / manifest["products"]["ndvi"]["name"]
    prov_path = products / manifest["products"]["provenance"]["name"]
    dataset = gdal.Open(str(ndvi_path))
    structure = dataset.GetMetadata("IMAGE_STRUCTURE")
    window = dataset.GetRasterBand(1).ReadAsArray()
    dataset.Close()
    assert structure["COMPRESSION"] == "DEFLATE"
    assert structure["LAYOUT"] == "COG"
    assert window[1, 1] == pytest.approx(np.float32(0.5))
    assert window[0, 1] == pytest.approx(np.float32(0.8))
    assert window[0, 0] == pytest.approx(np.float32(-9999.0))
    provenance = gdal.Open(str(prov_path)).ReadAsArray()
    assert provenance[0, 0] == 0
    assert provenance[0, 1] == 2
    assert int((provenance == 1).sum()) == 14
    stored = (tmp_path / "ndvi_local_manifest.json").read_text(encoding="utf-8")
    assert "C:\\Users" not in stored
    assert json.loads(stored)["ndvi_published"] is False
    previous_ndvi = ndvi_path.read_bytes()
    previous_manifest = stored

    def broken(row0: int, row1: int, col0: int, col1: int):
        raise RuntimeError("falha_de_escrita")

    with pytest.raises(RuntimeError, match="falha_de_escrita"):
        write_local_ndvi_products(
            products,
            rows=4,
            cols=4,
            geotransform=GT,
            projection=_projection(),
            epsg=32722,
            reader=broken,
            manifest_path=tmp_path / "ndvi_local_manifest.json",
            block=2,
        )
    assert ndvi_path.read_bytes() == previous_ndvi
    assert (tmp_path / "ndvi_local_manifest.json").read_text(encoding="utf-8") == (
        previous_manifest
    )

    def interrupt(stage: str) -> None:
        if stage == "before_manifest":
            raise RuntimeError("falha_de_finalizacao")

    with pytest.raises(RuntimeError, match="falha_de_finalizacao"):
        _write(tmp_path, red, nir, scl, aoi, block=2, stage_hook=interrupt)
    assert ndvi_path.read_bytes() == previous_ndvi
    assert (tmp_path / "ndvi_local_manifest.json").read_text(encoding="utf-8") == (
        previous_manifest
    )
    assert sorted(path.name for path in products.glob("*.tif")) == [
        ndvi_path.name,
        prov_path.name,
    ]


def test_a_second_product_does_not_replace_the_first(tmp_path: Path) -> None:
    pytest.importorskip("osgeo")
    red, nir, scl, aoi = _scene()
    first = _write(tmp_path, red, nir, scl, aoi, block=2)
    nir[1][:] = 0.5
    second = _write(tmp_path, red, nir, scl, aoi, block=2)
    products = tmp_path / "products"
    assert first["products"]["ndvi"]["name"] != second["products"]["ndvi"]["name"]
    assert (products / first["products"]["ndvi"]["name"]).is_file()
    assert (products / second["products"]["ndvi"]["name"]).is_file()
    current = json.loads(
        (tmp_path / "ndvi_local_manifest.json").read_text(encoding="utf-8")
    )
    assert current["products"]["ndvi"]["sha256"] == second["products"]["ndvi"]["sha256"]
    assert current["ndvi_published"] is False


def test_zero_dn_becomes_nodata_and_cloud_is_excluded(tmp_path: Path) -> None:
    pytest.importorskip("osgeo")
    from osgeo import gdal

    red_dn = np.array([[0, 2000], [2000, 2000]], dtype=np.uint16)
    nir_dn = np.full((2, 2), 4000, dtype=np.uint16)
    red = reflectance_block(red_dn, scale=0.0001, offset=-0.1, nodata=0)
    nir = reflectance_block(nir_dn, scale=0.0001, offset=-0.1, nodata=0)
    scl = [np.full((2, 2), 4), np.full((2, 2), 9)]
    aoi = np.ones((2, 2), dtype=bool)
    manifest = _write(tmp_path, [red, red], [nir, nir], scl, aoi, block=2)
    assert manifest["counts"]["n_valid"] == 3
    assert manifest["counts"]["pixels_per_tile"] == [3, 0]
    assert manifest["counts"]["finite_ndvi_pixels"] == 3
    path = tmp_path / "products" / manifest["products"]["ndvi"]["name"]
    values = gdal.Open(str(path)).ReadAsArray()
    assert values[0, 0] == pytest.approx(np.float32(-9999.0))
    assert values[0, 1] == pytest.approx(np.float32(0.5))


def test_unreadable_raster_is_rejected_before_a_product(tmp_path: Path) -> None:
    pytest.importorskip("osgeo")
    text = tmp_path / "nota.txt"
    text.write_text("nao e raster", encoding="utf-8")
    with pytest.raises(ValueError, match="raster_invalido"):
        reject_invalid_inputs([text])
    red, nir, scl, aoi = _scene()
    with pytest.raises(ValueError, match="raster_invalido"):
        _write(tmp_path, red, nir, scl, aoi, block=2, inputs=[text])
    assert not (tmp_path / "ndvi_local_manifest.json").exists()
    assert list((tmp_path / "products").glob("*.tif")) == []
