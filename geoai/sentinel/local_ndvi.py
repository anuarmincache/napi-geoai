"""NDVI local de Maringá. Não baixa JP2, não autentica e não publica o catálogo.

Os seis arquivos já precisam existir. A B04 de 22KCV entra por caminho
explícito. O manifesto só é trocado se a contagem repetir a medição aprovada.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from geoai.sentinel.gdal_blocks import measure_blocks, reflectance_block
from geoai.sentinel.gdal_scene import raster_info, read_window, same_projection
from geoai.sentinel.grid import (
    clip_placement,
    grid_bounds,
    nearest_sample,
    place_array,
    shift_geotransform,
    source_window_for_output,
    window_covering_bounds,
)
from geoai.sentinel.integrity import accept_used_jp2
from geoai.sentinel.ndvi_writer import (
    BLOCK,
    IncrementalDiskWriter,
    assert_window_array_budget,
    run_blocked_ndvi,
)

TILES = ("22KCV", "22KDV")
BANDS = ("B04_10m", "B08_10m", "SCL_20m")
SCALE = 0.0001
OFFSET = -0.1
NODATA = 0
MAX_PIXELS = 20_000_000
APPROVED_N_AOI = 4_876_416
APPROVED_N_VALID = 3_565_350
APPROVED_PIXELS = (3_086_107, 479_243)
APPROVED_OVERLAP = 2_034_052
LOCK_NAME = ".local-ndvi.lock"


def refuse_download(allow_download: bool) -> None:
    """O modo local não tem ramo de transferência."""

    if allow_download:
        raise PermissionError("download_recusado")


def require_approved_measurement(counts: dict[str, Any]) -> None:
    """A medição de Maringá é o único aceite para finalizar o manifesto."""

    pixels = tuple(int(item) for item in counts["pixels_per_tile"])
    approved = (
        int(counts["n_aoi"]) == APPROVED_N_AOI
        and int(counts["n_valid"]) == APPROVED_N_VALID
        and pixels == APPROVED_PIXELS
        and int(counts["overlap_both_valid"]) == APPROVED_OVERLAP
    )
    if not approved:
        raise RuntimeError("contagem_nao_aprovada")


def bind_bands(
    *,
    b04_22kcv: Path,
    b08_22kcv: Path,
    scl_22kcv: Path,
    b04_22kdv: Path,
    b08_22kdv: Path,
    scl_22kdv: Path,
) -> dict[tuple[str, str], Path]:
    """Seis caminhos explícitos. Nenhum checkout vizinho é consultado."""

    return {
        ("22KCV", "B04_10m"): Path(b04_22kcv),
        ("22KCV", "B08_10m"): Path(b08_22kcv),
        ("22KCV", "SCL_20m"): Path(scl_22kcv),
        ("22KDV", "B04_10m"): Path(b04_22kdv),
        ("22KDV", "B08_10m"): Path(b08_22kdv),
        ("22KDV", "SCL_20m"): Path(scl_22kdv),
    }


def claim_output(destination: Path) -> Path:
    """Recusa diretório ocupado e uma segunda execução no mesmo lugar.

    Uma exceção apaga o lock depois do rollback dos arquivos desta tentativa.
    Se o processo morrer, o lock pode ficar. A recuperação é manual: apague
    só `.local-ndvi.lock` quando ele for o único item. Qualquer outro arquivo
    permanece no lugar; a execução seguinte usa outro diretório.
    """

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / LOCK_NAME
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("execucao_concorrente") from exc
    os.close(descriptor)
    others = [item for item in destination.iterdir() if item.name != LOCK_NAME]
    if others:
        lock.unlink()
        raise FileExistsError("saida_ocupada")
    return lock


def _protect_catalog(path: Path, catalog_path: Path | None) -> None:
    if catalog_path is None or not catalog_path.exists():
        return
    if path.resolve() == catalog_path.resolve():
        raise PermissionError("catalogo_protegido")


def validate_local_bands(
    bands: dict[tuple[str, str], Path],
    contracts: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Confere os seis arquivos antes de criar raster de saída."""

    _validate(bands, contracts)


