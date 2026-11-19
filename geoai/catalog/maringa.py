"""Entrada piloto de Maringá, ligada ao manifesto e à medição já aprovados.

Os números fora de [-1, 1] vêm da inspeção somente leitura no QGIS em
2026-11-16. Não são um novo processamento do NDVI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.catalog.entry import build_catalog_entry
from geoai.catalog.integrity import integrity_record, write_json

APPROVED_N_AOI = 4_876_416
APPROVED_N_VALID = 3_565_350
APPROVED_PIXELS = (3_086_107, 479_243)
APPROVED_OVERLAP = 2_034_052
APPROVED_FRACTION = 0.7311414776754075
MUNICIPALITY_IBGE = "4115200"
MUNICIPALITY_NAME = "Maringá"
ACQUISITION_ID = "S2B_20261112T133149_R081"
PROCESSED_AT = "2026-11-17T00:18:08.8872919Z"

QUALITY_NOTE_PT = (
    "A fração válida 0,7311414776754075 atingiu o limiar de 0,70. "
    "A inspeção no QGIS, em 16/11/2026, encontrou 686 pixels válidos "
    "fora do intervalo [-1, 1], todos na tile 22KCV. "
    "Os valores armazenados não foram alterados. "
    "O mapa está validado localmente e não foi publicado."
)


def _require_approved_manifest(manifest: dict[str, Any]) -> None:
    counts = manifest["counts"]
    pixels = tuple(counts["pixels_per_tile"])
    if (
        counts["n_aoi"] != APPROVED_N_AOI
        or counts["n_valid"] != APPROVED_N_VALID
        or pixels != APPROVED_PIXELS
        or counts["overlap_both_valid"] != APPROVED_OVERLAP
    ):
        raise RuntimeError("medicao_nao_aprovada")
    if counts["n_valid"] / counts["n_aoi"] != APPROVED_FRACTION:
        raise RuntimeError("fracao_nao_aprovada")
    if manifest["epsg"] != 32722 or manifest["resolution_m"] != 10.0:
        raise RuntimeError("grade_nao_aprovada")


def build_maringa_pilot(manifest: dict[str, Any], product_dir: Path) -> dict[str, Any]:
    """Cataloga Maringá somente se o manifesto e os COGs conferirem."""

    _require_approved_manifest(manifest)
    entry = build_catalog_entry(
        manifest,
        ibge=MUNICIPALITY_IBGE,
        municipality=MUNICIPALITY_NAME,
        acquisition_id=ACQUISITION_ID,
        processed_at=PROCESSED_AT,
        product_dir=product_dir,
        quality_status="approved_with_reservations",
        quality_note_pt=QUALITY_NOTE_PT,
        fraction_gate_passed=True,
        outside_unit_interval={
            "minimum": -1.0,
            "maximum": 1.0,
            "count": 686,
            "below": 173,
            "above": 513,
            "observed_min": -37.0,
            "observed_max": 15.800000190734863,
            "source": "inspecao_qgis_2026-11-16",
            "display": "neutral_not_vegetation",
            "source_values_modified": False,
        },
    )
    downloads = entry["downloads"]
    if not downloads["geotiff"]["available"]:
        raise RuntimeError("geotiff_nao_disponivel")
    if not entry["provenance"]["product"]["available"]:
        raise RuntimeError("proveniencia_nao_disponivel")
    if downloads["png"]["available"] or downloads["csv"]["available"]:
        raise RuntimeError("formato_pendente_marcado_pronto")
    return entry


def write_maringa_catalog(
    manifest_path: Path,
    product_dir: Path,
    public_path: Path,
    integrity_path: Path,
) -> dict[str, Any]:
    """Grava a entrada pública e o registro de integridade, sem caminho local."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = build_maringa_pilot(manifest, product_dir)
    body = write_json(public_path, entry)
    write_json(
        integrity_path,
        integrity_record("catalog/public/4115200.json", body),
    )
    return entry
