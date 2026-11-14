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


def municipality_bounds(
    mesh_zip: Path,
    cd_mun: str,
    target_wkt: str,
) -> tuple[float, float, float, float]:
    """Retângulo do município no CRS do raster: minx, miny, maxx, maxy."""

    from osgeo import ogr, osr

    if not cd_mun.isdigit():
        raise ValueError("CD_MUN inválido")
    source = ogr.Open(str(mesh_zip))
    if source is None:
        raise OSError("malha ilegível")
    layer = source.GetLayer(0)
    layer.SetAttributeFilter(f"CD_MUN = '{cd_mun}'")
    feature = layer.GetNextFeature()
    if feature is None:
        raise ValueError("município ausente na malha")
    geometry = feature.GetGeometryRef().Clone()
    source_srs = layer.GetSpatialRef()
    target = osr.SpatialReference()
    target.ImportFromWkt(target_wkt)
    source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geometry.Transform(osr.CoordinateTransformation(source_srs, target))
    minx, maxx, miny, maxy = geometry.GetEnvelope()
    source = None
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

    from osgeo import gdal, ogr, osr

    if not cd_mun.isdigit():
        raise ValueError("CD_MUN inválido")
    gdal.UseExceptions()
    source = ogr.Open(str(mesh_zip))
    if source is None:
        raise OSError("malha ilegível")
    layer = source.GetLayer(0)
    layer.SetAttributeFilter(f"CD_MUN = '{cd_mun}'")
    feature = layer.GetNextFeature()
    if feature is None:
        raise ValueError("município ausente na malha")
    geometry = feature.GetGeometryRef().Clone()
    source_srs = layer.GetSpatialRef()
    target = osr.SpatialReference()
    target.ImportFromWkt(target_wkt)
    source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geometry.Transform(osr.CoordinateTransformation(source_srs, target))
    memory = ogr.GetDriverByName("Memory").CreateDataSource("aoi")
    mask_layer = memory.CreateLayer("aoi", target, ogr.wkbPolygon)
    burned = ogr.Feature(mask_layer.GetLayerDefn())
    burned.SetGeometry(geometry)
    mask_layer.CreateFeature(burned)
    raster = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_Byte)
    raster.SetGeoTransform(geotransform)
    raster.SetProjection(target_wkt)
    gdal.RasterizeLayer(raster, [1], mask_layer, burn_values=[1])
    array = raster.GetRasterBand(1).ReadAsArray()
    source = None
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
        gdal.Translate(str(partial), memory, options=options)
        memory = None
        if not partial.is_file() or partial.stat().st_size <= 0:
            raise OSError("cog vazio")
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return path.stat().st_size
