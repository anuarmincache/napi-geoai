"""Testes dos contratos e validadores de qualidade (MVP 06)."""

from __future__ import annotations

import pytest
from geoai.connectors.catalog import get_source
from geoai.quality import (
    EnergyQuantityKind,
    FieldConstraint,
    QualityStatus,
    assert_energy_quantities_separated,
    territorial_pr_uf_schema,
    validate_record,
)


def test_territorial_schema_links_existing_catalog_source() -> None:
    schema = territorial_pr_uf_schema()
    source = get_source(schema.source_id)
    assert source.source_id == "ibge.malhas_municipais.pr_uf_2025"
    assert schema.crs == "EPSG:4674"
    assert schema.content_sha256_required is True


def test_validate_record_valid() -> None:
    schema = territorial_pr_uf_schema()
    report = validate_record(
        schema,
        {
            "ibge_code": "41",
            "name": "Paraná",
            "mesh_edition": "2025",
            "srid": 4674,
        },
        version_label="2025",
        collected_at="2026-11-11T12:00:00+00:00",
        content_sha256="a" * 64,
        limitations=("edição sujeita a atualização IBGE",),
    )
    assert report.status == QualityStatus.VALID
    assert report.findings == ()
    assert report.dataset_id == schema.dataset_id


def test_validate_record_rejects_missing_and_bad_srid() -> None:
    schema = territorial_pr_uf_schema()
    report = validate_record(
        schema,
        {"ibge_code": "41", "name": "Paraná", "srid": 4326},
        version_label="x",
        collected_at="2026-11-11T12:00:00+00:00",
        content_sha256="b" * 64,
    )
    assert report.status == QualityStatus.REJECTED
    codes = {f.code for f in report.findings}
    assert "field.missing" in codes
    assert "field.range_min" in codes or "field.range_max" in codes


def test_validate_record_rejects_incomplete_integrity_meta() -> None:
    schema = territorial_pr_uf_schema()
    report = validate_record(
        schema,
        {
            "ibge_code": "41",
            "name": "Paraná",
            "mesh_edition": "2025",
            "srid": 4674,
        },
        version_label="2025",
        collected_at="not-a-date",
        content_sha256=None,
    )
    assert report.status == QualityStatus.REJECTED
    codes = {f.code for f in report.findings}
    assert "meta.collected_at" in codes
    assert "meta.content_sha256" in codes


def test_energy_quantities_must_not_mix() -> None:
    fields = (
        FieldConstraint(
            name="potencia_kw",
            unit="kW",
            energy_quantity=EnergyQuantityKind.INSTALLED_CAPACITY_KW,
        ),
        FieldConstraint(
            name="geracao_mwh",
            unit="MWh",
            energy_quantity=EnergyQuantityKind.GENERATION_MWH,
        ),
    )
    with pytest.raises(ValueError, match="não misturar"):
        assert_energy_quantities_separated(fields)

    from geoai.quality.contracts import DatasetSchema, GeometryKind

    schema = DatasetSchema(
        dataset_id="bad.energy.mix",
        source_id="aneel.siga.empreendimentos_geracao",
        title="mistura inválida",
        geometry_kind=GeometryKind.TABULAR,
        crs="EPSG:4674",
        spatial_resolution="ponto",
        temporal_periodicity="desconhecida",
        edition="n/a",
        license_note="ODbL",
        update_policy="n/a",
        fields=fields,
    )
    report = validate_record(
        schema,
        {"potencia_kw": 10, "geracao_mwh": 1},
        version_label="t",
        collected_at="2026-11-11T00:00:00+00:00",
        content_sha256="c" * 64,
    )
    assert report.status == QualityStatus.REJECTED
    assert any(f.code == "schema.energy_quantity_mix" for f in report.findings)
