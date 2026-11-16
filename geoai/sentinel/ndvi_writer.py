"""Grava NDVI e proveniência por janela. Não publica o catálogo nem abre JP2.

O manifesto local é o único ponto que passa a apontar para um par novo.
Os dois rasters recebem nomes imutáveis antes disso. Uma falha apaga só
os arquivos criados na tentativa e deixa o manifesto anterior no lugar.
`peak_rss_mb` permanece nulo: este módulo não mede o processo.

Duas execuções no mesmo diretório ficam proibidas. O hard link recusa
substituir um arquivo existente, mas não há trava entre processos: o
rollback ainda apaga o que a própria tentativa criou.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from geoai.processing.ndvi import NDVI_DENOM_EPS, SCL_INVALID
from geoai.processing.safety import atomic_write_json
from geoai.sentinel.budget import MAX_MEMORY_BYTES, block_working_bytes
from geoai.sentinel.gdal_blocks import iter_blocks, measure_blocks
from geoai.sentinel.mosaic_rule import RULE

ALGORITHM = "napi-ndvi-block-writer-1"
TILE_ORDER = ("22KCV", "22KDV")
PUBLISHED_NODATA = -9999.0
BLOCK = 256


def assert_window_array_budget(block: int, n_tiles: int = 2) -> int:
    """Bytes dos arrays de uma janela. Não é medição de RSS do processo."""

    if block < 1 or n_tiles < 1:
        raise ValueError("bloco inválido")
    needed = block_working_bytes(block, n_tiles)
    needed += block * block * 4
    needed += block * block
    if needed > MAX_MEMORY_BYTES:
        raise MemoryError("orcamento_de_arrays_excedido")
    return needed


def reject_invalid_inputs(paths: Sequence[Path]) -> None:
    """Recusa caminho ausente, arquivo vazio ou raster que o GDAL não abre."""

    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path.name)
        if path.stat().st_size <= 0:
            raise ValueError("raster_invalido")
    from osgeo import gdal

    gdal.UseExceptions()
    for path in paths:
        try:
            dataset = gdal.Open(str(path))
        except RuntimeError as exc:
            raise ValueError("raster_invalido") from exc
        if dataset is None:
            raise ValueError("raster_invalido")
        dataset.Close()


def run_blocked_ndvi(
    reader: Any,
    rows: int,
    cols: int,
    *,
    block: int = BLOCK,
    writer: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Reusa `measure_blocks`. O writer recebe só a janela corrente."""

    assert_window_array_budget(block)
    if writer is not None:
        observed = writer

        def _guarded(
            row0: int,
            col0: int,
            ndvi: np.ndarray,
            provenance: np.ndarray,
        ) -> None:
            if ndvi.shape[0] > block or ndvi.shape[1] > block:
                raise MemoryError("janela_acima_do_bloco")
            observed(row0, col0, ndvi, provenance)

        sink: Callable[..., None] | None = _guarded
    else:
        sink = None
    return measure_blocks(reader, rows, cols, block=block, writer=sink)


def place_immutable(partial: Path, target: Path) -> bool:
    """Publica `partial` em `target` sem substituir um arquivo existente.

    O hard link falha se `target` já existe, no Windows e no Linux.
    `os.replace` não serve: ele sobrescreve o destino.
    """

    try:
        os.link(partial, target)
    except FileExistsError:
        partial.unlink()
        return False
    partial.unlink()
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gdal():
    from osgeo import gdal

    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
    return gdal


