"""Leitura e painel MapBiomas. Linhas de teste são sintéticas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.landcover.mapbiomas_col11 import (
    CONTENT_SHA256,
    CoverageRecord,
    MapBiomasContractError,
)
from geoai.landcover.mapbiomas_load import (
    CLASS_TO_GROUP,
    build_landcover_panel,
    choose_panel_years,
    read_parana_records,
)
from geoai.portal.landcover_panel import (
    landcover_change,
    landcover_composition,
    landcover_share,
    load_landcover_bundle,
)
from geoai.portal.paths import (
    landcover_panel_path,
    landcover_provenance_path,
    landcover_quality_path,
)

REPO = Path(__file__).resolve().parents[1]
CODES = {f"41{n:05d}": 100.0 for n in range(1, 400)}  # 100 km² = 10.000 ha


def _records(scale: float = 1.0) -> list[CoverageRecord]:
    out = []
    for code in CODES:
        for year, forest in ((1985, 6000.0), (2025, 4000.0)):
            out.append(CoverageRecord(code, "Mata Atlântica", "PR", 3, year, forest))
            out.append(
                CoverageRecord(
                    code, "Mata Atlântica", "PR", 39, year, (10000 - forest) * scale
                )
            )
    return out


def test_every_leaf_class_has_a_display_group() -> None:
    assert CLASS_TO_GROUP[3] == "formacao_florestal"
    assert CLASS_TO_GROUP[39] == "agricultura"
    assert CLASS_TO_GROUP[24] == "area_urbanizada"


def test_year_rule_keeps_multiples_of_five_and_the_last() -> None:
    assert choose_panel_years(list(range(1985, 2025))) == [
        1985,
        1990,
        1995,
        2000,
        2005,
        2010,
        2015,
        2020,
        2024,
    ]


def test_panel_requires_the_registered_file() -> None:
    with pytest.raises(MapBiomasContractError, match="SHA-256"):
        build_landcover_panel(_records(), CODES, content_sha256="0" * 64)


def test_panel_sums_and_never_rescales() -> None:
    panel, quality = build_landcover_panel(
        _records(), CODES, content_sha256=CONTENT_SHA256
    )
    assert panel["years"] == [1985, 2025] and panel["last_year"] == 2025
    row = panel["municipalities"]["4100001"]
    assert row["groups_ha"]["2025"] == {
        "agricultura": 6000.0,
        "formacao_florestal": 4000.0,
    }
    assert row["relative_delta_vs_ibge"] == 0.0
    assert quality["reconcile_ok"] is True
    assert panel["totals_ha"]["1985"]["formacao_florestal"] == 6000.0 * 399


def test_systematic_area_mismatch_stops_the_load() -> None:
    # Dobro da área mapeada em todos: sinal de dupla contagem por bioma.
    with pytest.raises(MapBiomasContractError, match="Mediana"):
        build_landcover_panel(_records(scale=4.0), CODES, content_sha256=CONTENT_SHA256)


def test_reader_rejects_blank_hectares(tmp_path: Path) -> None:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "COVERAGE_11"
    sheet.append(["biome", "state", "geocode", "class", "y1985", "y2025"])
    sheet.append(["Mata Atlântica", "Paraná", "4100103", "3", 1.0, 2.0])
    sheet.append(["Amazônia", "Pará", "1501782", "3", 9.0, 9.0])
    path = tmp_path / "t.xlsx"
    book.save(path)
    records, facts = read_parana_records(path)
    assert facts["rows_national"] == 2 and facts["rows_parana"] == 1
    assert [(r.year, r.hectares) for r in records] == [(1985, 1.0), (2025, 2.0)]
    sheet.append(["Mata Atlântica", "Paraná", "4100202", "3", None, 2.0])
    book.save(path)
    with pytest.raises(MapBiomasContractError, match="Hectare ausente"):
        read_parana_records(path)


def test_service_fail_closed_and_derived_values(tmp_path: Path) -> None:
    assert load_landcover_bundle(tmp_path).available is False
    panel, quality = build_landcover_panel(
        _records(), CODES, content_sha256=CONTENT_SHA256
    )
    landcover_panel_path(tmp_path).parent.mkdir(parents=True)
    landcover_panel_path(tmp_path).write_text(json.dumps(panel), encoding="utf-8")
    landcover_quality_path(tmp_path).write_text(json.dumps(quality), encoding="utf-8")
    landcover_provenance_path(tmp_path).write_text(
        json.dumps({"content_sha256": "errado"}), encoding="utf-8"
    )
    assert load_landcover_bundle(tmp_path).available is False
    landcover_provenance_path(tmp_path).write_text(
        json.dumps({"content_sha256": CONTENT_SHA256}), encoding="utf-8"
    )
    bundle = load_landcover_bundle(tmp_path)
    assert bundle.available, bundle.missing_reason_pt
    assert landcover_share(bundle, "4100001", "formacao_florestal", 2025) == 40.0
    assert landcover_share(bundle, None, "agricultura", 1985) == 40.0
    comp = {r["key"]: r for r in landcover_composition(bundle, "4100001", 2025)}
    assert comp["pastagem"]["hectares"] == 0.0 and comp["pastagem"]["percent"] == 0.0
    change = {r["label_pt"]: r for r in landcover_change(bundle, None, 1985, 2025)}
    assert change["Floresta"]["delta_ha"] == -2000.0 * 399
    assert change["Floresta"]["delta_pp"] == -20.0


def test_versioned_panel_matches_contract_when_present() -> None:
    bundle = load_landcover_bundle(REPO)
    if not bundle.available:
        pytest.skip("painel MapBiomas ausente")
    assert bundle.panel["municipality_count"] == 399
    assert bundle.provenance["content_sha256"] == CONTENT_SHA256
    for row in bundle.panel["municipalities"].values():
        assert abs(row["relative_delta_vs_ibge"]) < 0.06
