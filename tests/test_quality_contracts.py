"""Testes dos contratos e validadores de qualidade (MVP 06)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.connectors.catalog import get_source
from geoai.quality import (
    DatasetSchema,
    EnergyQuantityKind,
    FieldConstraint,
    GeometryKind,
    QualityStatus,
    assert_energy_quantities_separated,
    is_sha256_hex,
    territorial_pr_uf_schema,
    validate_field_value,
    validate_record,
    validate_tabular_record,
    verify_content_sha256,
)

REPO = Path(__file__).resolve().parents[1]
PROVENANCE = REPO / "data" / "derived" / "parana_uf_2025.provenance.json"
VALIDATION = REPO / "data" / "derived" / "parana_uf_2025.validation.json"
GEOJSON = REPO / "data" / "derived" / "parana_uf_2025.geojson"


def test_territorial_schema_links_existing_catalog_source() -> None:
    schema = territorial_pr_uf_schema()
    source = get_source(schema.source_id)
    assert source.source_id == "ibge.malhas_municipais.pr_uf_2025"
    assert schema.crs == "EPSG:4674"
    assert schema.content_sha256_required is True


def test_validate_tabular_record_valid() -> None:
    schema = territorial_pr_uf_schema()
    report = validate_tabular_record(
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
    assert report.extra.get("scope") == "tabular_record_only"
    assert report.extra.get("validates_postgis_geometry") is False


def test_validate_record_alias() -> None:
    schema = territorial_pr_uf_schema()
    report = validate_record(
        schema,
        {
            "ibge_code": "41",
            "name": "Paraná",
            "mesh_edition": "2025",
            "srid": "4674",
        },
        version_label="2025",
        collected_at="2026-11-11T12:00:00+00:00",
        content_sha256="b" * 64,
    )
    assert report.status == QualityStatus.VALID


def test_validate_record_rejects_missing_and_bad_srid() -> None:
    schema = territorial_pr_uf_schema()
    report = validate_tabular_record(
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


def test_numeric_rejects_non_finite_bool_and_accepts_string() -> None:
    constraint = FieldConstraint(
        name="srid",
        min_value=4674,
        max_value=4674,
    )
    assert any(
        f.code == "field.non_finite"
        for f in validate_field_value(constraint, float("nan"))
    )
    assert any(
        f.code == "field.non_finite"
        for f in validate_field_value(constraint, float("inf"))
    )
    assert any(
        f.code == "field.numeric_bool"
        for f in validate_field_value(constraint, True)
    )
    assert validate_field_value(constraint, "4674") == []
    assert any(
        f.code == "field.numeric" for f in validate_field_value(constraint, "x")
    )


def test_range_boundaries_inclusive() -> None:
    constraint = FieldConstraint(name="x", min_value=0.0, max_value=10.0)
    assert validate_field_value(constraint, 0.0) == []
    assert validate_field_value(constraint, 10.0) == []
    low = validate_field_value(constraint, -0.1)
    high = validate_field_value(constraint, 10.1)
    assert any(f.code == "field.range_min" for f in low)
    assert any(f.code == "field.range_max" for f in high)


def test_sha256_format_and_byte_verification() -> None:
    assert is_sha256_hex("a" * 64)
    assert not is_sha256_hex("a" * 63)
    assert not is_sha256_hex("g" * 64)
    payload = b"napi-geoai"
    digest = __import__("hashlib").sha256(payload).hexdigest()
    assert verify_content_sha256(digest, payload)
    assert not verify_content_sha256("0" * 64, payload)

    schema = territorial_pr_uf_schema()
    record = {
        "ibge_code": "41",
        "name": "Paraná",
        "mesh_edition": "2025",
        "srid": 4674,
    }
    bad_fmt = validate_tabular_record(
        schema,
        record,
        version_label="2025",
        collected_at="2026-11-11T12:00:00+00:00",
        content_sha256="not-a-hash",
    )
    assert bad_fmt.status == QualityStatus.REJECTED
    assert any(f.code == "meta.content_sha256_format" for f in bad_fmt.findings)

    mismatch = validate_tabular_record(
        schema,
        record,
        version_label="2025",
        collected_at="2026-11-11T12:00:00+00:00",
        content_sha256=digest,
        content_bytes=b"other",
    )
    assert mismatch.status == QualityStatus.REJECTED
    assert any(f.code == "meta.content_sha256_mismatch" for f in mismatch.findings)
    assert mismatch.extra.get("content_sha256_verified") is False

    ok = validate_tabular_record(
        schema,
        record,
        version_label="2025",
        collected_at="2026-11-11T12:00:00+00:00",
        content_sha256=digest,
        content_bytes=payload,
    )
    assert ok.status == QualityStatus.VALID
    assert ok.extra.get("content_sha256_verified") is True


def test_energy_columns_may_coexist_with_canonical_units() -> None:
    fields = (
        FieldConstraint(
            name="potencia_kw",
            unit="kW",
            energy_quantity=EnergyQuantityKind.INSTALLED_CAPACITY_KW,
            min_value=0.0,
        ),
        FieldConstraint(
            name="geracao_mwh",
            unit="MWh",
            energy_quantity=EnergyQuantityKind.GENERATION_MWH,
            min_value=0.0,
        ),
        FieldConstraint(
            name="irradiacao",
            unit="kWh/m²",
            energy_quantity=EnergyQuantityKind.IRRADIANCE_KWH_M2,
            min_value=0.0,
        ),
    )
    assert_energy_quantities_separated(fields)
    schema = DatasetSchema(
        dataset_id="energy.multi_column.ok",
        source_id="aneel.siga.empreendimentos_geracao",
        title="colunas tipadas independentemente",
        geometry_kind=GeometryKind.TABULAR,
        crs="EPSG:4674",
        spatial_resolution="ponto",
        temporal_periodicity="desconhecida",
        edition="n/a",
        license_note="ODbL",
        update_policy="n/a",
        fields=fields,
        content_sha256_required=False,
    )
    report = validate_tabular_record(
        schema,
        {"potencia_kw": 10, "geracao_mwh": 1.5, "irradiacao": 5.0},
        version_label="t",
        collected_at="2026-11-11T00:00:00+00:00",
    )
    assert report.status == QualityStatus.VALID


def test_energy_unit_mismatch_on_same_field() -> None:
    bad = FieldConstraint(
        name="geracao",
        unit="kW",
        energy_quantity=EnergyQuantityKind.GENERATION_MWH,
    )
    with pytest.raises(ValueError, match="incompatível"):
        assert_energy_quantities_separated((bad,))
    findings = validate_field_value(bad, 1.0)
    assert any(f.code == "field.energy_unit_mismatch" for f in findings)


@pytest.mark.skipif(not PROVENANCE.is_file(), reason="artefato PR ausente")
def test_smoke_territorial_pr_artifacts_metadata() -> None:
    """Smoke: proveniência/validação reais do Paraná (sem tocar no banco)."""

    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    val = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert prov["expected_crs"] == "EPSG:4674"
    assert val["source_crs"] == "EPSG:4674"
    assert val["validation"]["all_valid"] is True
    assert is_sha256_hex(prov["content_sha256"])
    assert is_sha256_hex(prov["derived_geojson_sha256"])
    if GEOJSON.is_file():
        digest = prov["derived_geojson_sha256"]
        assert verify_content_sha256(digest, GEOJSON.read_bytes())

    schema = territorial_pr_uf_schema()
    report = validate_tabular_record(
        schema,
        {
            "ibge_code": "41",
            "name": "Paraná",
            "mesh_edition": prov.get("edition", "municipio_2025"),
            "srid": 4674,
        },
        version_label=str(prov.get("edition", "municipio_2025")),
        collected_at=str(prov["retrieved_at"]),
        content_sha256=prov["content_sha256"],
        limitations=("validate_tabular_record não inspeciona geometria PostGIS",),
    )
    assert report.status == QualityStatus.VALID
    assert report.extra["validates_postgis_geometry"] is False
