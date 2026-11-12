"""Prepara painel energético SIGA/PR: download, qualidade, join, agregados.

CSV bruto permanece em data/raw/aneel/ (gitignored).
Artefatos leves vão para data/derived/.

Uso:
  py -3 scripts/prepare_siga_parana.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.connectors.aneel import (  # noqa: E402
    ANEEL_LICENSE_NOTE,
    ANEEL_SIGA_CSV_URL,
    ANEEL_SIGA_SOURCE_ID,
    download_siga_csv,
    parse_siga_file,
)
from geoai.connectors.http_fetch import sha256_file  # noqa: E402
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT  # noqa: E402
from geoai.energy.siga_aggregate import (  # noqa: E402
    PHASE_OPERACAO,
    aggregate_plants_by_municipality,
    energy_panel_path,
    energy_provenance_path,
    energy_quality_path,
)
from geoai.energy.siga_normalize import normalize_siga_rows  # noqa: E402
from geoai.energy.siga_spatial import join_plants_to_municipalities  # noqa: E402
from geoai.portal.municipal_explorer import load_municipality_layer  # noqa: E402
from geoai.portal.paths import derived_dir  # noqa: E402


def main() -> int:
    raw_dir = REPO / "data" / "raw" / "aneel"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = raw_dir / "siga-empreendimentos-geracao.csv"
    mun_zip = REPO / "data" / "raw" / "ibge" / "PR_Municipios_2025.zip"
    if not mun_zip.is_file():
        raise SystemExit(f"ZIP municipal ausente: {mun_zip}")

    print("download SIGA…")
    ingest = download_siga_csv(csv_path, timeout_s=300.0)
    rows_pr = parse_siga_file(csv_path, uf="PR")
    accepted, rejected = normalize_siga_rows(rows_pr, uf="PR")
    print(
        f"PR brutos={len(rows_pr)} aceitos={len(accepted)} "
        f"rejeitados={len(rejected)}"
    )

    joined, join_stats = join_plants_to_municipalities(accepted, municipios_zip=mun_zip)
    print("join", join_stats)

    bundle = load_municipality_layer(REPO)
    if not bundle.available:
        raise SystemExit(bundle.missing_reason_pt or "malha municipal indisponível")
    catalog = [
        {"CD_MUN": str(r["CD_MUN"]), "NM_MUN": str(r["NM_MUN"])}
        for _, r in bundle.gdf[["CD_MUN", "NM_MUN"]].iterrows()
    ]
    if len(catalog) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise SystemExit(f"catálogo municipal != 399 ({len(catalog)})")

    panel = aggregate_plants_by_municipality(
        joined, catalog, phase=PHASE_OPERACAO
    )
    # Strip heavy plant lists from panel file for size — keep top summary only
    slim_munis = []
    for m in panel["municipalities"]:
        slim = {k: v for k, v in m.items() if k != "empreendimentos"}
        slim_munis.append(slim)
    panel_out = dict(panel)
    panel_out["municipalities"] = slim_munis
    # plants detail file (operação matched)
    plants_detail = []
    for m in panel["municipalities"]:
        for plant in m.get("empreendimentos") or []:
            plants_detail.append(
                {
                    **plant,
                    "CD_MUN": m["CD_MUN"],
                    "NM_MUN": m["NM_MUN"],
                }
            )
    plants_detail.extend(panel["nao_associados"])

    phase_counter = Counter(p.phase for p in accepted)
    tipo_counter = Counter(p.tipo_geracao for p in accepted)
    quality = {
        "product": "siga_pr_quality",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_id": ANEEL_SIGA_SOURCE_ID,
        "uf": "PR",
        "rows_pr_raw": len(rows_pr),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "rejected_reasons": dict(Counter(r.reject_reason for r in rejected)),
        "phases": dict(phase_counter),
        "tipos_geracao": dict(tipo_counter),
        "coord_ok": sum(1 for p in accepted if p.coord_ok),
        "coord_missing": sum(1 for p in accepted if not p.coord_ok),
        "join_geopandas": join_stats,
        "dat_conjunto_sample": next(
            (p.dat_conjunto for p in accepted if p.dat_conjunto), None
        ),
        "mmgd_included": False,
        "not_energy_generated_mwh": True,
    }

    provenance = {
        "source_id": ANEEL_SIGA_SOURCE_ID,
        "url": ANEEL_SIGA_CSV_URL,
        "license_note": ANEEL_LICENSE_NOTE,
        "retrieved_at": ingest.provenance.retrieved_at,
        "content_sha256": ingest.provenance.content_sha256,
        "content_length": ingest.provenance.content_length,
        "local_csv": "data/raw/aneel/siga-empreendimentos-geracao.csv",
        "http_etag": ingest.provenance.http_etag,
        "http_last_modified": ingest.provenance.http_last_modified,
        "municipios_zip": "data/raw/ibge/PR_Municipios_2025.zip",
        "municipios_zip_sha256": sha256_file(mun_zip),
        "phase_default": PHASE_OPERACAO,
        "metric": "MdaPotenciaFiscalizadaKw (MW = kW/1000)",
        "metric_secondary": "MdaPotenciaOutorgadaKw",
        "crs_join": "EPSG:4674 (pontos ANEEL lat/lon → SIRGAS 2000)",
        "prepared_at": datetime.now(UTC).isoformat(),
        "attribution_pt": (
            "ANEEL — Sistema de Informações de Geração (SIGA), Dados Abertos (ODbL). "
            "Malha municipal IBGE municipio_2025."
        ),
    }

    out_dir = derived_dir(REPO)
    out_dir.mkdir(parents=True, exist_ok=True)
    energy_panel_path(REPO).write_text(
        json.dumps(panel_out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    energy_provenance_path(REPO).write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    energy_quality_path(REPO).write_text(
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "siga_pr_operacao_plants.json").write_text(
        json.dumps(
            {
                "phase": PHASE_OPERACAO,
                "count": len(plants_detail),
                "plants": plants_detail,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("wrote", energy_panel_path(REPO))
    print("totals", panel_out["totals"])
    print(
        "municipios com empreendimentos",
        sum(1 for m in slim_munis if m["status_dados"] == "agregado"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
