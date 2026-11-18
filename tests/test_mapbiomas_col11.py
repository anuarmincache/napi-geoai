"""Contrato MapBiomas Coleção 11. As linhas são sintéticas e não descrevem o Paraná."""

from __future__ import annotations

import pytest
from geoai.landcover.mapbiomas_col11 import (
    CONTENT_SHA256,
    LOCAL_FILE,
    YEAR_MAX,
    CoverageRecord,
    MapBiomasContractError,
    area_difference_km2,
    composition_percent,
    validate_fixture_records,
    validate_parana_records,
)


def _row(
    code: str,
    biome: str,
    class_id: int,
    hectares: float,
    year: int = 2025,
) -> CoverageRecord:
    return CoverageRecord(code, biome, "PR", class_id, year, hectares)


def test_production_path_stays_closed_without_the_file():
    assert LOCAL_FILE is False
    assert CONTENT_SHA256 is None
    with pytest.raises(MapBiomasContractError, match="Arquivo oficial ausente"):
        validate_parana_records((), {"4100103"})


def test_biome_slices_are_kept_and_the_ibge_set_must_match():
    codes = {"4100103", "4100202"}
    records = [
        _row("4100103", "Mata Atlântica", 3, 100.0),
        _row("4100103", "Cerrado", 3, 40.0),
        _row("4100103", "Mata Atlântica", 15, 10.0),
        _row("4100202", "Mata Atlântica", 24, 5.0),
    ]
    summary = validate_fixture_records(records, codes)
    assert summary["geocode_count"] == 2
    assert summary["biomes"] == ("Cerrado", "Mata Atlântica")
    assert summary["years"] == (YEAR_MAX,)
    percent = composition_percent(records[:3])
    assert percent is not None
    assert percent[3] == pytest.approx(140 / 150 * 100)
    assert percent[15] == pytest.approx(10 / 150 * 100)


def test_parent_and_child_cannot_be_summed():
    records = [
        _row("4100103", "Mata Atlântica", 14, 80.0),
        _row("4100103", "Mata Atlântica", 15, 80.0),
    ]
    with pytest.raises(MapBiomasContractError, match="Pai e filho"):
        validate_fixture_records(records, {"4100103"})
    with pytest.raises(MapBiomasContractError, match="Percentual recusado"):
        composition_percent(records)


def test_missing_municipality_is_not_filled():
    with pytest.raises(MapBiomasContractError, match="Códigos divergentes"):
        validate_fixture_records(
            [_row("4100103", "Mata Atlântica", 3, 1.0)],
            {"4100103", "4100202"},
        )


def test_ibge_difference_is_reported_without_rescaling():
    diff = area_difference_km2(mapped_hectares=10_000.0, ibge_area_km2=102.0)
    assert diff["mapped_km2"] == 100.0
    assert diff["delta_km2"] == pytest.approx(-2.0)
    assert diff["ibge_area_km2"] == 102.0
