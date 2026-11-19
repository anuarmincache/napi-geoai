"""Recorte GDAL da AOI. O import de osgeo fica dentro das funções."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def raster_info(path: Path) -> dict[str, Any]:
    from osgeo import gdal

    gdal.UseExceptions()
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None:
        raise OSError("raster ilegível")
    try:
        band = dataset.GetRasterBand(1)
        return {
            "geotransform": tuple(float(item) for item in dataset.GetGeoTransform()),
            "cols": int(dataset.RasterXSize),
            "rows": int(dataset.RasterYSize),
            "projection": dataset.GetProjection() or "",
            "nodata": band.GetNoDataValue(),
        }
    finally:
        dataset.Close()


def read_window(path: Path, xoff: int, yoff: int, xsize: int, ysize: int) -> np.ndarray:
    from osgeo import gdal

    gdal.UseExceptions()
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None:
        raise OSError("raster ilegível")
    try:
        array = dataset.GetRasterBand(1).ReadAsArray(xoff, yoff, xsize, ysize)
    finally:
        dataset.Close()
    if array is None:
        raise OSError("janela vazia")
    return array


def same_projection(left: str, right: str) -> bool:
    from osgeo import osr

    first = osr.SpatialReference()
    second = osr.SpatialReference()
    first.ImportFromWkt(left)
    second.ImportFromWkt(right)
    first.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    second.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return bool(first.IsSame(second))


def ogr_mesh_path(mesh_zip: Path) -> str:
    """Caminho /vsizip/ do shapefile municipal, com barras normais."""

    import zipfile

    archive = Path(mesh_zip).resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)
    with zipfile.ZipFile(archive) as handle:
        members = []
        for name in handle.namelist():
            normalized = name.replace("\\", "/").lstrip("/")
            if (
                "municip" in normalized.lower()
                and normalized.lower().endswith(".shp")
            ):
                members.append(normalized)
    if not members:
        raise FileNotFoundError("shapefile municipal ausente no ZIP")
    if len(members) != 1:
        raise FileNotFoundError("shapefile municipal ambíguo no ZIP")
    return f"/vsizip/{archive.as_posix()}/{members[0]}"


def _projected_municipality(
    mesh_zip: Path,
    cd_mun: str,
    target_wkt: str,
):
    """Geometria oficial no CRS de destino. O código é só dígitos."""

    if not cd_mun.isdigit():
        raise ValueError("CD_MUN inválido")
    from osgeo import gdal, ogr, osr

    gdal.UseExceptions()
    previous = gdal.GetConfigOption("SHAPE_ENCODING")
    gdal.SetConfigOption("SHAPE_ENCODING", "UTF-8")
    source = None
    try:
        source = ogr.Open(ogr_mesh_path(mesh_zip), 0)
    except RuntimeError as exc:
        raise OSError("malha ilegível") from exc
    finally:
        gdal.SetConfigOption("SHAPE_ENCODING", previous)
    if source is None:
        raise OSError("malha ilegível")
    try:
        layer = source.GetLayer(0)
        if layer is None:
            raise OSError("malha sem camada")
        layer.SetAttributeFilter(f"CD_MUN = '{cd_mun}'")
        feature = layer.GetNextFeature()
        if feature is None:
            raise ValueError("município ausente na malha")
        geometry_ref = feature.GetGeometryRef()
        if geometry_ref is None:
            raise ValueError("município sem geometria")
        geometry = geometry_ref.Clone()
        source_srs = layer.GetSpatialRef()
        if source_srs is None:
            raise ValueError("malha sem CRS")
        source_srs = source_srs.Clone()
    finally:
        source = None
    target = osr.SpatialReference()
    target.ImportFromWkt(target_wkt)
    source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geometry.Transform(osr.CoordinateTransformation(source_srs, target))
    return geometry, target


def municipality_bounds(
    mesh_zip: Path,
    cd_mun: str,
    target_wkt: str,
) -> tuple[float, float, float, float]:
    """Retângulo do município no CRS do raster: minx, miny, maxx, maxy."""

    geometry, _target = _projected_municipality(mesh_zip, cd_mun, target_wkt)
    minx, maxx, miny, maxy = geometry.GetEnvelope()
    return float(minx), float(miny), float(maxx), float(maxy)


def rasterize_municipality(
    mesh_zip: Path,
    cd_mun: str,
    geotransform: tuple[float, float, float, float, float, float],
    cols: int,
    rows: int,
    target_wkt: str,
) -> np.ndarray:
    """Máscara 1 no pixel cujo centro cai no município. O código é só dígitos."""

    geometry, target = _projected_municipality(mesh_zip, cd_mun, target_wkt)
    from osgeo import gdal, ogr

    gdal.UseExceptions()
    memory = ogr.GetDriverByName("MEM").CreateDataSource("aoi")
    mask_layer = memory.CreateLayer("aoi", target, geometry.GetGeometryType())
    burned = ogr.Feature(mask_layer.GetLayerDefn())
    burned.SetGeometry(geometry)
    mask_layer.CreateFeature(burned)
    raster = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_Byte)
    raster.SetGeoTransform(geotransform)
    raster.SetProjection(target_wkt)
    gdal.RasterizeLayer(raster, [1], mask_layer, burn_values=[1])
    array = raster.GetRasterBand(1).ReadAsArray()
    memory = None
    raster = None
    if array is None:
        raise OSError("máscara vazia")
    return array.astype(bool)


def write_raster(
    path: Path,
    array: np.ndarray,
    geotransform: tuple[float, float, float, float, float, float],
    projection: str,
    *,
    nodata: float,
) -> int:
    """Escreve um COG em arquivo temporário e só então troca o destino."""

    from osgeo import gdal

    gdal.UseExceptions()
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial.tif")
    staged = path.with_name(path.name + ".new")
    rows, cols = array.shape
    memory = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_Float32)
    memory.SetGeoTransform(geotransform)
    memory.SetProjection(projection)
    band = memory.GetRasterBand(1)
    stored = np.array(array, dtype=np.float32, copy=True)
    invalid = ~np.isfinite(stored)
    stored[invalid] = np.float32(nodata)
    band.WriteArray(stored)
    band.SetNoDataValue(float(nodata))
    band.FlushCache()
    options = gdal.TranslateOptions(
        format="COG",
        creationOptions=["COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"],
    )
    try:
        if path.exists():
            raise FileExistsError("destino_ja_existe")
        gdal.Translate(str(partial), memory, options=options)
        memory = None
        if not partial.is_file() or partial.stat().st_size <= 0:
            raise OSError("cog vazio")
        partial.replace(staged)
        staged.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        staged.unlink(missing_ok=True)
        raise
    return path.stat().st_size
