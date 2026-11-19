"""Planeja o NDVI dos municípios-alvo: só consulta o catálogo STAC oficial.

Uso (na raiz do repositório):
  python scripts/plan_ndvi_targets.py [--as-of 2026-11-19T12:00:00Z] [--days 15]

Não autentica, não baixa banda, não mede pixel e não publica NDVI. Para cada
município-alvo, procura a passagem Sentinel-2 L2A mais recente, na janela
pedida, cujas tiles cobrem pelo menos 99,9% do polígono oficial, com a mesma
regra do piloto de Maringá (uma única passagem, sem misturar datas).

O resultado responde, com números do catálogo, quantas cenas distintas um
ciclo exige e quantos bytes de B04, B08 e SCL elas somam. Cobertura do
footprint e nuvem do item não são fração de pixels válidos.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.sentinel.aoi import load_official_municipality  # noqa: E402
from geoai.sentinel.assets import BANDS  # noqa: E402
from geoai.sentinel.pilot import (  # noqa: E402
    MESH_RELATIVE,
    MIN_FOOTPRINT_COVERAGE,
    STAC_COLLECTION,
    STAC_SEARCH_URL,
)
from geoai.sentinel.targets import load_ndvi_targets, plan_path  # noqa: E402
from geoai.sentinel.windows import parse_as_of  # noqa: E402


def _pilot_search():
    """Reusa a busca e a regra de passagem do piloto, sem duplicar código."""

    path = REPO / "scripts" / "search_sentinel_pilot.py"
    spec = importlib.util.spec_from_file_location("search_sentinel_pilot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _band_sizes(feature: dict[str, Any]) -> dict[str, int | None]:
    assets = feature.get("assets") or {}
    sizes: dict[str, int | None] = {}
    for band in BANDS:
        raw = (assets.get(band) or {}).get("file:size")
        sizes[band] = int(raw) if isinstance(raw, (int, float)) else None
    return sizes


def plan_target(
    search, target: dict[str, Any], mesh_zip: Path, window: str
) -> dict[str, Any]:
    municipality = load_official_municipality(mesh_zip, target["cd_mun"])
    body = {
        "collections": [STAC_COLLECTION],
        "bbox": municipality.bbox,
        "datetime": window,
        "limit": 100,
    }
    features, truncated = search._search_pages(body)
    by_id = {str(f.get("id")): f for f in features}
    scenes = search._evaluate(features, municipality)
    plans = search._acquisition_plans(scenes, municipality)
    selected = search._choose_acquisition(plans)
    record: dict[str, Any] = {
        "cd_mun": target["cd_mun"],
        "name": target["name"],
        "coverage_crs": municipality.coverage_crs,
        "scenes_found": len(features),
        "acquisitions_found": len(plans),
        "acquisitions_covering": sum(1 for p in plans if p.get("covers_threshold")),
        "truncated": bool(truncated),
        "selected_acquisition": None,
        "sensing_time_utc": None,
        "tiles": [],
    }
    if selected is None:
        return record
    record["selected_acquisition"] = selected["acquisition_id"]
    record["sensing_time_utc"] = selected["sensing_time_utc"]
    record["mosaic_required"] = bool(selected["mosaic_required"])
    for tile in selected["tiles"]:
        if not tile["selected"]:
            continue
        feature = by_id.get(str(tile["product_id"])) or {}
        record["tiles"].append(
            {
                "mgrs_tile": tile["mgrs_tile"],
                "product_id": tile["product_id"],
                "aoi_coverage": tile["aoi_coverage"],
                "eo_cloud_cover": tile["eo_cloud_cover"],
                "proj_code": ((feature.get("assets") or {}).get("B04_10m") or {}).get(
                    "proj:code"
                ),
                "band_bytes": _band_sizes(feature),
            }
        )
    return record


def summarize(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    products: dict[str, dict[str, Any]] = {}
    for record in records.values():
        for tile in record["tiles"]:
            products.setdefault(str(tile["product_id"]), tile)
    sizes = [
        size
        for tile in products.values()
        for size in tile["band_bytes"].values()
    ]
    known = [s for s in sizes if s is not None]
    return {
        "targets": len(records),
        "targets_with_pass": sum(
            1 for r in records.values() if r["selected_acquisition"]
        ),
        "targets_without_pass": sorted(
            r["name"] for r in records.values() if not r["selected_acquisition"]
        ),
        "targets_needing_mosaic": sum(
            1 for r in records.values() if r.get("mosaic_required")
        ),
        "distinct_products": len(products),
        "distinct_mgrs_tiles": sorted({t["mgrs_tile"] for t in products.values()}),
        "distinct_acquisitions": sorted(
            {
                str(r["selected_acquisition"])
                for r in records.values()
                if r["selected_acquisition"]
            }
        ),
        "band_files": len(sizes),
        "band_files_without_official_size": len(sizes) - len(known),
        "official_bytes_known": int(sum(known)),
        "bytes_note_pt": (
            "Soma dos tamanhos oficiais (file:size) de B04, B08 e SCL das "
            "cenas distintas. Cada cena conta uma vez, mesmo servindo vários "
            "municípios. Se houver arquivo sem tamanho oficial, a soma é parcial."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--as-of", default=None, help="Instante UTC RFC3339")
    parser.add_argument("--days", type=int, default=15, help="Janela em dias")
    parser.add_argument("--limit", type=int, default=None, help="Só os N maiores")
    args = parser.parse_args(argv)
    if args.days <= 0:
        raise SystemExit("--days deve ser positivo")

    registry = load_ndvi_targets(REPO)
    if registry is None:
        raise SystemExit(
            "lista de alvos ausente: rode scripts/prepare_ndvi_targets.py"
        )
    mesh_zip = REPO / MESH_RELATIVE
    if not mesh_zip.is_file():
        raise SystemExit(
            f"malha oficial ausente em {MESH_RELATIVE}: rode "
            "scripts/prepare_parana_municipalities.py"
        )
    targets = registry["targets"][: args.limit] if args.limit else registry["targets"]
    as_of = parse_as_of(args.as_of)
    window = f"{_stamp(as_of - timedelta(days=args.days))}/{_stamp(as_of)}"
    search = _pilot_search()

    started = time.perf_counter()
    records: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    for index, target in enumerate(targets, start=1):
        try:
            record = plan_target(search, target, mesh_zip, window)
        except Exception as error:  # noqa: BLE001 — registra e segue
            failures[target["cd_mun"]] = f"{type(error).__name__}: {error}"[:200]
            print(f"[{index}/{len(targets)}] {target['name']}: FALHA", flush=True)
            continue
        records[target["cd_mun"]] = record
        chosen = record["selected_acquisition"] or "sem passagem que cubra"
        tiles = ",".join(t["mgrs_tile"] for t in record["tiles"])
        print(
            f"[{index}/{len(targets)}] {target['name']}: {chosen} {tiles}",
            flush=True,
        )

    payload = {
        "schema_version": 1,
        "kind": "plano_stac_sem_download",
        "queried_at_utc": _stamp(datetime.now(UTC)),
        "as_of_utc": _stamp(as_of),
        "window_days": args.days,
        "window_utc": window,
        "stac_search_url": STAC_SEARCH_URL,
        "collection": STAC_COLLECTION,
        "min_footprint_coverage": MIN_FOOTPRINT_COVERAGE,
        "temporal_rule_pt": (
            "Uma única passagem por município (mesmo satélite, mesmo instante "
            "e mesma órbita relativa). Datas não se misturam."
        ),
        "limits_pt": [
            "Plano de catálogo: nenhuma banda foi baixada e nenhum pixel medido.",
            "Cobertura do footprint não é fração de pixels válidos.",
            "Nuvem do item (eo:cloud_cover) é da tile inteira, não do município.",
            "A fração válida só existe depois da leitura de B04, B08 e SCL.",
        ],
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "targets_requested": len(targets),
        "failures": failures,
        "summary": summarize(records),
        "targets": records,
    }
    out = plan_path(REPO)
    tmp = out.with_suffix(".json.partial")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    tmp.replace(out)
    summary = payload["summary"]
    print(f"gravado {out.relative_to(REPO)}")
    print(
        f"{summary['targets_with_pass']}/{summary['targets']} municípios com "
        f"passagem · {summary['distinct_products']} cenas distintas em "
        f"{len(summary['distinct_mgrs_tiles'])} tiles · "
        f"{summary['official_bytes_known'] / 1e9:.2f} GB oficiais conhecidos · "
        f"{len(failures)} falha(s)"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
