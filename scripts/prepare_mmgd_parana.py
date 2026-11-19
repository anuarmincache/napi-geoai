"""Prepara painel MMGD-PR a partir do ZIP oficial ANEEL.

Uso (na raiz do worktree):
  py -3 scripts/prepare_mmgd_parana.py

O CSV bruto permanece em data/raw/aneel/ (gitignored).
Artefatos leves (sem CPF/nome/CEP) vão para data/derived/.
"""

from __future__ import annotations

import json
import sys
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.connectors.aneel_mmgd import (  # noqa: E402
    ANEEL_MMGD_LICENSE_NOTE,
    ANEEL_MMGD_SOURCE_ID,
    ANEEL_MMGD_ZIP_URL,
    download_mmgd_zip,
    iter_mmgd_rows,
)
from geoai.connectors.http_fetch import sha256_file  # noqa: E402
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT  # noqa: E402
from geoai.energy.mmgd_aggregate import aggregate_mmgd_by_municipality  # noqa: E402
from geoai.energy.mmgd_normalize import normalize_mmgd_row  # noqa: E402
from geoai.portal.paths import (  # noqa: E402
    derived_dir,
    municipalities_geojson_path,
    municipalities_validation_path,
)


def _load_ibge_codes(repo: Path) -> set[str]:
    validation = json.loads(
        municipalities_validation_path(repo).read_text(encoding="utf-8")
    )
    if validation.get("feature_count") != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise SystemExit("validação IBGE: feature_count != 399")
    if validation.get("unique_cd_mun") != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise SystemExit("validação IBGE: unique_cd_mun != 399")
    geojson = json.loads(
        municipalities_geojson_path(repo).read_text(encoding="utf-8")
    )
    codes = {
        str(feat.get("properties", {}).get("CD_MUN", "")).strip()
        for feat in geojson.get("features", [])
    }
    codes.discard("")
    if len(codes) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise SystemExit(f"GeoJSON presentation: {len(codes)} códigos != 399")
    if not all(c.startswith("41") and len(c) == 7 and c.isdigit() for c in codes):
        raise SystemExit("códigos IBGE inválidos no GeoJSON")
    return codes


