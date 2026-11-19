"""Modo local do NDVI. Usa rasters sintéticos e não abre JP2 de Maringá."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from geoai.sentinel.budget import MAX_MEMORY_BYTES
from geoai.sentinel.local_ndvi import (
    APPROVED_N_AOI,
    APPROVED_N_VALID,
    APPROVED_OVERLAP,
    APPROVED_PIXELS,
    LOCK_NAME,
    bind_bands,
    claim_output,
    count_local_scene,
    refuse_download,
    require_approved_measurement,
    run_local_ndvi,
)
from geoai.sentinel.ndvi_writer import BLOCK, assert_window_array_budget

REPO = Path(__file__).resolve().parents[1]
GT = (300000.0, 10.0, 0.0, 7500040.0, 0.0, -10.0)
CATALOG = REPO / "data" / "derived" / "sentinel_maringa_pilot.json"
PAGE = REPO / "app" / "pages" / "8_Sentinel_Piloto.py"


def test_local_sources_stay_offline() -> None:
    module = (REPO / "geoai" / "sentinel" / "local_ndvi.py").read_text(
        encoding="utf-8"
    )
    command = (REPO / "scripts" / "run_maringa_local_ndvi.py").read_text(
        encoding="utf-8"
    )
    for text in (module, command):
        for token in (
            "urlopen",
            "httpx",
            "requests",
            "cdse_auth",
            "NAPI_VALIDATED_B04",
            "os.environ",
            "download_official_asset",
            "--measure-only",
        ):
            assert token not in text
    assert "allow_download=False" in command
    assert '"ndvi_published": False' in (
        REPO / "geoai" / "sentinel" / "ndvi_writer.py"
    ).read_text(encoding="utf-8")


def test_download_and_foreign_block_are_refused() -> None:
    with pytest.raises(PermissionError, match="download_recusado"):
        refuse_download(True)
    with pytest.raises(ValueError, match="bloco_recusado"):
        count_local_scene({}, {}, np.ones((1, 1), dtype=bool), GT, block=8192)
    assert assert_window_array_budget(BLOCK) < MAX_MEMORY_BYTES
    with pytest.raises(MemoryError, match="orcamento_de_arrays_excedido"):
        assert_window_array_budget(8192)


def test_approved_measurement_is_exact() -> None:
    require_approved_measurement(
        {
            "n_aoi": APPROVED_N_AOI,
            "n_valid": APPROVED_N_VALID,
            "pixels_per_tile": list(APPROVED_PIXELS),
            "overlap_both_valid": APPROVED_OVERLAP,
        }
    )
    broken = {
        "n_aoi": APPROVED_N_AOI,
        "n_valid": APPROVED_N_VALID - 1,
        "pixels_per_tile": list(APPROVED_PIXELS),
        "overlap_both_valid": APPROVED_OVERLAP,
    }
    with pytest.raises(RuntimeError, match="contagem_nao_aprovada"):
        require_approved_measurement(broken)


def test_missing_band_does_not_create_output(tmp_path: Path) -> None:
    missing = tmp_path / "B04_10m.jp2"
    bands = bind_bands(
        b04_22kcv=missing,
        b08_22kcv=missing,
        scl_22kcv=missing,
        b04_22kdv=missing,
        b08_22kdv=missing,
        scl_22kdv=missing,
    )
    destination = tmp_path / "saida"
    with pytest.raises(FileNotFoundError):
        run_local_ndvi(
            bands,
            {},
            np.ones((1, 1), dtype=bool),
            GT,
            destination,
            tmp_path / "manifesto.json",
        )
    assert not destination.exists()


def test_occupied_output_and_concurrent_lock_stay_intact(tmp_path: Path) -> None:
    destination = tmp_path / "saida"
    destination.mkdir()
    previous = destination / "ndvi_local_manifest.json"
    previous.write_bytes(b'{"ndvi_published": false}')
    with pytest.raises(FileExistsError, match="saida_ocupada"):
        claim_output(destination)
    assert previous.read_bytes() == b'{"ndvi_published": false}'
    assert not (destination / LOCK_NAME).exists()

    empty = tmp_path / "livre"
    lock = claim_output(empty)
    with pytest.raises(RuntimeError, match="execucao_concorrente"):
        claim_output(empty)
    assert lock.is_file()
    lock.unlink()


def test_catalog_path_cannot_be_the_output(tmp_path: Path) -> None:
    before = CATALOG.read_bytes()
    page = PAGE.read_bytes()
    bands = bind_bands(
        b04_22kcv=tmp_path / "a",
        b08_22kcv=tmp_path / "a",
        scl_22kcv=tmp_path / "a",
        b04_22kdv=tmp_path / "a",
        b08_22kdv=tmp_path / "a",
        scl_22kdv=tmp_path / "a",
    )
    with pytest.raises(PermissionError, match="catalogo_protegido"):
        run_local_ndvi(
            bands,
            {},
            np.ones((1, 1), dtype=bool),
            GT,
            tmp_path / "saida",
            CATALOG,
            catalog_path=CATALOG,
        )
    assert CATALOG.read_bytes() == before
    assert PAGE.read_bytes() == page


def test_measure_only_entrypoint_still_rejects_an_absent_mode() -> None:
    from scripts.run_maringa_sentinel import main

    assert main([]) == 2
    assert main(["--dry-run", "--measure-only"]) == 2


def _projection() -> str:
    pytest.importorskip("osgeo")
    from osgeo import osr

    osr.UseExceptions()
    spatial = osr.SpatialReference()
    spatial.ImportFromEPSG(32722)
    spatial.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return spatial.ExportToWkt()


def _write_raster(path: Path, array: np.ndarray, projection: str) -> None:
    from osgeo import gdal

    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
    dtype = gdal.GDT_Byte if array.dtype == np.uint8 else gdal.GDT_UInt16
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path),
        int(array.shape[1]),
        int(array.shape[0]),
        1,
        dtype,
    )
    dataset.SetGeoTransform(GT)
    dataset.SetProjection(projection)
    dataset.GetRasterBand(1).WriteArray(array)
    dataset.Close()


def _stac_transform() -> list[float]:
    return [GT[1], GT[2], GT[0], GT[4], GT[5], GT[3]]


def _contract(path: Path) -> dict[str, object]:
    digest = hashlib.sha3_256(path.read_bytes()).hexdigest()
    return {
        "expected_bytes": path.stat().st_size,
        "checksum": "1620" + digest,
        "shape": [4, 4],
        "transform": _stac_transform(),
        "epsg": 32722,
    }


def _scene(tmp_path: Path):
    projection = _projection()
    red = np.full((4, 4), 2000, dtype=np.uint16)
    nir_first = np.full((4, 4), 4000, dtype=np.uint16)
    nir_second = np.full((4, 4), 10000, dtype=np.uint16)
    scl = np.full((4, 4), 4, dtype=np.uint8)
    scl_first = scl.copy()
    scl_first[0, 1] = 8
    names = {
        ("22KCV", "B04_10m"): red,
        ("22KCV", "B08_10m"): nir_first,
        ("22KCV", "SCL_20m"): scl_first,
        ("22KDV", "B04_10m"): red,
        ("22KDV", "B08_10m"): nir_second,
        ("22KDV", "SCL_20m"): scl,
    }
    bands = {}
    contracts = {}
    for key, array in names.items():
        path = tmp_path / f"{key[0]}_{key[1]}.tif"
        _write_raster(path, array, projection)
        bands[key] = path
        contracts[key] = _contract(path)
    aoi = np.ones((4, 4), dtype=bool)
    aoi[0, 0] = False
    return bands, contracts, aoi


def test_tampered_band_is_refused_before_output(tmp_path: Path) -> None:
    pytest.importorskip("osgeo")
    bands, contracts, aoi = _scene(tmp_path)
    target = bands[("22KDV", "B08_10m")]
    payload = bytearray(target.read_bytes())
    payload[-1] ^= 0x01
    target.write_bytes(payload)
    destination = tmp_path / "saida"
    before = CATALOG.read_bytes()
    with pytest.raises(PermissionError, match="checksum_oficial_divergente"):
        run_local_ndvi(
            bands,
            contracts,
            aoi,
            GT,
            destination,
            tmp_path / "manifesto.json",
            catalog_path=CATALOG,
        )
    assert not destination.exists()
    assert CATALOG.read_bytes() == before


def test_synthetic_reader_counts_and_keeps_the_previous_manifest(
    tmp_path: Path,
) -> None:
    pytest.importorskip("osgeo")
    bands, contracts, aoi = _scene(tmp_path)
    counted = count_local_scene(bands, contracts, aoi, GT)
    assert counted["n_aoi"] == 15
    assert counted["n_valid"] == 15
    assert counted["pixels_per_tile"] == [14, 1]
    assert counted["overlap_both_valid"] == 14
    assert counted["pixels_per_tile"][0] + counted["pixels_per_tile"][1] == 15
    previous = tmp_path / "manifesto.json"
    previous.write_text('{"ndvi_published": false, "cog": null}\n', encoding="utf-8")
    stored = previous.read_bytes()
    catalog = CATALOG.read_bytes()
    destination = tmp_path / "saida"
    with pytest.raises(RuntimeError, match="contagem_nao_aprovada"):
        run_local_ndvi(
            bands,
            contracts,
            aoi,
            GT,
            destination,
            previous,
            catalog_path=CATALOG,
        )
    assert previous.read_bytes() == stored
    assert CATALOG.read_bytes() == catalog
    assert list(destination.glob("*.tif")) == []
    assert not (destination / LOCK_NAME).exists()
    text = json.dumps(counted)
    assert "CDSE_PASSWORD" not in text


def test_wrong_grid_is_refused_before_output(tmp_path: Path) -> None:
    pytest.importorskip("osgeo")
    bands, contracts, aoi = _scene(tmp_path)
    contracts[("22KCV", "B04_10m")]["shape"] = [5, 5]
    destination = tmp_path / "saida"
    with pytest.raises(PermissionError, match="grade_oficial_divergente"):
        run_local_ndvi(
            bands,
            contracts,
            aoi,
            GT,
            destination,
            tmp_path / "manifesto.json",
        )
    assert not destination.exists()


def test_s2a_catalog_is_refused_before_opening_bands(tmp_path: Path, capsys) -> None:
    from scripts.run_maringa_local_ndvi import main

    names = (
        "b04.jp2",
        "b08kcv.jp2",
        "sclkcv.jp2",
        "b04kdv.jp2",
        "b08kdv.jp2",
        "sclkdv.jp2",
    )
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"nao-aberto")
        paths.append(str(path))
    mesh = tmp_path / "malha.zip"
    mesh.write_bytes(b"nao-aberto")
    catalog = tmp_path / "catalogo.json"
    catalog.write_text(
        json.dumps({"measured_acquisition_id": "S2A_20261109T133231_R081"}),
        encoding="utf-8",
    )
    official = CATALOG.read_bytes()
    code = main(
        [
            "--b04",
            paths[0],
            "--b08-22kcv",
            paths[1],
            "--scl-22kcv",
            paths[2],
            "--b04-22kdv",
            paths[3],
            "--b08-22kdv",
            paths[4],
            "--scl-22kdv",
            paths[5],
            "--mesh",
            str(mesh),
            "--catalog",
            str(catalog),
            "--output",
            str(tmp_path / "saida"),
            "--manifest",
            str(tmp_path / "manifesto.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "passagem_recusada" in captured.err
    assert paths[0] and Path(paths[0]).read_bytes() == b"nao-aberto"
    assert not (tmp_path / "saida").exists()
    assert CATALOG.read_bytes() == official


def test_local_command_stops_when_the_mesh_is_absent(tmp_path: Path) -> None:
    from scripts.run_maringa_local_ndvi import main

    catalog = CATALOG.read_bytes()
    code = main(
        [
            "--b04",
            str(tmp_path / "ausente.jp2"),
            "--b08-22kcv",
            str(tmp_path / "ausente.jp2"),
            "--scl-22kcv",
            str(tmp_path / "ausente.jp2"),
            "--b04-22kdv",
            str(tmp_path / "ausente.jp2"),
            "--b08-22kdv",
            str(tmp_path / "ausente.jp2"),
            "--scl-22kdv",
            str(tmp_path / "ausente.jp2"),
            "--mesh",
            str(tmp_path / "malha.zip"),
            "--catalog",
            str(CATALOG),
            "--output",
            str(tmp_path / "saida"),
            "--manifest",
            str(tmp_path / "manifesto.json"),
        ]
    )
    assert code == 2
    assert CATALOG.read_bytes() == catalog
    assert not (tmp_path / "saida").exists()
