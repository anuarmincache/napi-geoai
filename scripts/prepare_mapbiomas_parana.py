"""Prepara o painel de cobertura e uso da terra do Paraná (MapBiomas Col. 11).

Uso (na raiz do repositório):
  python scripts/prepare_mapbiomas_parana.py

Lê data/raw/mapbiomas/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx
(fora do Git; obtenha com scripts/inspect_mapbiomas_col11.py). Se só o .zip
estiver na pasta, extrai o .xlsx. O SHA-256 precisa ser o do contrato. Se
qualquer etapa falhar, nenhum artefato derivado é sobrescrito.
"""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.landcover import mapbiomas_col11 as contract  # noqa: E402
from geoai.landcover.mapbiomas_load import (  # noqa: E402
    build_landcover_panel,
    read_parana_records,
    sha256_file,
)
from geoai.portal.paths import (  # noqa: E402
    landcover_panel_path,
    landcover_provenance_path,
    landcover_quality_path,
    population_panel_path,
)

RAW_DIR = REPO / "data" / "raw" / "mapbiomas"
XLSX = RAW_DIR / contract.EXPECTED_FILENAME


def _ensure_xlsx() -> None:
    if XLSX.is_file() and zipfile.is_zipfile(XLSX):
        with zipfile.ZipFile(XLSX) as archive:
            names = archive.namelist()
        if "[Content_Types].xml" in names:
            return
        # O link oficial entrega um .zip com o .xlsx dentro, com o mesmo nome.
        XLSX.replace(XLSX.with_suffix(".zip"))
    packed = XLSX.with_suffix(".zip")
    if not XLSX.is_file() and packed.is_file():
        with zipfile.ZipFile(packed) as archive:
            archive.extract(contract.EXPECTED_FILENAME, RAW_DIR)
    if not XLSX.is_file():
        raise SystemExit(
            f"arquivo ausente: {XLSX.relative_to(REPO)}. Rode "
            "scripts/inspect_mapbiomas_col11.py ou baixe em "
            f"{contract.STATISTICS_PAGE}"
        )


def main() -> int:
    _ensure_xlsx()
    digest = sha256_file(XLSX)
    size = XLSX.stat().st_size
    if digest != contract.CONTENT_SHA256:
        raise SystemExit(
            "SHA-256 diferente do contrato. O MapBiomas pode ter publicado "
            f"outra versão.\n  obtido:   {digest}\n  contrato: "
            f"{contract.CONTENT_SHA256}\nNada foi gravado."
        )
    population = json.loads(population_panel_path(REPO).read_text(encoding="utf-8"))
    areas = {
        str(m["CD_MUN"]): float(m["area_km2_ibge_2025"])
        for m in population["municipalities"]
    }
    print("lendo a planilha oficial …", flush=True)
    records, facts = read_parana_records(XLSX)
    panel, quality = build_landcover_panel(records, areas, content_sha256=digest)
    prepared_at = datetime.now(UTC).isoformat()
    quality = {"prepared_at": prepared_at, **facts, **quality}
    provenance = {
        "prepared_at": prepared_at,
        "source_id": "mapbiomas.brazil.lulc",
        "organization": "MapBiomas",
        "product": contract.PRODUCT_LABEL,
        "release": contract.RELEASE_LABEL,
        "statistics_page": contract.STATISTICS_PAGE,
        "official_link": contract.OFFICIAL_LINK,
        "file_name": contract.EXPECTED_FILENAME,
        "content_bytes": size,
        "content_sha256": digest,
        "zip_bytes": contract.ZIP_BYTES,
        "zip_sha256": contract.ZIP_SHA256,
        "sheet": facts["sheet"],
        "filter": "state == 'Paraná'",
        "sensor": contract.SENSOR,
        "resolution_m": contract.RESOLUTION_M,
        "license_note": (
            "MapBiomas: uso público com citação obrigatória (termos de uso "
            "declaram Creative Commons CC-BY)."
        ),
        "citation_pt": (
            "Projeto MapBiomas – Coleção 11 da Série Anual de Mapas de "
            "Cobertura e Uso da Terra do Brasil, acessado em 19/11/2026 "
            f"através do link: {contract.STATISTICS_PAGE}"
        ),
        "ibge_area_reference": "AREA_KM2, malha municipal IBGE 2025",
    }
    outputs = (
        (landcover_panel_path(REPO), panel, None),
        (landcover_quality_path(REPO), quality, 1),
        (landcover_provenance_path(REPO), provenance, 1),
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
    last = str(panel["last_year"])
    total = sum(panel["totals_ha"][last].values())
    print(f"{quality['geocode_count']} municípios · anos {panel['years']}")
    for group in panel["groups"]:
        value = panel["totals_ha"][last].get(group["key"], 0.0)
        print(f"  {group['label_pt']}: {value:,.0f} ha ({100 * value / total:.1f}%)")
    delta = quality["area_delta_vs_ibge"]
    print(
        f"diferença para a área IBGE: mediana {100 * delta['median_abs']:.3f}%, "
        f"máxima {100 * delta['max_abs']:.2f}%"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except contract.MapBiomasContractError as exc:
        print(f"ERRO de contrato (nada foi gravado): {exc}")
        raise SystemExit(2) from exc