class IncrementalDiskWriter:
    """Duas grades em disco. Cada chamada grava uma janela e descarta o array."""

    def __init__(
        self,
        destination: Path,
        *,
        rows: int,
        cols: int,
        geotransform: tuple[float, float, float, float, float, float],
        projection: str,
        epsg: int,
        manifest_path: Path,
        block: int = BLOCK,
        stage_hook: Callable[[str], None] | None = None,
    ) -> None:
        self.array_budget_bytes = assert_window_array_budget(block)
        self.destination = Path(destination)
        self.destination.mkdir(parents=True, exist_ok=True)
        self.rows = int(rows)
        self.cols = int(cols)
        self.geotransform = tuple(float(value) for value in geotransform)
        self.projection = projection
        self.epsg = int(epsg)
        self.block = int(block)
        self.manifest_path = Path(manifest_path)
        self.stage_hook = stage_hook
        self._token = uuid.uuid4().hex
        self._existing = {
            path.resolve()
            for path in self.destination.iterdir()
            if path.is_file()
        }
        if self.manifest_path.is_file():
            self._existing.add(self.manifest_path.resolve())
        self._created: list[Path] = []
        self._datasets: list[Any] = []
        self._ndvi_work = self._track(
            self.destination / f".{self._token}.ndvi.work.tif"
        )
        self._prov_work = self._track(
            self.destination / f".{self._token}.prov.work.tif"
        )

    def _track(self, path: Path) -> Path:
        self._created.append(path)
        return path

    def open(self) -> None:
        gdal = _gdal()
        self._datasets.append(
            self._create(
                gdal,
                self._ndvi_work,
                gdal.GDT_Float32,
                PUBLISHED_NODATA,
                PUBLISHED_NODATA,
            )
        )
        self._datasets.append(
            self._create(gdal, self._prov_work, gdal.GDT_Byte, None, 0)
        )

    def _create(
        self,
        gdal: Any,
        path: Path,
        dtype: int,
        nodata: float | None,
        fill: float,
    ):
        dataset = gdal.GetDriverByName("GTiff").Create(
            str(path),
            self.cols,
            self.rows,
            1,
            dtype,
            options=["BIGTIFF=IF_SAFER"],
        )
        if dataset is None:
            raise RuntimeError("geotiff_nao_criado")
        dataset.SetGeoTransform(self.geotransform)
        dataset.SetProjection(self.projection)
        band = dataset.GetRasterBand(1)
        if nodata is not None:
            band.SetNoDataValue(float(nodata))
        band.Fill(fill)
        return dataset

    def __call__(
        self,
        row0: int,
        col0: int,
        ndvi: np.ndarray,
        provenance: np.ndarray,
    ) -> None:
        if ndvi.shape[0] > self.block or ndvi.shape[1] > self.block:
            raise MemoryError("janela_acima_do_bloco")
        stored = np.array(ndvi, dtype=np.float32, copy=True)
        stored[~np.isfinite(stored)] = np.float32(PUBLISHED_NODATA)
        self._datasets[0].GetRasterBand(1).WriteArray(stored, int(col0), int(row0))
        codes = np.array(provenance, dtype=np.uint8, copy=True)
        self._datasets[1].GetRasterBand(1).WriteArray(codes, int(col0), int(row0))

    def _close(self) -> None:
        while self._datasets:
            dataset = self._datasets.pop()
            dataset.FlushCache()
            dataset.Close()

    def abort(self) -> None:
        """Remove só o que esta tentativa criou. Não toca arquivo anterior."""

        self._close()
        for path in self._created:
            if path.resolve() in self._existing or not path.is_file():
                continue
            path.unlink()

    def _to_cog(self, source: Path, target: Path, nodata: float | None) -> None:
        gdal = _gdal()
        options: dict[str, Any] = {
            "format": "COG",
            "creationOptions": ["COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"],
        }
        if nodata is not None:
            options["noData"] = nodata
        dataset = gdal.Translate(
            str(target),
            str(source),
            options=gdal.TranslateOptions(**options),
        )
        if dataset is None:
            raise RuntimeError("cog_nao_gerado")
        dataset.Close()

    def _seal(self, partial: Path, prefix: str) -> tuple[str, str, int]:
        digest = _sha256(partial)
        target = self.destination / f"{prefix}-{digest}.tif"
        created = place_immutable(partial, target)
        if created:
            self._created.append(target)
        if not target.is_file() or _sha256(target) != digest:
            raise RuntimeError("produto_imutavel_divergente")
        return target.name, digest, target.stat().st_size

    def finalize(self, counts: dict[str, Any]) -> dict[str, Any]:
        self._close()
        if self.stage_hook is not None:
            self.stage_hook("before_cog")
        ndvi_cog = self._track(self.destination / f".{self._token}.ndvi.cog.tif")
        prov_cog = self._track(self.destination / f".{self._token}.prov.cog.tif")
        self._to_cog(self._ndvi_work, ndvi_cog, PUBLISHED_NODATA)
        self._to_cog(self._prov_work, prov_cog, None)
        self._ndvi_work.unlink()
        self._prov_work.unlink()
        finite, histogram = _validated_pair(
            ndvi_cog,
            prov_cog,
            counts,
            self.geotransform,
            self.epsg,
            self.block,
        )
        ndvi_name, ndvi_hash, ndvi_bytes = self._seal(ndvi_cog, "ndvi")
        prov_name, prov_hash, prov_bytes = self._seal(prov_cog, "provenance")
        first, second = (int(item) for item in counts["pixels_per_tile"])
        gdal = _gdal()
        payload = {
            "schema": "napi-ndvi-local-manifest-1",
            "algorithm": ALGORITHM,
            "ndvi_published": False,
            "peak_rss_mb": None,
            "peak_rss_status": "not_measured",
            "array_budget_bytes": self.array_budget_bytes,
            "array_budget_note": "orcamento_de_arrays_por_janela",
            "rule": RULE,
            "block": self.block,
            "tile_order": list(TILE_ORDER),
            "scl_invalid": sorted(SCL_INVALID),
            "ndvi_denom_eps": NDVI_DENOM_EPS,
            "nodata": PUBLISHED_NODATA,
            "ndvi_dtype": "float32",
            "provenance_dtype": "uint8",
            "provenance_values": {
                "0": "nao_selecionado",
                "1": TILE_ORDER[0],
                "2": TILE_ORDER[1],
            },
            "rows": self.rows,
            "cols": self.cols,
            "resolution_m": abs(self.geotransform[1]),
            "geotransform": list(self.geotransform),
            "epsg": self.epsg,
            "gdal_version": gdal.VersionInfo("RELEASE_NAME"),
            "counts": {
                "n_aoi": int(counts["n_aoi"]),
                "n_valid": int(counts["n_valid"]),
                "pixels_per_tile": [first, second],
                "overlap_both_valid": int(counts["overlap_both_valid"]),
                "finite_ndvi_pixels": finite,
                "provenance_histogram": histogram,
                "pixel_equation": f"{first} + {second} = {int(counts['n_valid'])}",
                "counters_from": "mascara_antes_do_float32",
            },
            "products": {
                "ndvi": {
                    "name": ndvi_name,
                    "sha256": ndvi_hash,
                    "bytes": ndvi_bytes,
                },
                "provenance": {
                    "name": prov_name,
                    "sha256": prov_hash,
                    "bytes": prov_bytes,
                },
            },
        }
        if self.stage_hook is not None:
            self.stage_hook("before_manifest")
        atomic_write_json(self.manifest_path, payload)
        return payload


