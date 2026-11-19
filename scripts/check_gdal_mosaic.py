"""Mosaico sintético com GDAL. Não é cena Sentinel e não publica NDVI.

Executar com python-qgis-ltr.bat.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from osgeo import gdal, osr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from geoai.sentinel.gdal_blocks import compose_blocked, reflectance_block  # noqa: E402

OUT = REPO / "docs" / "evidence" / "sentinel" / "gdal_mosaic_synthetic.json"
CATALOG = REPO / "data" / "derived" / "sentinel_maringa_pilot.json"


def _dataset(
    array: np.ndarray,
    origin_x: float,
    origin_y: float,
    pixel: float,
    nodata: float,
):
    rows, cols = array.shape
    dataset = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_UInt16)
    dataset.SetGeoTransform((origin_x, pixel, 0.0, origin_y, 0.0, -pixel))
    spatial = osr.SpatialReference()
    spatial.ImportFromEPSG(32722)
    dataset.SetProjection(spatial.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.WriteArray(array.astype(np.uint16))
    band.SetNoDataValue(nodata)
    return dataset


def _warp_to_grid(
    source,
    origin_x: float,
    origin_y: float,
    pixel: float,
    cols: int,
    rows: int,
):
    min_y = origin_y - rows * pixel
    return gdal.Warp(
        "",
        source,
        format="MEM",
        xRes=pixel,
        yRes=pixel,
        resampleAlg=gdal.GRA_NearestNeighbour,
        outputBounds=(origin_x, min_y, origin_x + cols * pixel, origin_y),
        dstSRS="EPSG:32722",
        outputType=gdal.GDT_UInt16,
        dstNodata=0,
    )


def _rss_mb() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        get_info = psapi.GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        ok = get_info(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return counters.PeakWorkingSetSize / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    gdal.UseExceptions()
    started = time.perf_counter()
    # Tile A: 40 m. Tile B começa 20 m à direita. Grade comum: 60 m x 40 m.
    red_a = np.full((4, 4), 2000, dtype=np.uint16)
    red_a[0, 0] = 0
    nir_a = np.full((4, 4), 3000, dtype=np.uint16)
    scl_a = np.array([[4, 9], [4, 9]], dtype=np.uint16)
    red_b = np.full((4, 4), 2000, dtype=np.uint16)
    nir_b = np.full((4, 4), 3000, dtype=np.uint16)
    scl_b = np.full((2, 2), 4, dtype=np.uint16)
    origin_y = 7_200_040.0
    common_cols, common_rows, pixel = 6, 4, 10.0
    warped = []
    sources = (
        (600_000.0, 10.0, red_a, nir_a, scl_a),
        (600_020.0, 10.0, red_b, nir_b, scl_b),
    )
    for origin_x, band_pixel, red, nir, scl in sources:
        scl_pixel = band_pixel * 2
        red_ds = _warp_to_grid(
            _dataset(red, origin_x, origin_y, band_pixel, 0),
            600_000.0,
            origin_y,
            pixel,
            common_cols,
            common_rows,
        )
        nir_ds = _warp_to_grid(
            _dataset(nir, origin_x, origin_y, band_pixel, 0),
            600_000.0,
            origin_y,
            pixel,
            common_cols,
            common_rows,
        )
        scl_ds = _warp_to_grid(
            _dataset(scl, origin_x, origin_y, scl_pixel, 0),
            600_000.0,
            origin_y,
            pixel,
            common_cols,
            common_rows,
        )
        red_ref = reflectance_block(
            red_ds.ReadAsArray(),
            scale=0.0001,
            offset=-0.1,
            nodata=0,
        )
        nir_ref = reflectance_block(
            nir_ds.ReadAsArray(),
            scale=0.0001,
            offset=-0.1,
            nodata=0,
        )
        warped.append((red_ref, nir_ref, scl_ds.ReadAsArray()))
    aoi = np.ones((common_rows, common_cols), dtype=bool)
    result = compose_blocked(
        [item[0] for item in warped],
        [item[1] for item in warped],
        [item[2] for item in warped],
        aoi,
        block=2,
    )
    elapsed = time.perf_counter() - started
    catalog_flag = None
    if CATALOG.is_file():
        payload_catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        catalog_flag = payload_catalog.get("ndvi_published")
    payload = {
        "sentinel_scene": False,
        "official_pixels": False,
        "ndvi_published": False,
        "catalog_ndvi_published_after": catalog_flag,
        "rule": result["rule"],
        "crs": "EPSG:32722",
        "gsd_m": 10,
        "scl_resample": "gdal_warp_nearest",
        "block": 2,
        "n_aoi": result["n_aoi"],
        "n_valid": result["n_valid"],
        "pixels_per_tile": result["pixels_per_tile"],
        "overlap_both_valid": result["overlap_both_valid"],
        "valid_fraction": result["valid_fraction"],
        "quality_approved_for_pilot": False,
        "provenance_values": sorted({int(v) for v in result["provenance"].ravel()}),
        "disk_bytes_written": 0,
        "elapsed_seconds": round(elapsed, 3),
        "peak_rss_mb": None if _rss_mb() is None else round(_rss_mb(), 3),
        "gdal": gdal.VersionInfo("RELEASE_NAME"),
        "qgis_python": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    summary = {
        "n_valid": payload["n_valid"],
        "pixels_per_tile": payload["pixels_per_tile"],
        "ndvi_published": payload["ndvi_published"],
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
