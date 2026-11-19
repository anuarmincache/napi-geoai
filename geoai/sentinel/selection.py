"""Triagem de cenas STAC. Cloud cover do item não aceita a cena."""

from __future__ import annotations

from typing import Any

from shapely.geometry import shape

from geoai.sentinel.pilot import MIN_FOOTPRINT_COVERAGE


def footprint_coverage(
    scene_geometry: dict[str, Any],
    aoi_geometry: dict[str, Any],
) -> float:
    """Fração da AOI coberta pelo footprint. Não mede nuvem dentro da AOI."""

    aoi = shape(aoi_geometry)
    if aoi.is_empty or aoi.area == 0:
        raise ValueError("AOI vazia")
    scene = shape(scene_geometry)
    return float(scene.intersection(aoi).area / aoi.area)


def rank_full_coverage(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordena cenas que cobrem a AOI. Não marca nenhuma como aceita."""

    covered = [
        item
        for item in candidates
        if item.get("aoi_coverage") is not None
        and float(item["aoi_coverage"]) >= MIN_FOOTPRINT_COVERAGE
    ]

    def _cloud_key(item: dict[str, Any]) -> tuple[bool, float]:
        cloud = item.get("eo_cloud_cover")
        if cloud is None:
            return (True, 0.0)
        return (False, float(cloud))

    covered.sort(key=lambda item: item.get("datetime") or "", reverse=True)
    covered.sort(key=_cloud_key)
    return covered


def scene_is_accepted(valid_pixel_fraction: float | None) -> bool:
    """Aceite depende da fração válida medida na AOI. Ausência não é zero."""

    from geoai.sentinel.pilot import MIN_VALID_PIXEL_FRACTION

    if valid_pixel_fraction is None:
        return False
    return float(valid_pixel_fraction) >= MIN_VALID_PIXEL_FRACTION
