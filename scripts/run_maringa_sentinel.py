"""NDVI de Maringá com B04, B08 e SCL. Não mistura datas e não publica abaixo de 0,70.

Executar com python-qgis-ltr.bat. Credenciais ficam só no ambiente do processo.
"""

from __future__ import annotations

import ctypes
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from geoai.processing.safety import atomic_write_json  # noqa: E402
from geoai.sentinel.assets import BANDS, https_band_urls, official_asset_url  # noqa: E402
from geoai.sentinel.cdse_auth import (  # noqa: E402
    _token_from_environment as token_from_environment,
)
from geoai.sentinel.cdse_auth import (  # noqa: E402
    credential_flags,
    download_official_asset,
)
from geoai.sentinel.gdal_blocks import compose_blocked, reflectance_block  # noqa: E402
from geoai.sentinel.gdal_scene import (  # noqa: E402
    municipality_bounds,
    raster_info,
    rasterize_municipality,
    read_window,
    same_projection,
    write_raster,
)
from geoai.sentinel.grid import (  # noqa: E402
    grid_bounds,
    nearest_sample,
    place_array,
    snap_aoi_grid,
    source_window_for_output,
    window_covering_bounds,
)
from geoai.sentinel.pilot import (  # noqa: E402
    CATALOG_NAME,
    MESH_RELATIVE,
    PILOT_CD_MUN,
    STAC_SEARCH_URL,
)
from geoai.sentinel.publish import publication_allowed  # noqa: E402

TILES = ("22KCV", "22KDV")
SCALE = 0.0001
OFFSET = -0.1
NODATA = 0
PUBLISHED_NODATA = -9999.0
MAX_PIXELS = 20_000_000
EVIDENCE = REPO / "docs" / "evidence" / "sentinel" / "maringa_aoi_measurement.json"
CATALOG = REPO / "data" / "derived" / CATALOG_NAME


def _rss_mb() -> float | None:
    try:
        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        process = kernel.GetCurrentProcess()
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        ok = psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        )
        if not ok:
            return None
        return counters.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        return None


def _assert_public(payload: dict[str, Any]) -> None:
    text = json.dumps(payload)
    for needle in ("access_token", "Authorization", "Bearer ", "CDSE_PASSWORD"):
        if needle in text:
            raise RuntimeError("registro_recusado")


