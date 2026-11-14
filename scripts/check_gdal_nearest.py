"""Nearest georreferenciado em grade sintética. Não é cena Sentinel.

Executar com python-qgis-ltr.bat.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from osgeo import gdal, osr

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "evidence" / "sentinel" / "gdal_nearest_synthetic.json"


def main() -> int:
    gdal.UseExceptions()
    started = time.perf_counter()
    driver = gdal.GetDriverByName("MEM")
    source = driver.Create("", 2, 2, 1, gdal.GDT_Byte)
    source.SetGeoTransform((600000.0, 20.0, 0.0, 7200000.0, 0.0, -20.0))
    spatial = osr.SpatialReference()
    spatial.ImportFromEPSG(32722)
    source.SetProjection(spatial.ExportToWkt())
    band = source.GetRasterBand(1)
    band.WriteRaster(0, 0, 2, 2, bytes([4, 8, 9, 4]))
    band.SetNoDataValue(0)
    warped = gdal.Warp(
        "",
        source,
        format="MEM",
        xRes=10,
        yRes=10,
        resampleAlg=gdal.GRA_NearestNeighbour,
        outputBounds=(600000.0, 7199960.0, 600040.0, 7200000.0),
        dstSRS="EPSG:32722",
        outputType=gdal.GDT_Byte,
    )
    values = list(warped.GetRasterBand(1).ReadAsArray().ravel())
    elapsed = time.perf_counter() - started
    payload = {
        "sentinel_scene": False,
        "method": "gdal_warp_nearest",
        "src_gsd_m": 20,
        "dst_gsd_m": 10,
        "src_crs": "EPSG:32722",
        "classes_in": [4, 8, 9, 4],
        "values_out": [int(item) for item in values],
        "classes_not_blended": set(int(item) for item in values) <= {4, 8, 9},
        "elapsed_seconds": round(elapsed, 6),
        "gdal": gdal.VersionInfo("RELEASE_NAME"),
        "qgis_python": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    print(json.dumps(payload))
    return 0 if payload["classes_not_blended"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