def main() -> int:
    raw_dir = REPO / "data" / "raw" / "aneel"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "empreendimento-geracao-distribuida.zip"

    print("download/validação ZIP…")
    t_dl0 = time.perf_counter()
    ingest = download_mmgd_zip(zip_path, timeout_s=600.0)
    t_dl = time.perf_counter() - t_dl0
    print(
        f"ZIP ok size={ingest.provenance.content_length} "
        f"sha256={ingest.provenance.content_sha256} elapsed_s={t_dl:.3f}"
    )

    ibge_codes = _load_ibge_codes(REPO)
    print(f"IBGE codes={len(ibge_codes)}")

    print("agregando PR (streaming, uma passagem)…")
    tracemalloc.start()
    t0 = time.perf_counter()
    n_national = 0

    def plants_pr():
        nonlocal n_national
        for row in iter_mmgd_rows(zip_path, uf=None, public_only=True):
            n_national += 1
            if (row.get("SigUF") or "").strip().upper() != "PR":
                continue
            yield normalize_mmgd_row(row)

    panel = aggregate_mmgd_by_municipality(plants_pr(), ibge_codes=ibge_codes)
    elapsed = time.perf_counter() - t0
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    n_pr_from_panel = panel["n_valid"] + panel["n_rejected"]

    quality = {
        "source_id": ANEEL_MMGD_SOURCE_ID,
        "prepared_at": datetime.now(UTC).isoformat(),
        "rows_national": n_national,
        "rows_pr_streamed": n_pr_from_panel,
        "n_valid": panel["n_valid"],
        "n_rejected": panel["n_rejected"],
        "duplicate_cod_empreendimento": panel["duplicate_cod_empreendimento"],
        "municipios_com_registros": panel["municipios_com_registros"],
        "municipios_zero_confirmado": panel["municipios_zero_confirmado"],
        "ibge_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "potencia_instalada_kw_conhecida": panel["potencia_instalada_kw_conhecida"],
        "potencia_instalada_mw_conhecida": panel["potencia_instalada_mw_conhecida"],
        "qtd_uc_recebe_credito_total": panel["qtd_uc_recebe_credito_total"],
        "by_tipo": panel["by_tipo"],
        "by_classe": panel["by_classe"],
        "reject_reasons": panel["reject_reasons"],
        "reconcile_ok": (
            panel["n_valid"] + panel["n_rejected"] == n_pr_from_panel
            and panel["municipios_com_registros"]
            + panel["municipios_zero_confirmado"]
            == EXPECTED_PR_MUNICIPALITY_COUNT
        ),
        "unit_primary": panel["unit_primary"],
        "unit_secondary_uc_credito": panel["unit_secondary_uc_credito"],
        "temporal_note_pt": panel["temporal_note_pt"],
        "personal_fields_excluded": [
            "NumCPFCNPJ",
            "NomTitularEmpreendimento",
            "CodCEP",
            "NumCoordESub",
            "NumCoordNSub",
        ],
        "benchmark": {
            "download_elapsed_s": round(t_dl, 3),
            "aggregate_elapsed_s": round(elapsed, 3),
            "peak_tracemalloc_mb": round(peak / 1e6, 2),
            "zip_bytes": ingest.provenance.content_length,
            "zip_sha256": ingest.provenance.content_sha256,
        },
    }

    if not quality["reconcile_ok"]:
        raise SystemExit(f"reconciliação falhou: {quality}")

    provenance = {
        "source_id": ANEEL_MMGD_SOURCE_ID,
        "url": ANEEL_MMGD_ZIP_URL,
        "license_note": ANEEL_MMGD_LICENSE_NOTE,
        "retrieved_at": ingest.provenance.retrieved_at,
        "prepared_at": quality["prepared_at"],
        "content_sha256": ingest.provenance.content_sha256,
        "content_length": ingest.provenance.content_length,
        "http_etag": ingest.provenance.http_etag,
        "http_last_modified": ingest.provenance.http_last_modified,
        "local_zip": "data/raw/aneel/empreendimento-geracao-distribuida.zip",
        "dat_conjunto": panel["dat_conjunto"],
        "periodo_referencia": panel["periodo_referencia"],
        "municipios_validation_sha256": sha256_file(
            municipalities_validation_path(REPO)
        ),
    }

    out_dir = derived_dir(REPO)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel_path = out_dir / "mmgd_pr_panel.json"
    quality_path = out_dir / "mmgd_pr.quality.json"
    provenance_path = out_dir / "mmgd_pr.provenance.json"

    payload = {
        "source_id": ANEEL_MMGD_SOURCE_ID,
        "uf": "PR",
        "dat_conjunto": panel["dat_conjunto"],
        "periodo_referencia": panel["periodo_referencia"],
        "unit_primary": panel["unit_primary"],
        "unit_secondary_uc_credito": panel["unit_secondary_uc_credito"],
        "temporal_note_pt": panel["temporal_note_pt"],
        "totals": {
            "n_empreendimentos": panel["n_valid"],
            "potencia_instalada_kw_conhecida": panel[
                "potencia_instalada_kw_conhecida"
            ],
            "potencia_instalada_mw_conhecida": panel[
                "potencia_instalada_mw_conhecida"
            ],
            "qtd_uc_recebe_credito_total": panel["qtd_uc_recebe_credito_total"],
            "municipios_com_registros": panel["municipios_com_registros"],
            "municipios_zero_confirmado": panel["municipios_zero_confirmado"],
            "by_tipo": panel["by_tipo"],
            "by_classe": panel["by_classe"],
        },
        "municipalities": panel["municipalities"],
        "notices_pt": [
            "Potência instalada (kW/MW) não é energia gerada (MWh).",
            "MMGD não é SIGA (geração centralizada).",
            "Contagem primária = empreendimentos (CodEmpreendimento).",
            "QtdUCRecebeCredito conta UCs beneficiárias de créditos, "
            "não empreendimentos.",
            panel["temporal_note_pt"],
            "Campos pessoais (CPF/CNPJ do titular, nome, CEP, "
            "coordenadas de subestação) foram excluídos deste artefato.",
        ],
    }

    panel_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    quality_path.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {panel_path.relative_to(REPO)}")
    print(f"wrote {quality_path.relative_to(REPO)}")
    print(f"wrote {provenance_path.relative_to(REPO)}")
    print(
        f"valid={panel['n_valid']} rejected={panel['n_rejected']} "
        f"mun_with={panel['municipios_com_registros']} "
        f"mw={panel['potencia_instalada_mw_conhecida']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