def _stac_features(bbox: list[float], sensing_utc: str) -> list[dict[str, Any]]:
    minute = sensing_utc[:16]
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{minute}:00Z/{minute}:59Z",
        "limit": 20,
    }
    request = urllib.request.Request(
        STAC_SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    features = payload.get("features") or []
    return [item for item in features if isinstance(item, dict)]


def _urls_for_acquisition(
    catalog: dict[str, Any],
    acquisition_id: str,
) -> dict[str, dict[str, str]]:
    group = next(
        item
        for item in catalog["acquisitions"]
        if item["acquisition_id"] == acquisition_id
    )
    products = {
        tile["mgrs_tile"]: tile["product_id"]
        for tile in group["tiles"]
        if tile["mgrs_tile"] in TILES and tile["selected"]
    }
    if set(products) != set(TILES):
        raise RuntimeError("tiles_ausentes")
    features = _stac_features(catalog["aoi"]["bbox"], group["sensing_time_utc"])
    by_id = {str(feature.get("id")): feature for feature in features}
    urls: dict[str, dict[str, str]] = {}
    for tile, product_id in products.items():
        feature = by_id.get(product_id)
        if feature is None:
            raise RuntimeError("stac_sem_produto")
        urls[tile] = https_band_urls(feature)
    probe = catalog.get("access_probe_scene") or {}
    if probe.get("product_id") == products["22KCV"]:
        expected = {
            key: official_asset_url(probe["assets"][key]["https_path"]) for key in BANDS
        }
        if urls["22KCV"] != expected:
            raise RuntimeError("url_b04_divergente")
    return urls


def _jp2_signature(path: Path) -> bool:
    header = path.read_bytes()[:64]
    return b"ftypjp2" in header or b"jP  " in header


def _ensure_band(url: str, destination: Path, token: str) -> dict[str, int]:
    if destination.is_file() and _jp2_signature(destination):
        try:
            raster_info(destination)
            return {"bytes_downloaded": 0, "bytes_on_disk": destination.stat().st_size}
        except Exception:
            destination.unlink(missing_ok=True)
    report = download_official_asset(url, destination, token)
    if not _jp2_signature(destination):
        destination.unlink(missing_ok=True)
        raise PermissionError("asset_nao_jp2")
    raster_info(destination)
    return {
        "bytes_downloaded": int(report["bytes_written"]),
        "bytes_on_disk": destination.stat().st_size,
    }


def _measure(
    catalog: dict[str, Any],
    acquisition_id: str,
    urls: dict[str, dict[str, str]],
    token: str,
) -> dict[str, Any]:
    raw_root = REPO / "data" / "raw" / "sentinel" / acquisition_id
    downloaded = 0
    on_disk = 0
    stored: dict[tuple[str, str], Path] = {}

    def take(tile: str, band: str) -> None:
        nonlocal downloaded, on_disk
        destination = raw_root / tile / f"{band}.jp2"
        counts = _ensure_band(urls[tile][band], destination, token)
        downloaded += counts["bytes_downloaded"]
        on_disk += counts["bytes_on_disk"]
        stored[(tile, band)] = destination

    take("22KCV", "B04_10m")
    reference = raster_info(stored[("22KCV", "B04_10m")])
    mesh = REPO / MESH_RELATIVE
    bounds = municipality_bounds(mesh, PILOT_CD_MUN, reference["projection"])
    grid = snap_aoi_grid(bounds, reference["geotransform"])
    rows = int(grid["rows"])
    cols = int(grid["cols"])
    if rows * cols > MAX_PIXELS:
        raise RuntimeError("grade_maior_que_o_piloto")
    for tile in TILES:
        for band in BANDS:
            if (tile, band) not in stored:
                take(tile, band)
    output_gt = grid["geotransform"]
    red_tiles: list[np.ndarray] = []
    nir_tiles: list[np.ndarray] = []
    scl_tiles: list[np.ndarray] = []
    for tile in TILES:
        red_info = raster_info(stored[(tile, "B04_10m")])
        nir_info = raster_info(stored[(tile, "B08_10m")])
        if not same_projection(reference["projection"], red_info["projection"]):
            raise RuntimeError("crs_divergente")
        if not same_projection(reference["projection"], nir_info["projection"]):
            raise RuntimeError("crs_divergente")
        red = np.zeros((rows, cols), dtype=np.uint16)
        nir = np.zeros((rows, cols), dtype=np.uint16)
        window = source_window_for_output(
            red_info["geotransform"],
            red_info["cols"],
            red_info["rows"],
            output_gt,
            cols,
            rows,
        )
        if window is not None:
            place_array(
                red,
                read_window(
                    stored[(tile, "B04_10m")],
                    window["src_xoff"],
                    window["src_yoff"],
                    window["xsize"],
                    window["ysize"],
                ),
                window,
            )
        nir_window = source_window_for_output(
            nir_info["geotransform"],
            nir_info["cols"],
            nir_info["rows"],
            output_gt,
            cols,
            rows,
        )
        if nir_window is not None:
            place_array(
                nir,
                read_window(
                    stored[(tile, "B08_10m")],
                    nir_window["src_xoff"],
                    nir_window["src_yoff"],
                    nir_window["xsize"],
                    nir_window["ysize"],
                ),
                nir_window,
            )
        red_tiles.append(
            reflectance_block(red, scale=SCALE, offset=OFFSET, nodata=NODATA)
        )
        nir_tiles.append(
            reflectance_block(nir, scale=SCALE, offset=OFFSET, nodata=NODATA)
        )
        scl_info = raster_info(stored[(tile, "SCL_20m")])
        covered = window_covering_bounds(
            scl_info["geotransform"],
            scl_info["cols"],
            scl_info["rows"],
            grid_bounds(output_gt, cols, rows),
        )
        if covered is None:
            scl_tiles.append(np.zeros((rows, cols), dtype=np.uint8))
            continue
        scl_window = read_window(
            stored[(tile, "SCL_20m")],
            covered["xoff"],
            covered["yoff"],
            covered["xsize"],
            covered["ysize"],
        )
        scl_tiles.append(
            nearest_sample(
                scl_window,
                covered["geotransform"],
                output_gt,
                rows,
                cols,
            )
        )
    aoi = rasterize_municipality(
        mesh,
        PILOT_CD_MUN,
        output_gt,
        cols,
        rows,
        reference["projection"],
    )
    composed = compose_blocked(red_tiles, nir_tiles, scl_tiles, aoi, block=256)
    return {
        "acquisition_id": acquisition_id,
        "official_pixels": True,
        "dates_combined": False,
        "rows": rows,
        "cols": cols,
        "n_aoi": composed["n_aoi"],
        "n_valid": composed["n_valid"],
        "valid_fraction": composed["valid_fraction"],
        "pixels_per_tile": composed["pixels_per_tile"],
        "overlap_both_valid": composed["overlap_both_valid"],
        "quality_approved": composed["quality_approved"],
        "rule": composed["rule"],
        "bytes_downloaded": downloaded,
        "bytes_on_disk": on_disk,
        "ndvi": composed["ndvi"],
        "provenance": composed["provenance"],
        "geotransform": output_gt,
        "projection": reference["projection"],
        "scale": SCALE,
        "offset": OFFSET,
        "nodata_dn": NODATA,
    }


def _public_result(
    result: dict[str, Any],
    published: bool,
    cog: str | None,
) -> dict[str, Any]:
    fraction = result["valid_fraction"]
    return {
        "acquisition_id": result["acquisition_id"],
        "official_pixels": True,
        "dates_combined": False,
        "rows": result["rows"],
        "cols": result["cols"],
        "n_aoi": result["n_aoi"],
        "n_valid": result["n_valid"],
        "valid_fraction": fraction,
        "pixels_per_tile": result["pixels_per_tile"],
        "overlap_both_valid": result["overlap_both_valid"],
        "quality_approved": bool(result["quality_approved"]),
        "rule": result["rule"],
        "bytes_downloaded": result["bytes_downloaded"],
        "bytes_on_disk": result["bytes_on_disk"],
        "ndvi_published": published,
        "cog": cog,
        "scale": result["scale"],
        "offset": result["offset"],
        "nodata_dn": result["nodata_dn"],
        "published_nodata": PUBLISHED_NODATA,
    }


def _apply_catalog(
    catalog: dict[str, Any],
    results: list[dict[str, Any]],
    published: dict[str, Any] | None,
    elapsed: float,
) -> None:
    chosen = published or results[-1]
    fraction = chosen["valid_fraction"]
    approved = published is not None
    catalog["valid_pixel_fraction"] = fraction
    catalog["quality_approved"] = approved
    catalog["quality_status"] = "approved" if approved else "rejected"
    catalog["geometric_candidate_only"] = not approved
    catalog["processing_status"] = "measured"
    catalog["ndvi_published"] = approved
    catalog["status"] = "ready" if approved else "quality_rejected"
    catalog["downloaded_bytes"] = sum(item["bytes_downloaded"] for item in results)
    catalog["measured_acquisition_id"] = chosen["acquisition_id"]
    catalog["dates_combined"] = False
    catalog["aoi_measurements"] = results
    catalog["measurement_seconds"] = round(elapsed, 3)
    if approved:
        catalog["cog"] = published["cog"]
        message = (
            f"Maringá: passagem {chosen['acquisition_id']} com fração válida "
            f"{fraction:.6f} na AOI. NDVI publicado. Datas não foram misturadas."
        )
    else:
        catalog["cog"] = None
        message = (
            f"Maringá: passagem {chosen['acquisition_id']} com fração válida "
            f"{fraction:.6f} na AOI, abaixo de 0,70. NDVI não publicado."
        )
    catalog["public_message_pt"] = message
    _assert_public(catalog)
    previous = CATALOG.read_text(encoding="utf-8")
    try:
        atomic_write_json(CATALOG, catalog)
    except Exception:
        CATALOG.write_text(previous, encoding="utf-8", newline="\n")
        raise


def main() -> int:
    started = time.perf_counter()
    flags = credential_flags()
    if not (flags["password_grant_configured"] or flags["bearer_configured"]):
        print("credencial ausente neste processo")
        print("ndvi_published False")
        return 2
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    token = token_from_environment()
    if not token:
        print("credencial ausente neste processo")
        print("ndvi_published False")
        return 2
    order = [
        catalog["selected_acquisition"]["acquisition_id"],
        catalog["fallback_acquisition_id"],
    ]
    results: list[dict[str, Any]] = []
    published: dict[str, Any] | None = None
    arrays: dict[str, Any] | None = None
    try:
        for acquisition_id in order:
            urls = _urls_for_acquisition(catalog, acquisition_id)
            measured = _measure(catalog, acquisition_id, urls, token)
            allowed = publication_allowed(
                official_pixels=True,
                valid_fraction=measured["valid_fraction"],
                acquisition_ids=(acquisition_id,),
            )
            cog_name = None
            if allowed:
                cog_path = (
                    REPO
                    / "data"
                    / "processed"
                    / "sentinel"
                    / f"maringa_{acquisition_id}_ndvi.tif"
                )
                provenance_path = cog_path.with_name(
                    f"maringa_{acquisition_id}_provenance.tif"
                )
                write_raster(
                    cog_path,
                    measured["ndvi"],
                    measured["geotransform"],
                    measured["projection"],
                    nodata=PUBLISHED_NODATA,
                )
                write_raster(
                    provenance_path,
                    measured["provenance"].astype(np.float32),
                    measured["geotransform"],
                    measured["projection"],
                    nodata=-1,
                )
                cog_name = cog_path.relative_to(REPO).as_posix()
                published = _public_result(measured, True, cog_name)
                published["provenance"] = provenance_path.relative_to(REPO).as_posix()
            public = _public_result(measured, allowed, cog_name)
            if published is not None:
                public["provenance"] = published.get("provenance")
            results.append(public)
            measured["ndvi"] = None
            measured["provenance"] = None
            arrays = measured
            if allowed:
                break
            if measured["valid_fraction"] is None:
                break
            if acquisition_id == order[-1]:
                break
    finally:
        token = None
    if not results or arrays is None:
        print("medicao_ausente")
        print("ndvi_published False")
        return 2
    elapsed = time.perf_counter() - started
    try:
        _apply_catalog(catalog, results, published, elapsed)
    except Exception:
        if published and published.get("cog"):
            (REPO / published["cog"]).unlink(missing_ok=True)
            provenance = published.get("provenance")
            if isinstance(provenance, str):
                (REPO / provenance).unlink(missing_ok=True)
        raise
    usage = shutil.disk_usage(REPO)
    evidence = {
        "sentinel_scene": True,
        "official_pixels": True,
        "dates_combined": False,
        "results": results,
        "ndvi_published": published is not None,
        "elapsed_seconds": round(elapsed, 3),
        "peak_rss_mb": _rss_mb(),
        "disk_free_bytes": usage.free,
        "rule": "first_valid_tile_in_declared_order",
        "tiles": list(TILES),
        "bands": list(BANDS),
    }
    _assert_public(evidence)
    atomic_write_json(EVIDENCE, evidence)
    final = published or results[-1]
    print(f"acquisition={final['acquisition_id']}")
    print(f"valid_fraction={final['valid_fraction']}")
    print(f"quality_approved={final['quality_approved']}")
    print(f"ndvi_published={final['ndvi_published']}")
    print(f"bytes_downloaded={sum(item['bytes_downloaded'] for item in results)}")
    print(f"elapsed_seconds={round(elapsed, 3)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        token = None
        text = str(error)
        if any(part in text for part in ("Bearer", "access_token", "CDSE_PASSWORD")):
            text = type(error).__name__
        print(text, file=sys.stderr)
        print("ndvi_published False")
        raise SystemExit(2) from None
