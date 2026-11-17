"""PNG do NDVI a partir de um GeoTIFF já validado.

A leitura é somente de consulta. A rampa é a do catálogo
``ndvi-yellow-green-v1``. Nenhum valor do raster de origem é regravado.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

import numpy as np

from geoai.catalog.integrity import (
    assert_public_metadata,
    canonical_json,
    sha256_file,
)
from geoai.catalog.style import STYLE_ID, ndvi_style
from geoai.preview.glyphs import GLYPH_HEIGHT, GLYPH_WIDTH, GLYPHS

PREVIEW_NAME = "ndvi-preview.png"
LEGEND_NAME = "ndvi-preview-with-legend.png"
MANIFEST_NAME = "ndvi_png_manifest.json"
PANEL_WIDTH = 560
APPROVED_STOPS = (0.0, 0.2, 0.4, 0.6, 0.8)


def _hex_rgb(value: str) -> tuple[int, int, int]:
    text = value.removeprefix("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _style_arrays(style: dict[str, Any]) -> dict[str, Any]:
    if style["id"] != STYLE_ID:
        raise ValueError("estilo_recusado")
    stops = style["stops"]
    values = tuple(item["value"] for item in stops)
    if values != APPROVED_STOPS:
        raise ValueError("rampa_recusada")
    return {
        "nodata": np.float64(style["nodata_value"]),
        "yellow": np.array(_hex_rgb(style["below_display_min"]["hex"]), np.uint8),
        "green": np.array(_hex_rgb(style["above_display_max"]["hex"]), np.uint8),
        "gray": np.array(_hex_rgb(style["outside_physical_interval"]["hex"]), np.uint8),
        "physical_min": float(style["outside_physical_interval"]["minimum"]),
        "physical_max": float(style["outside_physical_interval"]["maximum"]),
        "display_min": float(style["display_min"]),
        "display_max": float(style["display_max"]),
        "stop_values": np.array(values, dtype=np.float64),
        "stop_colors": np.array(
            [_hex_rgb(item["hex"]) for item in stops], dtype=np.float64
        ),
    }


def colorize_ndvi(
    values: np.ndarray,
    style: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, int]]:
    """Converte a grade para RGBA. O array de entrada não é modificado."""

    source = np.asarray(values)
    if source.ndim != 2:
        raise ValueError("grade_invalida")
    original = source.ravel()[:8].copy()
    chosen = ndvi_style() if style is None else style
    spec = _style_arrays(chosen)
    data = source.astype(np.float64, copy=False)
    output = np.zeros(source.shape + (4,), dtype=np.uint8)
    valid = np.isfinite(data) & (data != spec["nodata"])
    anomalous = valid & ((data < spec["physical_min"]) | (data > spec["physical_max"]))
    low = valid & ~anomalous & (data < spec["display_min"])
    high = valid & ~anomalous & (data > spec["display_max"])
    ramp = valid & ~anomalous & ~low & ~high

    def paint(mask: np.ndarray, color: np.ndarray) -> None:
        output[mask, 0] = color[0]
        output[mask, 1] = color[1]
        output[mask, 2] = color[2]
        output[mask, 3] = 255

    paint(anomalous, spec["gray"])
    paint(low, spec["yellow"])
    paint(high, spec["green"])
    if np.any(ramp):
        samples = data[ramp]
        index = np.searchsorted(spec["stop_values"], samples, side="right") - 1
        index = np.clip(index, 0, len(spec["stop_values"]) - 2)
        start = spec["stop_values"][index]
        end = spec["stop_values"][index + 1]
        weight = ((samples - start) / (end - start))[:, None]
        mixed = spec["stop_colors"][index] * (1.0 - weight)
        mixed += spec["stop_colors"][index + 1] * weight
        output[ramp, :3] = np.rint(mixed).astype(np.uint8)
        output[ramp, 3] = 255
    if not np.array_equal(source.ravel()[:8], original):
        raise RuntimeError("grade_alterada")
    counts = {
        "nodata": int((~valid).sum()),
        "anomalous": int(anomalous.sum()),
        "low": int(low.sum()),
        "high": int(high.sum()),
        "ramp": int(ramp.sum()),
    }
    return output, counts


def _chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def write_rgba_png(path: Path, image: np.ndarray) -> None:
    """PNG RGBA sem carimbo de tempo, para repetir o mesmo SHA-256."""

    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("rgba_u8_obrigatorio")
    height, width, _ = image.shape
    rows = [b"\x00" + image[row].tobytes() for row in range(height)]
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    body = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(body)


def read_rgba_png(path: Path) -> np.ndarray:
    """Lê um PNG RGBA gerado por este módulo."""

    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("png_invalido")
    position = 8
    width = height = 0
    compressed = b""
    while position < len(data):
        length = struct.unpack(">I", data[position : position + 4])[0]
        tag = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if tag == b"IHDR":
            width, height, bit_depth, color_type, *_ = struct.unpack(
                ">IIBBBBB", payload
            )
            if bit_depth != 8 or color_type != 6:
                raise ValueError("png_nao_rgba")
        elif tag == b"IDAT":
            compressed += payload
        elif tag == b"IEND":
            break
    raw = zlib.decompress(compressed)
    stride = width * 4
    rows = []
    offset = 0
    for _ in range(height):
        if raw[offset] != 0:
            raise ValueError("filtro_png_recusado")
        offset += 1
        rows.append(np.frombuffer(raw[offset : offset + stride], np.uint8).copy())
        offset += stride
    return np.vstack(rows).reshape(height, width, 4)


def draw_text(
    image: np.ndarray,
    x: int,
    y: int,
    text: str,
    *,
    scale: int = 3,
    color: tuple[int, int, int, int] = (26, 26, 26, 255),
) -> None:
    cursor = x
    ink = np.array(color, dtype=np.uint8)
    for char in text:
        glyph = GLYPHS.get(char, GLYPHS["?"])
        for row, bits in enumerate(glyph):
            for col in range(GLYPH_WIDTH):
                if bits & (1 << (GLYPH_WIDTH - 1 - col)):
                    top = y + row * scale
                    left = cursor + col * scale
                    image[top : top + scale, left : left + scale] = ink
        cursor += (GLYPH_WIDTH + 1) * scale


def legend_panel(
    height: int,
    style: dict[str, Any],
    lines: tuple[str, ...],
) -> np.ndarray:
    """Painel opaco à direita. Não reamostra o mapa."""

    if height < 520:
        raise ValueError("painel_sem_espaco")
    panel = np.full((height, PANEL_WIDTH, 4), 255, dtype=np.uint8)
    y = 28
    for index, line in enumerate(lines):
        scale = 4 if index == 0 else 3
        draw_text(panel, 24, y, line, scale=scale)
        y += GLYPH_HEIGHT * scale + 12
    bar_width = 400
    bar_height = 36
    samples = np.linspace(0.0, 0.8, bar_width, dtype=np.float64)
    bar, _ = colorize_ndvi(np.repeat(samples[None, :], bar_height, axis=0), style)
    panel[y : y + bar_height, 24 : 24 + bar_width] = bar
    y += bar_height + 10
    for stop in style["stops"]:
        label_x = 24 + int(round(stop["value"] / 0.8 * (bar_width - 1))) - 12
        draw_text(panel, max(24, label_x), y, stop["label"], scale=2)
    y += 28
    panel[y : y + 22, 24:46] = (
        *_hex_rgb(style["outside_physical_interval"]["hex"]),
        255,
    )
    draw_text(panel, 56, y, "Cinza: fora de [-1, 1]", scale=2)
    y += 36
    panel[y : y + 22, 24:46] = (255, 255, 255, 0)
    panel[y : y + 22, 24] = (26, 26, 26, 255)
    panel[y : y + 22, 45] = (26, 26, 26, 255)
    panel[y, 24:46] = (26, 26, 26, 255)
    panel[y + 21, 24:46] = (26, 26, 26, 255)
    draw_text(panel, 56, y, "Sem dado: transparente", scale=2)
    return panel


def compose_legend(preview: np.ndarray, panel: np.ndarray) -> np.ndarray:
    if panel.shape[0] != preview.shape[0]:
        raise ValueError("painel_altura")
    return np.concatenate((preview, panel), axis=1)


def _empty_directory(path: Path) -> None:
    if path.exists():
        if any(path.iterdir()):
            raise FileExistsError("destino_ocupado")
    else:
        path.mkdir(parents=True)


def write_preview_pair(
    preview: np.ndarray,
    destination: Path,
    *,
    style: dict[str, Any],
    identity: dict[str, str],
    source: dict[str, Any],
    counts: dict[str, int],
    orientation: str,
) -> dict[str, Any]:
    """Grava os dois PNG e o manifesto. Recusa pasta que já tenha arquivo."""

    _empty_directory(destination)
    lines = (
        style["legend_title"],
        identity["name"],
        f"IBGE {identity['ibge']}",
        identity["image_date_label"],
        identity["satellite"],
        identity["acquisition_id"],
        style["resolution_label"],
        "Fonte: Sentinel-2",
    )
    panel = legend_panel(preview.shape[0], style, lines)
    legend = compose_legend(preview, panel)
    preview_path = destination / PREVIEW_NAME
    legend_path = destination / LEGEND_NAME
    write_rgba_png(preview_path, preview)
    write_rgba_png(legend_path, legend)
    manifest = {
        "schema": "napi-ndvi-png-preview-1",
        "ndvi_published": False,
        "public_download": False,
        "source_values_modified": False,
        "style_id": style["id"],
        "stops": style["stops"],
        "display_rules": {
            "nodata": "transparent",
            "below_display_min": style["below_display_min"],
            "ramp": "linear_yellow_to_green",
            "above_display_max": style["above_display_max"],
            "outside_physical_interval": style["outside_physical_interval"],
        },
        "municipality": {"ibge": identity["ibge"], "name": identity["name"]},
        "acquisition_id": identity["acquisition_id"],
        "image_date": identity["image_date"],
        "satellite": identity["satellite"],
        "source_cog": source,
        "orientation": orientation,
        "counts": counts,
        "images": {
            PREVIEW_NAME: _image_record(preview_path, preview.shape),
            LEGEND_NAME: _image_record(legend_path, legend.shape),
        },
    }
    assert_public_metadata(manifest)
    (destination / MANIFEST_NAME).write_bytes(canonical_json(manifest))
    return manifest


def _image_record(path: Path, shape: tuple[int, ...]) -> dict[str, Any]:
    return {
        "filename": path.name,
        "height": int(shape[0]),
        "width": int(shape[1]),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def read_ndvi_cog(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    """Abre o COG só para leitura e não grava arquivo auxiliar."""

    import os

    os.environ["GDAL_PAM_ENABLED"] = "NO"
    from osgeo import gdal, osr

    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None:
        raise FileNotFoundError("cog_ilegivel")
    band = dataset.GetRasterBand(1)
    array = band.ReadAsArray()
    transform = dataset.GetGeoTransform()
    spatial = osr.SpatialReference()
    spatial.ImportFromWkt(dataset.GetProjection())
    epsg = spatial.GetAuthorityCode(None)
    grid = {
        "width": dataset.RasterXSize,
        "height": dataset.RasterYSize,
        "geotransform": [float(value) for value in transform],
        "epsg": epsg,
        "nodata": band.GetNoDataValue(),
    }
    dataset.Close()
    north_up = (
        transform[1] > 0
        and transform[5] < 0
        and transform[2] == 0
        and transform[4] == 0
    )
    if not north_up:
        raise RuntimeError("orientacao_recusada")
    return array, grid


def render_cog_previews(
    cog_path: Path,
    destination: Path,
    *,
    expected_sha256: str,
    identity: dict[str, str],
) -> dict[str, Any]:
    """Gera os PNG depois de conferir o SHA-256 do COG."""

    digest = sha256_file(cog_path)
    if digest != expected_sha256:
        raise RuntimeError("cog_divergente")
    size_before = cog_path.stat().st_size
    array, grid = read_ndvi_cog(cog_path)
    if sha256_file(cog_path) != digest or cog_path.stat().st_size != size_before:
        raise RuntimeError("cog_alterado")
    style = ndvi_style()
    preview, counts = colorize_ndvi(array, style)
    source = {
        "filename": cog_path.name,
        "sha256": digest,
        "bytes": size_before,
        "width": grid["width"],
        "height": grid["height"],
        "epsg": grid["epsg"],
        "geotransform": grid["geotransform"],
    }
    manifest = write_preview_pair(
        preview,
        destination,
        style=style,
        identity=identity,
        source=source,
        counts=counts,
        orientation="norte_na_primeira_linha",
    )
    if sha256_file(cog_path) != expected_sha256:
        raise RuntimeError("cog_alterado")
    return manifest
