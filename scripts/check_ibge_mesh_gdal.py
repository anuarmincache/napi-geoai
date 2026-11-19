"""Abre a malha IBGE pelo GDAL e gera a máscara de Maringá.

Executar com python-qgis-ltr.bat. Não baixa Sentinel e não publica NDVI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from osgeo import gdal, ogr, osr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.processing.safety import atomic_write_json  # noqa: E402
from geoai.sentinel.gdal_scene import (  # noqa: E402
    _projected_municipality,
    municipality_bounds,
    ogr_mesh_path,
    rasterize_municipality,
)
from geoai.sentinel.pilot import MESH_RELATIVE, PILOT_CD_MUN  # noqa: E402

OUT = REPO / "docs" / "evidence" / "sentinel" / "ibge_mesh_gdal.json"
BBOX = (-52.1000868, -23.5583336, -51.8358064999999, -23.2539786999999)
MASK_SIZE = 64


def _same_bbox(bounds: tuple[float, float, float, float]) -> bool:
    pairs = zip(bounds, BBOX, strict=True)
    return all(abs(left - right) <= 1e-9 for left, right in pairs)


def _target_wkt() -> str:
    target = osr.SpatialReference()
    target.ImportFromEPSG(4674)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return target.ExportToWkt()


def _layer_matches_4674(opened: str) -> tuple[str, float, bool]:
    official = osr.SpatialReference()
    official.ImportFromEPSG(4674)
    official.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    source = ogr.Open(opened, 0)
    try:
        layer = source.GetLayer(0)
        spatial = layer.GetSpatialRef()
        spatial.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        layer.SetAttributeFilter(f"CD_MUN = '{PILOT_CD_MUN}'")
        feature = layer.GetNextFeature()
        name = str(feature.GetField("NM_MUN"))
        area = float(feature.GetField("AREA_KM2"))
        return name, area, bool(spatial.IsSame(official))
    finally:
        source = None


def main() -> int:
    gdal.UseExceptions()
    mesh = REPO / MESH_RELATIVE
    opened = ogr_mesh_path(mesh)
    member = opened.rsplit("/", 1)[-1]
    target_wkt = _target_wkt()
    geometry, _target = _projected_municipality(mesh, PILOT_CD_MUN, target_wkt)
    bounds = municipality_bounds(mesh, PILOT_CD_MUN, target_wkt)
    minx, miny, maxx, maxy = bounds
    pixel_x = (maxx - minx) / MASK_SIZE
    pixel_y = (maxy - miny) / MASK_SIZE
    geotransform = (minx, pixel_x, 0.0, maxy, 0.0, -pixel_y)
    mask = rasterize_municipality(
        mesh,
        PILOT_CD_MUN,
        geotransform,
        MASK_SIZE,
        MASK_SIZE,
        target_wkt,
    )
    surface = geometry.PointOnSurface()
    sx, sy, _z = surface.GetPoint()
    col = int((sx - geotransform[0]) / geotransform[1])
    row = int((sy - geotransform[3]) / geotransform[5])
    in_grid = 0 <= row < MASK_SIZE and 0 <= col < MASK_SIZE
    inside = bool(mask[row, col]) if in_grid else False
    name, area, same_crs = _layer_matches_4674(opened)
    true_count = int(mask.sum())
    false_count = int(mask.size - true_count)
    payload = {
        "sentinel_scene": False,
        "official_pixels": False,
        "ndvi_published": False,
        "download_started": False,
        "cd_mun": PILOT_CD_MUN,
        "name": name,
        "area_km2_official": area,
        "crs_same_as_epsg_4674": same_crs,
        "geometry_valid": bool(geometry.IsValid()),
        "geometry_type": ogr.GeometryTypeToName(geometry.GetGeometryType()),
        "bbox": [minx, miny, maxx, maxy],
        "member": member,
        "open_path": "vsizip",
        "path_has_backslash": "\\" in opened,
        "mask_shape": [int(mask.shape[0]), int(mask.shape[1])],
        "mask_true": true_count,
        "mask_false": false_count,
        "point_on_surface_inside": inside,
        "gdal": gdal.__version__,
    }
    atomic_write_json(OUT, payload)
    print(OUT)
    print(name, area, same_crs, inside, true_count, false_count)
    checks = [
        name == "Maringá",
        area == 487.912,
        same_crs,
        bool(geometry.IsValid()),
        _same_bbox(bounds),
        opened.startswith("/vsizip/"),
        "\\" not in opened,
        member == "PR_Municipios_2025.shp",
        true_count > 0,
        false_count > 0,
        inside,
        payload["ndvi_published"] is False,
        payload["download_started"] is False,
    ]
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
