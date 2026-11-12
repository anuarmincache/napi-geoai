"""Prepara painel populacional IBGE 2026 + indicadores SIGA per capita.

Uso:
  py -3 scripts/prepare_population_parana.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.connectors.http_fetch import sha256_file  # noqa: E402
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT  # noqa: E402
from geoai.connectors.ibge_population import (  # noqa: E402
    IBGE_POP_DOWNLOAD_URL,
    IBGE_POP_EDITION_ID,
    IBGE_POP_ENTRY_URL,
    IBGE_POP_LICENSE_NOTE,
    IBGE_POP_REFERENCE_DATE,
    IBGE_POP_SOURCE_ID,
    default_population_xlsx_path,
    download_population_xlsx,
)
from geoai.energy.siga_aggregate import load_energy_panel_bundle  # noqa: E402
from geoai.population.panel import (  # noqa: E402
    build_population_energy_panel,
    population_panel_path,
    population_provenance_path,
    population_quality_path,
)
from geoai.population.parse import (  # noqa: E402
    assert_codes_match_mesh,
    parse_municipality_populations,
)
from geoai.portal.municipal_explorer import load_municipality_layer  # noqa: E402
from geoai.portal.paths import derived_dir  # noqa: E402


def main() -> int:
    raw_dir = REPO / "data" / "raw" / "ibge"
    xlsx = default_population_xlsx_path(raw_dir)
    print("download estimativas IBGE 2026…")
    ingest = download_population_xlsx(xlsx, timeout_s=180.0)
    print("sha", ingest.provenance.content_sha256)

    records, parse_quality = parse_municipality_populations(xlsx, uf="PR")
    print(
        "PR municípios",
        len(records),
        "soma",
        parse_quality["population_sum_municipalities"],
    )

    mun = load_municipality_layer(REPO)
    if not mun.available:
        raise SystemExit(mun.missing_reason_pt or "malha ausente")
    mesh_codes = {str(c) for c in mun.gdf["CD_MUN"].astype(str)}
    assert_codes_match_mesh(records, mesh_codes)

    mesh_rows = [
        {
            "CD_MUN": str(r["CD_MUN"]),
            "NM_MUN": str(r["NM_MUN"]),
            "AREA_KM2": float(r["AREA_KM2"]),
        }
        for _, r in mun.gdf[["CD_MUN", "NM_MUN", "AREA_KM2"]].iterrows()
    ]
    pop_by = {r["CD_MUN"]: r for r in records}

    energy = load_energy_panel_bundle(REPO)
    energy_by: dict[str, dict] = {}
    nao_n = 0
    if energy.available:
        nao_n = len(energy.panel.get("nao_associados") or [])
        for m in energy.panel.get("municipalities") or []:
            energy_by[str(m["CD_MUN"])] = {
                "n_empreendimentos": m.get("n_empreendimentos"),
                "potencia_fiscalizada_mw": m.get("potencia_fiscalizada_mw"),
                "potencia_fiscalizada_completa": m.get(
                    "potencia_fiscalizada_completa", True
                ),
                "status_dados": m.get("status_dados"),
            }
    else:
        print("AVISO: painel SIGA ausente — indicadores kW/hab sem energia")

    panel = build_population_energy_panel(
        mesh_rows=mesh_rows,
        population_by_code=pop_by,
        energy_by_code=energy_by,
        nao_associados_n=nao_n,
    )

    quality = {
        "product": "ibge_pr_population_2026_quality",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_id": IBGE_POP_SOURCE_ID,
        "edition_id": IBGE_POP_EDITION_ID,
        "reference_date": IBGE_POP_REFERENCE_DATE,
        "codes_match_mesh": True,
        "municipality_count": EXPECTED_PR_MUNICIPALITY_COUNT,
        "parse": parse_quality,
        "energy_panel_available": energy.available,
        "nao_associados_siga_n": nao_n,
        "not_census": True,
        "not_mmgd": True,
        "not_energy_mwh": True,
        "xlsx_sha256": ingest.provenance.content_sha256,
        "mesh_presentation_sha256": (mun.provenance or {}).get(
            "derived_geojson_sha256"
        )
        or (mun.provenance or {}).get("content_sha256"),
    }

    provenance = {
        "source_id": IBGE_POP_SOURCE_ID,
        "url": IBGE_POP_DOWNLOAD_URL,
        "entry_url": IBGE_POP_ENTRY_URL,
        "license_note": IBGE_POP_LICENSE_NOTE,
        "edition_id": IBGE_POP_EDITION_ID,
        "reference_date": IBGE_POP_REFERENCE_DATE,
        "retrieved_at": ingest.provenance.retrieved_at,
        "content_sha256": ingest.provenance.content_sha256,
        "content_length": ingest.provenance.content_length,
        "local_xlsx": f"data/raw/ibge/{xlsx.name}",
        "municipios_malha": "data/raw/ibge/PR_Municipios_2025.zip",
        "prepared_at": datetime.now(UTC).isoformat(),
        "attribution_pt": (
            "IBGE — Estimativas da população residente em 1º de julho de 2026 "
            f"(edição {IBGE_POP_EDITION_ID}). Malha municipal IBGE 2025. "
            "Capacidade: ANEEL SIGA (quando disponível)."
        ),
        "xlsx_bytes_sha256_verify": sha256_file(xlsx),
    }

    out = derived_dir(REPO)
    out.mkdir(parents=True, exist_ok=True)
    population_panel_path(REPO).write_text(
        json.dumps(panel, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    population_provenance_path(REPO).write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    population_quality_path(REPO).write_text(
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", population_panel_path(REPO))
    print(
        "municípios",
        panel["municipality_count"],
        "pop_sum",
        panel["population_sum_hab"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
