"""Alvos e plano do NDVI estadual. Cenas de teste são sintéticas."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from geoai.portal.paths import municipalities_geojson_path, population_panel_path
from geoai.sentinel.targets import (
    build_ndvi_targets,
    load_ndvi_targets,
    sentinel_utm_epsg,
    target_status,
)

REPO = Path(__file__).resolve().parents[1]
MARINGA = "4115200"


def _load(name: str):
    path = REPO / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> dict:
    population = json.loads(population_panel_path(REPO).read_text(encoding="utf-8"))
    mesh = json.loads(municipalities_geojson_path(REPO).read_text(encoding="utf-8"))
    return build_ndvi_targets(population, mesh)


def test_targets_follow_population_rule() -> None:
    registry = _registry()
    population = json.loads(population_panel_path(REPO).read_text(encoding="utf-8"))
    expected = {
        str(m["CD_MUN"])
        for m in population["municipalities"]
        if (m.get("populacao_estimada_2026_hab") or 0) > 20_000
    }
    codes = [t["cd_mun"] for t in registry["targets"]]
    assert set(codes) == expected and len(codes) == registry["count"]
    assert MARINGA in expected
    pops = [t["population"] for t in registry["targets"]]
    assert pops == sorted(pops, reverse=True)
    assert all(t["population"] > 20_000 for t in registry["targets"])
    assert sum(registry["by_sentinel_utm_epsg"].values()) == registry["count"]


def test_versioned_registry_matches_rebuild() -> None:
    stored = load_ndvi_targets(REPO)
    assert stored is not None, "rode scripts/prepare_ndvi_targets.py"
    assert stored == _registry()


def test_west_of_54w_uses_utm_21s() -> None:
    assert sentinel_utm_epsg(-51.93, -23.42) == 32722  # Maringá
    assert sentinel_utm_epsg(-54.58, -25.54) == 32721  # Foz do Iguaçu
    by_name = {t["name"]: t for t in _registry()["targets"]}
    assert by_name["Foz do Iguaçu"]["sentinel_utm_epsg"] == 32721
    assert by_name["Maringá"]["sentinel_utm_epsg"] == 32722


def test_status_never_promotes_plan_to_measurement() -> None:
    catalog = {
        "aoi": {"cd_mun": MARINGA},
        "ndvi_published": False,
        "aoi_measurements": [{"acquisition_id": "A", "valid_fraction": 0.73}],
    }
    plan = {"targets": {"4106902": {"selected_acquisition": "B"}, "1": {}}}
    assert target_status(MARINGA, catalog, plan)["code"] == "medido"
    planned = target_status("4106902", catalog, plan)
    assert planned["code"] == "planejado" and planned["valid_fraction"] is None
    assert target_status("1", catalog, {"targets": {"1": {"x": 1}}})["code"] == (
        "sem_passagem"
    )
    assert target_status("4113700", catalog, plan)["code"] == "aguardando"
    assert target_status("4113700", None, None)["code"] == "aguardando"


def _feature(product_id: str, bbox: list[float], sizes: tuple[int, int, int]):
    minx, miny, maxx, maxy = bbox
    ring = [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
    return {
        "id": product_id,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"datetime": "2026-11-12T13:31:49Z", "eo:cloud_cover": 12.5},
        "assets": {
            band: {"file:size": size, "proj:code": "EPSG:32722"}
            for band, size in zip(
                ("B04_10m", "B08_10m", "SCL_20m"), sizes, strict=True
            )
        },
    }


def test_plan_counts_each_scene_once(monkeypatch: pytest.MonkeyPatch) -> None:
    planner = _load("plan_ndvi_targets.py")
    search = planner._pilot_search()
    mesh = municipalities_geojson_path(REPO)
    registry = _registry()
    by_name = {t["name"]: t for t in registry["targets"]}
    targets = [by_name["Maringá"], by_name["Sarandi"]]
    wide = [-53.0, -24.5, -51.0, -22.5]  # cobre os dois municípios vizinhos
    scene = _feature(
        "S2B_MSIL2A_20261112T133149_N0513_R081_T22KCV_20261112T184116",
        wide,
        (100, 200, 30),
    )
    far = _feature(
        "S2B_MSIL2A_20261112T133149_N0513_R081_T22KDV_20261112T184116",
        [-49.0, -24.5, -48.0, -22.5],
        (1, 1, 1),
    )
    monkeypatch.setattr(search, "_search_pages", lambda body: ([scene, far], False))
    records = {
        t["cd_mun"]: planner.plan_target(search, t, mesh, "2026-11-04/2026-11-19")
        for t in targets
    }
    for record in records.values():
        assert record["selected_acquisition"] == "S2B_20261112T133149_R081"
        assert [t["mgrs_tile"] for t in record["tiles"]] == ["22KCV"]
    summary = planner.summarize(records)
    assert summary["targets_with_pass"] == 2
    assert summary["distinct_products"] == 1  # a cena serve os dois municípios
    assert summary["official_bytes_known"] == 330
    assert summary["band_files_without_official_size"] == 0

    monkeypatch.setattr(search, "_search_pages", lambda body: ([far], False))
    empty = planner.plan_target(search, targets[0], mesh, "2026-11-04/2026-11-19")
    assert empty["selected_acquisition"] is None and empty["tiles"] == []
    assert planner.summarize({"x": empty})["targets_without_pass"] == ["Maringá"]