def _authority_epsg(dataset: Any) -> str | None:
    spatial = dataset.GetSpatialRef()
    if spatial is None:
        return None
    for target in (None, "PROJCS"):
        code = spatial.GetAuthorityCode(target)
        if code:
            return str(code)
    return None


def _validated_pair(
    ndvi_path: Path,
    provenance_path: Path,
    counts: dict[str, Any],
    geotransform: tuple[float, ...],
    epsg: int,
    block: int,
) -> tuple[int, dict[str, int]]:
    finite = _inspect_ndvi(ndvi_path, geotransform, epsg, block)
    histogram = _inspect_provenance(provenance_path, geotransform, epsg, block)
    expected = [int(item) for item in counts["pixels_per_tile"]]
    if finite != int(counts["n_valid"]):
        raise RuntimeError("contagem_finita_divergente")
    if histogram.get("1", 0) != expected[0] or histogram.get("2", 0) != expected[1]:
        raise RuntimeError("proveniencia_divergente")
    if any(code not in {"0", "1", "2"} for code in histogram):
        raise RuntimeError("proveniencia_divergente")
    return finite, histogram


def _inspect_ndvi(
    path: Path,
    geotransform: tuple[float, ...],
    epsg: int,
    block: int,
) -> int:
    gdal = _gdal()
    dataset = gdal.Open(str(path))
    try:
        _expect_grid(dataset, geotransform, epsg, gdal.GDT_Float32)
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        if nodata is None or abs(float(nodata) - PUBLISHED_NODATA) > 1e-6:
            raise RuntimeError("nodata_divergente")
        _expect_cog(dataset)
        finite = 0
        for row0, row1, col0, col1 in iter_blocks(
            dataset.RasterYSize,
            dataset.RasterXSize,
            block,
        ):
            window = band.ReadAsArray(col0, row0, col1 - col0, row1 - row0)
            data = np.asarray(window, dtype=np.float32)
            valid = np.isfinite(data) & (data != np.float32(PUBLISHED_NODATA))
            finite += int(valid.sum())
        return finite
    finally:
        dataset.Close()