def _validate(
    bands: dict[tuple[str, str], Path],
    contracts: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for tile in TILES:
        for band in BANDS:
            path = bands[(tile, band)]
            if not path.is_file():
                raise FileNotFoundError(path.name)
            contract = contracts[(tile, band)]
            accept_used_jp2(
                path,
                raster_info(path),
                expected_bytes=int(contract["expected_bytes"]),
                checksum=str(contract["checksum"]),
                shape=list(contract["shape"]),
                transform=list(contract["transform"]),
                epsg=int(contract["epsg"]),
            )


def _reader(
    bands: dict[tuple[str, str], Path],
    placements: dict[str, dict[str, Any]],
    output_gt: tuple[float, float, float, float, float, float],
    aoi: np.ndarray,
):
    def read_piece(
        path: Path,
        placement: dict[str, int] | None,
        height: int,
        width: int,
    ):
        canvas = np.zeros((height, width), dtype=np.uint16)
        if placement is None:
            return canvas
        place_array(
            canvas,
            read_window(
                path,
                placement["src_xoff"],
                placement["src_yoff"],
                placement["xsize"],
                placement["ysize"],
            ),
            placement,
        )
        return canvas

    def reader(row0: int, row1: int, col0: int, col1: int):
        height = row1 - row0
        width = col1 - col0
        block_gt = shift_geotransform(output_gt, col0, row0)
        reds = []
        nirs = []
        scls = []
        for tile in TILES:
            reds.append(
                reflectance_block(
                    read_piece(
                        bands[(tile, "B04_10m")],
                        clip_placement(placements[tile]["red"], row0, row1, col0, col1),
                        height,
                        width,
                    ),
                    scale=SCALE,
                    offset=OFFSET,
                    nodata=NODATA,
                )
            )
            nirs.append(
                reflectance_block(
                    read_piece(
                        bands[(tile, "B08_10m")],
                        clip_placement(placements[tile]["nir"], row0, row1, col0, col1),
                        height,
                        width,
                    ),
                    scale=SCALE,
                    offset=OFFSET,
                    nodata=NODATA,
                )
            )
            scl_info = placements[tile]["scl"]
            covered = window_covering_bounds(
                scl_info["geotransform"],
                scl_info["cols"],
                scl_info["rows"],
                grid_bounds(block_gt, width, height),
            )
            if covered is None:
                scls.append(np.zeros((height, width), dtype=np.uint8))
            else:
                scls.append(
                    nearest_sample(
                        read_window(
                            bands[(tile, "SCL_20m")],
                            covered["xoff"],
                            covered["yoff"],
                            covered["xsize"],
                            covered["ysize"],
                        ),
                        covered["geotransform"],
                        block_gt,
                        height,
                        width,
                    )
                )
        return reds, nirs, scls, aoi[row0:row1, col0:col1]

    return reader


def _prepare(
    bands: dict[tuple[str, str], Path],
    contracts: dict[tuple[str, str], dict[str, Any]],
    aoi: np.ndarray,
    output_gt: tuple[float, float, float, float, float, float],
    *,
    allow_download: bool,
    block: int,
) -> tuple[Any, int, int, str, int]:
    refuse_download(allow_download)
    if int(block) != BLOCK:
        raise ValueError("bloco_recusado")
    assert_window_array_budget(BLOCK)
    for tile in TILES:
        for band in BANDS:
            path = bands[(tile, band)]
            if not path.is_file():
                raise FileNotFoundError(path.name)
    from osgeo import gdal

    gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
    _validate(bands, contracts)
    rows = int(aoi.shape[0])
    cols = int(aoi.shape[1])
    if rows * cols > MAX_PIXELS:
        raise RuntimeError("grade_maior_que_o_piloto")
    reference = raster_info(bands[("22KCV", "B04_10m")])
    placements: dict[str, dict[str, Any]] = {}
    for tile in TILES:
        red_info = raster_info(bands[(tile, "B04_10m")])
        nir_info = raster_info(bands[(tile, "B08_10m")])
        scl_info = raster_info(bands[(tile, "SCL_20m")])
        if not same_projection(reference["projection"], red_info["projection"]):
            raise RuntimeError("crs_divergente")
        if not same_projection(reference["projection"], nir_info["projection"]):
            raise RuntimeError("crs_divergente")
        placements[tile] = {
            "red": source_window_for_output(
                red_info["geotransform"],
                red_info["cols"],
                red_info["rows"],
                output_gt,
                cols,
                rows,
            ),
            "nir": source_window_for_output(
                nir_info["geotransform"],
                nir_info["cols"],
                nir_info["rows"],
                output_gt,
                cols,
                rows,
            ),
            "scl": scl_info,
        }
    reader = _reader(bands, placements, output_gt, np.asarray(aoi, dtype=bool))
    return reader, rows, cols, reference["projection"], int(
        contracts[("22KCV", "B04_10m")]["epsg"]
    )


def count_local_scene(
    bands: dict[tuple[str, str], Path],
    contracts: dict[tuple[str, str], dict[str, Any]],
    aoi: np.ndarray,
    output_gt: tuple[float, float, float, float, float, float],
    *,
    allow_download: bool = False,
    block: int = BLOCK,
) -> dict[str, Any]:
    """Conta a cena sem gravar raster e sem finalizar manifesto."""

    reader, rows, cols, _projection, _epsg = _prepare(
        bands,
        contracts,
        aoi,
        output_gt,
        allow_download=allow_download,
        block=block,
    )
    return measure_blocks(reader, rows, cols, block=BLOCK)


def run_local_ndvi(
    bands: dict[tuple[str, str], Path],
    contracts: dict[tuple[str, str], dict[str, Any]],
    aoi: np.ndarray,
    output_gt: tuple[float, float, float, float, float, float],
    destination: Path,
    manifest_path: Path,
    *,
    allow_download: bool = False,
    block: int = BLOCK,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Valida os JP2, grava só na saída local e só então aceita o manifesto."""

    destination = Path(destination)
    manifest_path = Path(manifest_path)
    _protect_catalog(destination, catalog_path)
    _protect_catalog(manifest_path, catalog_path)
    reader, rows, cols, projection, epsg = _prepare(
        bands,
        contracts,
        aoi,
        output_gt,
        allow_download=allow_download,
        block=block,
    )
    lock = claim_output(destination)
    try:
        writer = IncrementalDiskWriter(
            destination,
            rows=rows,
            cols=cols,
            geotransform=output_gt,
            projection=projection,
            epsg=epsg,
            manifest_path=manifest_path,
            block=BLOCK,
        )
        try:
            writer.open()
            counts = run_blocked_ndvi(
                reader,
                rows,
                cols,
                block=BLOCK,
                writer=writer,
            )
            require_approved_measurement(counts)
            per_tile = [int(item) for item in counts["pixels_per_tile"]]
            if per_tile[0] + per_tile[1] != int(counts["n_valid"]):
                raise RuntimeError("soma_das_tiles_divergente")
            return writer.finalize(counts)
        except Exception:
            writer.abort()
            raise
    finally:
        lock.unlink(missing_ok=True)
