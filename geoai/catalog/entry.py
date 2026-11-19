"""Montagem do catálogo público a partir de um manifesto local já validado."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from geoai.catalog.integrity import assert_public_metadata, product_availability
from geoai.catalog.style import ndvi_style
from geoai.catalog.updates import UPDATE_INTERVAL_DAYS

SCHEMA = "napi-map-catalog-1"
DOWNLOAD_FORMATS = ("png", "geotiff", "csv", "json")
_ACQUISITION = re.compile(r"^S2([AB])_(\d{8})T\d{6}_R\d{3}$")


def parse_acquisition(acquisition_id: str) -> tuple[str, str]:
    match = _ACQUISITION.fullmatch(acquisition_id)
    if match is None:
        raise ValueError("aquisicao_invalida")
    satellite = f"Sentinel-2{match.group(1)}"
    raw = match.group(2)
    return satellite, f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def _require_consistent_counts(counts: dict[str, Any]) -> float:
    pixels = tuple(counts["pixels_per_tile"])
    if len(pixels) != 2:
        raise ValueError("tiles_ausentes")
    if pixels[0] + pixels[1] != counts["n_valid"]:
        raise ValueError("soma_das_tiles_divergente")
    overlap = counts["overlap_both_valid"]
    if overlap < 0 or overlap > pixels[0]:
        raise ValueError("sobreposicao_incoerente")
    if counts["finite_ndvi_pixels"] != counts["n_valid"]:
        raise ValueError("pixels_finitos_divergentes")
    histogram = counts["provenance_histogram"]
    if (histogram["1"], histogram["2"]) != pixels:
        raise ValueError("histograma_divergente")
    fraction = counts["n_valid"] / counts["n_aoi"]
    return fraction


def build_catalog_entry(
    manifest: dict[str, Any],
    *,
    ibge: str,
    municipality: str,
    acquisition_id: str,
    processed_at: str,
    product_dir: Path,
    quality_status: str,
    quality_note_pt: str,
    fraction_gate_passed: bool,
    outside_unit_interval: dict[str, Any] | None = None,
    publish: bool = False,
) -> dict[str, Any]:
    """Descreve um produto. Recusa publicação e caminhos locais."""

    if publish:
        raise PermissionError("publicacao_recusada")
    if manifest.get("ndvi_published") is not False:
        raise PermissionError("manifesto_indica_publicacao")
    if not processed_at.endswith("Z"):
        raise ValueError("data_sem_utc")
    satellite, image_date = parse_acquisition(acquisition_id)
    counts = manifest["counts"]
    fraction = _require_consistent_counts(counts)
    if outside_unit_interval and quality_status == "approved":
        raise ValueError("qualidade_incompleta")

    products = manifest["products"]
    geotiff = product_availability(
        product_dir / products["ndvi"]["name"],
        expected_sha256=products["ndvi"]["sha256"],
        expected_bytes=products["ndvi"]["bytes"],
    )
    provenance = product_availability(
        product_dir / products["provenance"]["name"],
        expected_sha256=products["provenance"]["sha256"],
        expected_bytes=products["provenance"]["bytes"],
    )
    pending = {
        "exists": False,
        "validated": False,
        "published": False,
        "public_download": False,
        "available": False,
        "filename": None,
        "sha256": None,
        "bytes": None,
        "reason": "nao_gerado",
    }
    entry = {
        "schema": SCHEMA,
        "municipality": {
            "ibge": ibge,
            "name": municipality,
            "uf": "PR",
        },
        "product_type": "NDVI",
        "satellite": satellite,
        "acquisition_id": acquisition_id,
        "image_date": image_date,
        "processed_at": processed_at,
        "spatial_resolution_m": manifest["resolution_m"],
        "crs": f"EPSG:{manifest['epsg']}",
        "grid": {
            "rows": manifest["rows"],
            "cols": manifest["cols"],
            "geotransform": list(manifest["geotransform"]),
        },
        "nodata": manifest["nodata"],
        "ndvi_dtype": manifest["ndvi_dtype"],
        "valid_pixel_fraction": fraction,
        "counts": {
            "n_aoi": counts["n_aoi"],
            "n_valid": counts["n_valid"],
            "pixels_per_tile": {
                "22KCV": counts["pixels_per_tile"][0],
                "22KDV": counts["pixels_per_tile"][1],
            },
            "overlap_both_valid": counts["overlap_both_valid"],
            "pixel_equation": counts["pixel_equation"],
        },
        "quality": {
            "status": quality_status,
            "fraction_gate_passed": fraction_gate_passed,
            "minimum_valid_fraction": 0.70,
            "note_pt": quality_note_pt,
            "outside_unit_interval": outside_unit_interval,
        },
        "algorithm": {
            "version": manifest["algorithm"],
            "rule": manifest["rule"],
            "gdal_version": manifest["gdal_version"],
            "peak_rss_mb": manifest["peak_rss_mb"],
            "peak_rss_status": manifest["peak_rss_status"],
        },
        "provenance": {
            "dtype": manifest["provenance_dtype"],
            "values": manifest["provenance_values"],
            "histogram": counts["provenance_histogram"],
            "product": provenance,
        },
        "downloads": {
            "png": dict(pending),
            "geotiff": geotiff,
            "csv": dict(pending),
            "json": {
                "exists": True,
                "validated": True,
                "published": False,
                "public_download": False,
                "available": True,
                "filename": f"{ibge}.json",
                "sha256": None,
                "bytes": None,
                "reason": None,
                "checksum_record": f"catalog/integrity/{ibge}.json",
            },
        },
        "publication_state": "nao_publicado",
        "ndvi_published": False,
        "last_update_attempt": {
            "at": processed_at,
            "result": "produto_local_validado",
            "published": False,
        },
        "update_policy": {
            "interval_days": UPDATE_INTERVAL_DAYS,
            "scheduler_active": False,
            "guarantees_new_valid_scene": False,
            "scene_organization": "uma_cena_por_tile",
            "if_quality_fails": "manter_ultimo_mapa_aprovado",
            "previous_products": "preservar",
        },
        "acquisitions": [
            {
                "acquisition_id": acquisition_id,
                "image_date": image_date,
                "role": "atual",
                "valid_pixel_fraction": fraction,
                "quality_status": quality_status,
                "algorithm_version": manifest["algorithm"],
                "publication_state": "nao_publicado",
            }
        ],
        "previous_acquisitions": [],
        "style": ndvi_style(),
    }
    assert_public_metadata(entry)
    return entry


def file_states(entry: dict[str, Any]) -> dict[str, dict[str, bool]]:
    """Existência, validação e publicação, em campos separados."""

    states = {}
    for name in DOWNLOAD_FORMATS:
        item = entry["downloads"][name]
        states[name] = {
            "exists": bool(item["exists"]),
            "validated": bool(item["validated"]),
            "published": bool(item["published"]),
        }
    return states


def download_menu(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Somente um arquivo publicado entra no download público."""

    if entry.get("ndvi_published") is not True:
        return []
    if entry.get("publication_state") != "publicado":
        return []
    menu = []
    for name in DOWNLOAD_FORMATS:
        item = entry["downloads"][name]
        if item.get("public_download") is True and item.get("published") is True:
            menu.append({"format": name, "filename": item["filename"]})
    return menu


def frontend_view(entry: dict[str, Any]) -> dict[str, Any]:
    """Resumo sem caminhos locais para a futura página do município."""

    return {
        "ibge": entry["municipality"]["ibge"],
        "name": entry["municipality"]["name"],
        "title": f"NDVI de {entry['municipality']['name']}",
        "image_date": entry["image_date"],
        "valid_image_date": entry["image_date"],
        "latest_attempted_image_date": entry["image_date"],
        "dates_differ": False,
        "valid_pixel_fraction": entry["valid_pixel_fraction"],
        "quality_status": entry["quality"]["status"],
        "message_pt": entry["quality"]["note_pt"],
        "style": entry["style"],
        "files": file_states(entry),
        "public_downloads": download_menu(entry),
        "published": False,
    }