def _inspect_provenance(
    path: Path,
    geotransform: tuple[float, ...],
    epsg: int,
    block: int,
) -> dict[str, int]:
    gdal = _gdal()
    dataset = gdal.Open(str(path))
    try:
        _expect_grid(dataset, geotransform, epsg, gdal.GDT_Byte)
        if dataset.GetRasterBand(1).GetNoDataValue() is not None:
            raise RuntimeError("proveniencia_com_nodata")
        _expect_cog(dataset)
        histogram = {"0": 0, "1": 0, "2": 0}
        band = dataset.GetRasterBand(1)
        for row0, row1, col0, col1 in iter_blocks(
            dataset.RasterYSize,
            dataset.RasterXSize,
            block,
        ):
            window = np.asarray(
                band.ReadAsArray(col0, row0, col1 - col0, row1 - row0),
                dtype=np.uint8,
            )
            for code in np.unique(window):
                key = str(int(code))
                histogram[key] = histogram.get(key, 0) + int((window == code).sum())
        return histogram
    finally:
        dataset.Close()


def _expect_grid(
    dataset: Any,
    geotransform: tuple[float, ...],
    epsg: int,
    dtype: int,
) -> None:
    got = tuple(round(float(value), 6) for value in dataset.GetGeoTransform())
    expected = tuple(round(float(value), 6) for value in geotransform)
    if got != expected:
        raise RuntimeError("geotransform_divergente")
    if _authority_epsg(dataset) != str(epsg):
        raise RuntimeError("crs_divergente")
    if dataset.GetRasterBand(1).DataType != dtype:
        raise RuntimeError("tipo_divergente")


def _expect_cog(dataset: Any) -> None:
    structure = dataset.GetMetadata("IMAGE_STRUCTURE") or {}
    if structure.get("COMPRESSION") != "DEFLATE":
        raise RuntimeError("compressao_divergente")
    if structure.get("LAYOUT") != "COG":
        raise RuntimeError("layout_nao_cog")


def write_local_ndvi_products(
    destination: Path,
    *,
    rows: int,
    cols: int,
    geotransform: tuple[float, float, float, float, float, float],
    projection: str,
    epsg: int,
    reader: Any,
    manifest_path: Path,
    block: int = BLOCK,
    inputs: Sequence[Path] | None = None,
    stage_hook: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Calcula pelas janelas e só então troca o manifesto de referência."""

    if inputs is not None:
        reject_invalid_inputs(inputs)
    writer = IncrementalDiskWriter(
        destination,
        rows=rows,
        cols=cols,
        geotransform=geotransform,
        projection=projection,
        epsg=epsg,
        manifest_path=manifest_path,
        block=block,
        stage_hook=stage_hook,
    )
    try:
        writer.open()
        counts = run_blocked_ndvi(
            reader,
            rows,
            cols,
            block=block,
            writer=writer,
        )
        per_tile = [int(item) for item in counts["pixels_per_tile"]]
        if len(per_tile) != 2 or per_tile[0] + per_tile[1] != int(counts["n_valid"]):
            raise RuntimeError("soma_das_tiles_divergente")
        return writer.finalize(counts)
    except Exception:
        writer.abort()
        raise
