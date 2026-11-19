"""Integração com ZIP MMGD real. Skip se o bruto local não existir."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.connectors.aneel_mmgd import (
    PERSONAL_OR_SENSITIVE_FIELDS,
    iter_mmgd_rows,
    validate_mmgd_zip_file,
)
from geoai.connectors.http_fetch import sha256_file
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.mmgd_aggregate import aggregate_mmgd_by_municipality
from geoai.energy.mmgd_normalize import normalize_mmgd_row
from geoai.portal.paths import (
    mmgd_panel_path,
    mmgd_quality_path,
    municipalities_geojson_path,
)

REPO = Path(__file__).resolve().parents[1]
ZIP = REPO / "data" / "raw" / "aneel" / "empreendimento-geracao-distribuida.zip"
EXPECTED_SHA256 = (
    "b6bf91d1cf6f50657730ed3990d3f3b8628afdf90a55a1b951433679986ef45f"
)


pytestmark = pytest.mark.skipif(
    not ZIP.is_file(),
    reason="ZIP MMGD oficial ausente em data/raw/aneel/",
)


def test_real_zip_header_and_hash() -> None:
    assert ZIP.stat().st_size == 113_212_595
    assert sha256_file(ZIP) == EXPECTED_SHA256
    fields = validate_mmgd_zip_file(ZIP)
    assert "CodMunicipioIbge" in fields
    assert "MdaPotenciaInstaladaKW" in fields


def test_real_pr_sample_has_no_personal_fields_in_public_iter() -> None:
    row = next(iter_mmgd_rows(ZIP, uf="PR", public_only=True))
    for key in PERSONAL_OR_SENSITIVE_FIELDS:
        assert key not in row
    assert row["SigUF"] == "PR"
    assert row["CodMunicipioIbge"].startswith("41")


def test_prepared_panel_if_present_reconciles_399() -> None:
    panel_path = mmgd_panel_path(REPO)
    quality_path = mmgd_quality_path(REPO)
    if not panel_path.is_file() or not quality_path.is_file():
        pytest.skip("painel derivado ainda não gerado")
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality.get("reconcile_ok") is True
    assert len(panel["municipalities"]) == EXPECTED_PR_MUNICIPALITY_COUNT
    assert panel["totals"]["n_empreendimentos"] == quality["n_valid"]
    text = panel_path.read_text(encoding="utf-8")
    assert "NomTitularEmpreendimento" not in text
    assert "NumCPFCNPJ" not in text


def test_stream_aggregate_pr_matches_expected_ballpark() -> None:
    """Sanidade: 399 códigos e contagem > 0. Valores exatos vêm do quality JSON."""

    geojson = json.loads(
        municipalities_geojson_path(REPO).read_text(encoding="utf-8")
    )
    codes = {
        str(f.get("properties", {}).get("CD_MUN", "")).strip()
        for f in geojson["features"]
    }
    codes.discard("")
    assert len(codes) == EXPECTED_PR_MUNICIPALITY_COUNT

    # Amostra limitada: só valida o pipeline em poucos municípios via early break
    # não substitui o prepare completo.
    plants = []
    for i, row in enumerate(iter_mmgd_rows(ZIP, uf="PR", public_only=True)):
        plants.append(normalize_mmgd_row(row))
        if i >= 5000:
            break
    panel = aggregate_mmgd_by_municipality(plants, ibge_codes=codes)
    assert panel["n_valid"] > 0
    assert panel["n_valid"] + panel["n_rejected"] == len(plants)
