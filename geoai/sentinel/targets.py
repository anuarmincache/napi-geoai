"""Municípios-alvo do NDVI estadual: população estimada acima de um limiar.

A lista é derivada (classe B) de dois artefatos já validados: o painel de
população IBGE e a malha municipal. Nada aqui baixa cena, mede pixel ou
publica NDVI. Estar na lista não significa ter imagem processada.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.sentinel.aoi import sirgas_utm_epsg

POPULATION_THRESHOLD = 20_000
POPULATION_FIELD = "populacao_estimada_2026_hab"
TARGETS_NAME = "ndvi_targets_pr.json"
PLAN_NAME = "ndvi_plan_pr.json"


def targets_path(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "derived" / TARGETS_NAME


def plan_path(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "derived" / PLAN_NAME


def sentinel_utm_epsg(longitude: float, latitude: float) -> int:
    """EPSG WGS 84 / UTM da grade Sentinel-2 (327xx no hemisfério sul)."""

    sirgas = sirgas_utm_epsg(longitude, latitude)
    zone = sirgas - (31960 if latitude < 0 else 31936)
    return (32700 if latitude < 0 else 32600) + zone


def build_ndvi_targets(
    population_panel: dict[str, Any],
    mesh_geojson: dict[str, Any],
    *,
    threshold: int = POPULATION_THRESHOLD,
) -> dict[str, Any]:
    """Seleciona municípios com população estritamente acima de ``threshold``."""

    from shapely.geometry import shape

    shapes: dict[str, Any] = {}
    for feature in mesh_geojson.get("features") or []:
        code = str((feature.get("properties") or {}).get("CD_MUN") or "").strip()
        if code:
            shapes[code] = shape(feature["geometry"])

    rows = []
    for item in population_panel.get("municipalities") or []:
        population = item.get(POPULATION_FIELD)
        if population is None or int(population) <= int(threshold):
            continue
        code = str(item["CD_MUN"])
        if code not in shapes:
            raise ValueError(f"CD_MUN {code} sem geometria na malha")
        geom = shapes[code]
        minx, miny, maxx, maxy = geom.bounds
        point = geom.representative_point()
        rows.append(
            {
                "cd_mun": code,
                "name": str(item["NM_MUN"]),
                "population": int(population),
                "area_km2": float(item["area_km2_ibge_2025"]),
                "bbox": [round(v, 6) for v in (minx, miny, maxx, maxy)],
                "label_point": [round(point.x, 6), round(point.y, 6)],
                "sentinel_utm_epsg": sentinel_utm_epsg(point.x, point.y),
            }
        )
    rows.sort(key=lambda r: (-r["population"], r["cd_mun"]))
    zones: dict[str, int] = {}
    for row in rows:
        key = str(row["sentinel_utm_epsg"])
        zones[key] = zones.get(key, 0) + 1
    return {
        "schema_version": 1,
        "rule_pt": (
            f"Municípios do Paraná com população estimada IBGE acima de "
            f"{int(threshold):,} habitantes".replace(",", ".")
            + f" (campo {POPULATION_FIELD})."
        ),
        "threshold": int(threshold),
        "population_reference_date": population_panel.get(
            "population_reference_date"
        ),
        "geometry_note_pt": (
            "bbox e ponto de rótulo calculados na malha de apresentação "
            "(simplificada). A AOI de processamento usa a malha oficial."
        ),
        "aoi_note_pt": (
            "A AOI é o município inteiro, como no piloto de Maringá. Inclui "
            "área rural: o NDVI municipal reflete sobretudo lavoura e "
            "vegetação, não apenas a área urbana."
        ),
        "count": len(rows),
        "total_area_km2": round(sum(r["area_km2"] for r in rows), 3),
        "by_sentinel_utm_epsg": zones,
        "targets": rows,
    }


def load_ndvi_targets(repo_root: Path) -> dict[str, Any] | None:
    path = targets_path(repo_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("schema_version") != 1 or len(data.get("targets") or []) != data.get(
        "count"
    ):
        return None
    return data


def load_ndvi_plan(repo_root: Path) -> dict[str, Any] | None:
    path = plan_path(repo_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if data.get("schema_version") in (1, 2) else None


def target_status(
    cd_mun: str,
    pilot_catalog: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """Estado público de um alvo. Nunca promove plano a medição."""

    catalog = pilot_catalog or {}
    aoi = catalog.get("aoi") or {}
    if str(aoi.get("cd_mun")) == str(cd_mun) and catalog.get("aoi_measurements"):
        last = catalog["aoi_measurements"][-1]
        published = bool(catalog.get("ndvi_published"))
        return {
            "code": "publicado" if published else "medido",
            "label_pt": (
                "NDVI publicado" if published else "Cena medida, NDVI não publicado"
            ),
            "acquisition_id": last.get("acquisition_id"),
            "valid_fraction": last.get("valid_fraction"),
        }
    entry = ((plan or {}).get("targets") or {}).get(str(cd_mun))
    if entry:
        if entry.get("selected_acquisition"):
            return {
                "code": "planejado",
                "label_pt": "Passagem candidata encontrada, sem medição",
                "acquisition_id": entry["selected_acquisition"],
                "valid_fraction": None,
            }
        return {
            "code": "sem_passagem",
            "label_pt": "Sem passagem aproveitável na janela",
            "acquisition_id": None,
            "valid_fraction": None,
        }
    return {
        "code": "aguardando",
        "label_pt": "Aguardando planejamento e processamento",
        "acquisition_id": None,
        "valid_fraction": None,
    }
