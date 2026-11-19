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
    assert empty["candidates"] == []
    assert len(records[targets[0]["cd_mun"]]["candidates"]) == 1


def _cand(acq: str, when: str, tiles: list[tuple[str, float, float]]) -> dict:
    return {
        "acquisition_id": acq,
        "sensing_time_utc": when,
        "tiles": [
            {
                "mgrs_tile": name,
                "product_id": f"{acq}_{name}",
                "aoi_coverage": coverage,
                "eo_cloud_cover": cloud,
                "band_bytes": {"B04_10m": 100, "B08_10m": 100, "SCL_20m": 2},
            }
            for name, cloud, coverage in tiles
        ],
    }


def test_weighted_cloud_uses_municipal_coverage() -> None:
    from geoai.sentinel.cycle_plan import weighted_cloud

    tiles = _cand("A", "t", [("X", 10.0, 0.9), ("Y", 90.0, 0.1)])["tiles"]
    assert weighted_cloud(tiles) == pytest.approx(18.0)
    tiles[0]["eo_cloud_cover"] = None
    assert weighted_cloud(tiles) is None  # sem dado não vira zero


def test_optimizer_drops_cloudy_passes_and_shares_scenes() -> None:
    from geoai.sentinel.cycle_plan import optimize_cycle, summarize_selection

    clear_old = _cand("OLD", "2026-11-10T13:00:00Z", [("22KCV", 5.0, 1.0)])
    cloudy_new = _cand("NEW", "2026-11-19T13:00:00Z", [("22KCV", 95.0, 1.0)])
    other_clear = _cand("MID", "2026-11-15T13:00:00Z", [("22KDV", 5.0, 1.0)])
    records = {
        # só tem a passagem limpa antiga
        "1": {"candidates": [clear_old, cloudy_new]},
        # pode usar a cena de "1" (reuso) ou outra cena igualmente limpa
        "2": {"candidates": [other_clear, clear_old]},
        # só passagem nublada: fica sem imagem, não baixa nada
        "3": {"candidates": [cloudy_new]},
        "4": {"candidates": []},
    }
    selection = optimize_cycle(records, max_cloud=40.0)
    assert selection["1"]["selected_acquisition"] == "OLD"
    assert selection["2"]["selected_acquisition"] == "OLD"  # reuso da cena
    assert selection["3"]["selected_acquisition"] is None
    assert selection["3"]["reason"] == "todas_acima_do_limite_de_nuvem"
    assert selection["4"]["reason"] == "sem_passagem_cobrindo"
    summary = summarize_selection(selection, {"3": "C", "4": "D"})
    assert summary["distinct_products"] == 1
    assert summary["stage1_mask_bytes"] == 2
    assert summary["stage2_bands_bytes_max"] == 200
    assert summary["scenes_with_cloud_above_50"] == 0
    assert summary["targets_without_pass"] == ["C", "D"]


def test_optimizer_prefers_clearer_then_newer_on_equal_cost() -> None:
    from geoai.sentinel.cycle_plan import optimize_cycle

    a = _cand("A", "2026-11-10T13:00:00Z", [("T1", 30.0, 1.0)])
    b = _cand("B", "2026-11-12T13:00:00Z", [("T1", 10.0, 1.0)])
    c = _cand("C", "2026-11-15T13:00:00Z", [("T1", 10.0, 1.0)])
    chosen = optimize_cycle({"1": {"candidates": [a, b, c]}})["1"]
    assert chosen["selected_acquisition"] == "C"
    assert chosen["weighted_cloud"] == 10.0
