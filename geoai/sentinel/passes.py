"""Agrupa cenas L2A por uma mesma aquisição. Datas diferentes não se misturam."""

from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

_PRODUCT = re.compile(
    r"^(S2[A-C])_MSIL2A_(\d{8}T\d{6})_N(\d{4})_R(\d{3})_T(\d{2}[A-Z]{3})_(\d{8}T\d{6})"
)


def parse_product_id(product_id: str) -> dict[str, str] | None:
    """Lê satélite, instante de aquisição, órbita e tile no identificador SAFE."""

    match = _PRODUCT.match(product_id or "")
    if not match:
        return None
    satellite, sensing, baseline, orbit, tile, processed = match.groups()
    return {
        "satellite": satellite,
        "sensing_time": sensing,
        "sensing_time_utc": _sensing_utc(sensing),
        "baseline": baseline,
        "relative_orbit": orbit,
        "mgrs_tile": tile,
        "processing_time": processed,
        "acquisition_id": f"{satellite}_{sensing}_R{orbit}",
    }


def _sensing_utc(sensing: str) -> str:
    day, clock = sensing.split("T")
    return f"{day[0:4]}-{day[4:6]}-{day[6:8]}T{clock[0:2]}:{clock[2:4]}:{clock[4:6]}Z"


def mosaic_metrics(
    tile_geometries: dict[str, BaseGeometry],
    aoi: BaseGeometry,
) -> dict[str, Any]:
    """União, lacuna e sobreposição no mesmo CRS da AOI."""

    aoi_area = float(aoi.area)
    if aoi_area <= 0:
        raise ValueError("AOI sem área")
    coverages: dict[str, float] = {}
    clipped = []
    for name, geom in tile_geometries.items():
        piece = geom.intersection(aoi)
        clipped.append(piece)
        coverages[name] = float(piece.area / aoi_area)
    if not clipped:
        return {
            "union_coverage": 0.0,
            "gap": 1.0,
            "overlap_coverage": 0.0,
            "tile_coverages": {},
        }
    union_coverage = float(unary_union(clipped).area / aoi_area)
    return {
        "union_coverage": union_coverage,
        "gap": float(1.0 - union_coverage),
        "overlap_coverage": _overlap_fraction(clipped, aoi_area),
        "tile_coverages": coverages,
    }


def _overlap_fraction(clipped: list[BaseGeometry], aoi_area: float) -> float:
    shared = []
    for left, right in combinations(clipped, 2):
        piece = left.intersection(right)
        if not piece.is_empty:
            shared.append(piece)
    if not shared:
        return 0.0
    return float(unary_union(shared).area / aoi_area)


def minimal_covering_tiles(
    tile_geometries: dict[str, BaseGeometry],
    aoi: BaseGeometry,
    threshold: float,
) -> dict[str, Any]:
    """Menor subconjunto de tiles da mesma passagem que atinge o limiar."""

    names = list(tile_geometries)
    if len(names) > 8:
        raise ValueError("muitas tiles para enumerar o subconjunto mínimo")
    full = mosaic_metrics(tile_geometries, aoi)
    best: tuple[tuple[Any, ...], list[str], dict[str, Any]] | None = None
    for mask in range(1, 1 << len(names)):
        chosen = [names[index] for index in range(len(names)) if mask & (1 << index)]
        subset = {name: tile_geometries[name] for name in chosen}
        metrics = mosaic_metrics(subset, aoi)
        if metrics["union_coverage"] + 1e-12 < threshold:
            continue
        rank = (
            len(chosen),
            -metrics["union_coverage"],
            metrics["overlap_coverage"],
            tuple(sorted(chosen)),
        )
        if best is None or rank < best[0]:
            best = (rank, chosen, metrics)
    if best is None:
        return {
            **full,
            "pass_union_coverage": full["union_coverage"],
            "pass_overlap_coverage": full["overlap_coverage"],
            "tile_coverages": full["tile_coverages"],
            "selected_tiles": [],
            "covers_threshold": False,
            "mosaic_required": False,
        }
    chosen = best[1]
    metrics = best[2]
    return {
        **metrics,
        "pass_union_coverage": full["union_coverage"],
        "pass_overlap_coverage": full["overlap_coverage"],
        "tile_coverages": full["tile_coverages"],
        "selected_tiles": sorted(chosen),
        "covers_threshold": True,
        "mosaic_required": len(chosen) > 1,
    }
