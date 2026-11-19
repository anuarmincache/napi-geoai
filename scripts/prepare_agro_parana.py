"""Prepara o painel agropecuário do Paraná (IBGE PAM e PPM via SIDRA).

Uso (na raiz do repositório):
  python scripts/prepare_agro_parana.py

As respostas brutas da API ficam em data/raw/ibge/sidra/ (gitignored).
Os artefatos leves vão para data/derived/. Se qualquer etapa falhar,
nenhum artefato derivado existente é sobrescrito.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.agriculture import (  # noqa: E402
    PAM_VARIABLES,
    PPM_INDICATORS,
    build_agro_panel,
)
from geoai.connectors.http_fetch import download_http_file  # noqa: E402
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT  # noqa: E402
from geoai.connectors.sidra import (  # noqa: E402
    PAM_TABLE,
    PPM_ANIMAL_PRODUCT_TABLE,
    PPM_HERD_TABLE,
    SIDRA_LICENSE_NOTE,
    SIDRA_PAM_SOURCE_ID,
    SIDRA_PPM_HERD_SOURCE_ID,
    SIDRA_PPM_PRODUCT_SOURCE_ID,
    SidraError,
    metadata_url,
    parse_sidra_values,
    resolve_category,
    resolve_classification,
    resolve_variable,
    values_url,
)
from geoai.portal.paths import (  # noqa: E402
    agro_panel_path,
    agro_provenance_path,
    agro_quality_path,
    municipalities_geojson_path,
    municipalities_validation_path,
)

RAW_DIR = REPO / "data" / "raw" / "ibge" / "sidra"


def _load_ibge_codes(repo: Path) -> set[str]:
    validation = json.loads(
        municipalities_validation_path(repo).read_text(encoding="utf-8")
    )
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
        raise SystemExit(f"malha municipal: {len(codes)} códigos != 399")
    return codes


def _json_ok(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8"))


def _fetch(
    url: str, name: str, source_id: str, downloads: list[dict[str, Any]]
) -> Any:
    destination = RAW_DIR / name
    print(f"baixando {name} …", flush=True)
    record = download_http_file(
        url,
        destination,
        source_id=source_id,
        license_note=SIDRA_LICENSE_NOTE,
        timeout_s=300.0,
        retries=4,
        retry_backoff_s=2.0,
        content_validator=_json_ok,
    )
    info = record.to_dict()
    info["local_path"] = str(destination.relative_to(REPO)).replace("\\", "/")
    downloads.append(info)
    return json.loads(destination.read_text(encoding="utf-8"))


def main() -> int:
    codes = _load_ibge_codes(REPO)
    downloads: list[dict[str, Any]] = []
    resolved: dict[str, Any] = {}

    # ------------------------------------------------------------ PAM
    meta = _fetch(
        metadata_url(PAM_TABLE),
        f"metadados_{PAM_TABLE}.json",
        SIDRA_PAM_SOURCE_ID,
        downloads,
    )
    pam_class = resolve_classification(meta, "Produto das lavouras")
    pam_records = {}
    resolved["pam"] = {
        "table": PAM_TABLE,
        "table_name": meta.get("nome"),
        "classification": {"id": pam_class["id"], "name": pam_class["nome"]},
        "variables": {},
    }
    for key, (name, prefix) in PAM_VARIABLES.items():
        var = resolve_variable(meta, name, prefix=prefix)
        resolved["pam"]["variables"][key] = {"id": var.item_id, "name": var.name}
        payload = _fetch(
            values_url(
                PAM_TABLE, var.item_id, classification_id=int(pam_class["id"])
            ),
            f"pam_{PAM_TABLE}_{key}.json",
            SIDRA_PAM_SOURCE_ID,
            downloads,
        )
        pam_records[key] = parse_sidra_values(
            payload, classification_name=str(pam_class["nome"])
        )

    # ------------------------------------------------------------ PPM
    ppm_sets: dict[str, list] = {}
    resolved["ppm"] = {}
    plan = {
        "rebanho": (
            PPM_HERD_TABLE,
            SIDRA_PPM_HERD_SOURCE_ID,
            "Efetivo dos rebanhos",
            "Tipo de rebanho",
        ),
        "produto": (
            PPM_ANIMAL_PRODUCT_TABLE,
            SIDRA_PPM_PRODUCT_SOURCE_ID,
            "Produção de origem animal",
            "Tipo de produto de origem animal",
        ),
    }
    for label, (table, source_id, var_name, class_prefix) in plan.items():
        meta = _fetch(
            metadata_url(table), f"metadados_{table}.json", source_id, downloads
        )
        var = resolve_variable(meta, var_name)
        cls = resolve_classification(meta, class_prefix)
        cats = [
            resolve_category(cls, cat_name)
            for _key, (group, cat_name) in PPM_INDICATORS.items()
            if group == label
        ]
        resolved["ppm"][label] = {
            "table": table,
            "table_name": meta.get("nome"),
            "variable": {"id": var.item_id, "name": var.name},
            "classification": {"id": cls["id"], "name": cls["nome"]},
            "categories": [{"id": c.item_id, "name": c.name} for c in cats],
        }
        payload = _fetch(
            values_url(
                table,
                var.item_id,
                classification_id=int(cls["id"]),
                category_ids=tuple(c.item_id for c in cats),
            ),
            f"ppm_{table}_{label}.json",
            source_id,
            downloads,
        )
        ppm_sets[label] = parse_sidra_values(
            payload, classification_name=str(cls["nome"])
        )

    panel = build_agro_panel(
        municipality_codes=codes,
        pam_records=pam_records,
        herd_records=ppm_sets["rebanho"],
        product_records=ppm_sets["produto"],
    )

    prepared_at = datetime.now(UTC).isoformat()
    n_pam = {k: len(v) for k, v in pam_records.items()}
    quality = {
        "prepared_at": prepared_at,
        "ibge_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "municipality_count": panel["municipality_count"],
        "rows_pam": n_pam,
        "rows_ppm": {k: len(v) for k, v in ppm_sets.items()},
        "pam_year": panel["pam"]["year"],
        "ppm_year_rebanho": panel["ppm"]["year_rebanho"],
        "ppm_year_produto": panel["ppm"]["year_produto"],
        "crops_in_panel": len(panel["pam"]["crops"]),
        "crops_available_in_source": panel["pam"]["crops_available_in_source"],
        "totals": panel["totals"],
        "reconcile_ok": panel["municipality_count"]
        == EXPECTED_PR_MUNICIPALITY_COUNT
        and len(panel["pam"]["crops"]) > 0,
    }
    if not quality["reconcile_ok"]:
        raise SystemExit("painel não reconciliado — nada foi gravado")
    provenance = {
        "prepared_at": prepared_at,
        "organization": "IBGE",
        "api": "SIDRA",
        "license_note": SIDRA_LICENSE_NOTE,
        "territory": "municípios do Paraná (n6 em n3 41)",
        "period_requested": "último ano publicado (last 1)",
        "resolved_identifiers": resolved,
        "downloads": downloads,
        "municipios_validation": str(
            municipalities_validation_path(REPO).relative_to(REPO)
        ).replace("\\", "/"),
    }

    outputs = (
        (agro_panel_path(REPO), panel, None),
        (agro_quality_path(REPO), quality, 2),
        (agro_provenance_path(REPO), provenance, 2),
    )
    staged = []
    for path, data, indent in outputs:
        tmp = path.with_suffix(path.suffix + ".partial")
        tmp.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=indent,
                separators=(",", ":") if indent is None else None,
            )
            + "\n",
            encoding="utf-8",
        )
        staged.append((tmp, path))
    for tmp, path in staged:
        tmp.replace(path)
        print(f"gravado {path.relative_to(REPO)}")

    print(
        f"PAM {panel['pam']['year']}: {len(panel['pam']['crops'])} culturas · "
        f"PPM rebanho {panel['ppm']['year_rebanho']} · "
        f"PPM produto {panel['ppm']['year_produto']}"
    )
    for crop in panel["pam"]["crops"]:
        print(
            f"  {crop['name']}: "
            f"{crop['area_plantada_soma_publicada']:,.0f} "
            f"{panel['pam']['variables']['area_plantada']['unit']}"
        )
    for key, total in panel["totals"]["ppm"].items():
        ind = panel["ppm"]["indicators"][key]
        print(f"  {ind['category_name']}: {total['soma_publicada']:,.0f} {ind['unit']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SidraError as exc:
        print(f"ERRO SIDRA (nada foi gravado em data/derived): {exc}")
        raise SystemExit(2) from exc
