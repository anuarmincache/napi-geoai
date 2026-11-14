"""Janela real do GDAL em raster sintético. Não é cena Sentinel.

Executar com python-qgis-ltr.bat.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from osgeo import gdal

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from geoai.processing.safety import atomic_write_json  # noqa: E402
from geoai.sentinel.gdal_scene import read_window  # noqa: E402
from geoai.sentinel.grid import place_array  # noqa: E402

OUT = REPO / "docs" / "evidence" / "sentinel" / "gdal_window_synthetic.json"


def main() -> int:
    started = time.perf_counter()
    gdal.UseExceptions()
    source = np.arange(16, dtype=np.uint16).reshape(4, 4)
    dataset = gdal.GetDriverByName("MEM").Create("", 4, 4, 1, gdal.GDT_UInt16)
    dataset.SetGeoTransform((0.0, 10.0, 0.0, 40.0, 0.0, -10.0))
    dataset.GetRasterBand(1).WriteArray(source)
    temporary = REPO / "data" / "processed" / "sentinel" / "_window_synthetic.tif"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    gdal.GetDriverByName("GTiff").CreateCopy(str(temporary), dataset)
    dataset = None
    window = read_window(temporary, 1, 1, 2, 2)
    target = gdal.GetDriverByName("GTiff").Create(
        str(temporary.with_name("_window_write.tif")),
        4,
        4,
        1,
        gdal.GDT_UInt16,
    )
    target.GetRasterBand(1).WriteArray(window, 1, 1)
    written = target.GetRasterBand(1).ReadAsArray(1, 1, 2, 2)
    target = None
    temporary.with_name("_window_write.tif").unlink(missing_ok=True)
    destination = np.zeros((4, 4), dtype=np.uint16)
    place_array(
        destination,
        window,
        {
            "src_xoff": 1,
            "src_yoff": 1,
            "xsize": 2,
            "ysize": 2,
            "dst_xoff": 1,
            "dst_yoff": 1,
        },
    )
    temporary.unlink(missing_ok=True)
    payload = {
        "sentinel_scene": False,
        "official_pixels": False,
        "ndvi_published": False,
        "read": "ReadAsArray",
        "window_shape": list(window.shape),
        "values_match": bool(np.array_equal(destination[1:3, 1:3], source[1:3, 1:3])),
        "write": "WriteArray",
        "write_matches": bool(np.array_equal(written, source[1:3, 1:3])),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "gdal": gdal.__version__,
    }
    atomic_write_json(OUT, payload)
    print(OUT)
    print(payload["values_match"], payload["window_shape"])
    ok = payload["values_match"] and payload["write_matches"]
    return 0 if ok and payload["window_shape"] == [2, 2] else 1


if __name__ == "__main__":
    raise SystemExit(main())
