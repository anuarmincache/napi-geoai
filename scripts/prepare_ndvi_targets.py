"""Gera a lista de municípios-alvo do NDVI (população IBGE acima de 20 mil).

Uso (na raiz do repositório):
  python scripts/prepare_ndvi_targets.py

Sem rede. Lê só artefatos derivados já validados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.portal.paths import (  # noqa: E402
    municipalities_geojson_path,
    population_panel_path,
)
from geoai.sentinel.targets import build_ndvi_targets, targets_path  # noqa: E402


def main() -> int:
    population = json.loads(population_panel_path(REPO).read_text(encoding="utf-8"))
    mesh = json.loads(municipalities_geojson_path(REPO).read_text(encoding="utf-8"))
    payload = build_ndvi_targets(population, mesh)
    out = targets_path(REPO)
    tmp = out.with_suffix(".json.partial")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    tmp.replace(out)
    print(f"gravado {out.relative_to(REPO)}")
    print(
        f"{payload['count']} municípios · {payload['total_area_km2']:,.0f} km² · "
        f"zonas UTM {payload['by_sentinel_utm_epsg']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
