"""Testes sem PostGIS: descoberta de migrações e validação dos artefatos MVP 02."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from geoai.db.import_parana import (
    EXPECTED_CRS,
    EXPECTED_FEATURE_COUNT,
    EXPECTED_IBGE_CODE,
    EXPECTED_UF,
    default_artifacts,
    sha256_file,
    validate_preconditions,
)
from geoai.db.migrate import discovery_migrations

REPO = Path(__file__).resolve().parents[1]


def test_discovery_migrations_finds_0001() -> None:
    migs = discovery_migrations(REPO / "db" / "migrations")
    assert migs, "Nenhuma migração encontrada"
    versions = [v for v, _ in migs]
    assert "0001_init_postgis" in versions
    sql = (REPO / "db" / "migrations" / "0001_init_postgis.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql
    assert "territorial_units" in sql
    assert "4674" in sql
    assert "USING GIST" in sql


def test_discovery_rejects_bad_name(tmp_path: Path) -> None:
    bad = tmp_path / "init.sql"
    bad.write_text("-- noop\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inválido"):
        discovery_migrations(tmp_path)


def test_parana_artifacts_validate() -> None:
    arts = default_artifacts(REPO)
    payload = validate_preconditions(arts)
    assert payload["ibge_code"] == EXPECTED_IBGE_CODE
    assert payload["uf_sigla"] == EXPECTED_UF
    assert payload["validation"]["source_crs"] == EXPECTED_CRS
    assert (
        payload["validation"]["validation"]["feature_count"] == EXPECTED_FEATURE_COUNT
    )
    assert len(payload["content_sha256"]) == 64
    assert payload["geometry"]["type"] == "MultiPolygon"


def test_geojson_sha_stable() -> None:
    path = REPO / "data" / "derived" / "parana_uf_2025.geojson"
    a = sha256_file(path)
    b = hashlib.sha256(path.read_bytes()).hexdigest()
    assert a == b


def test_validate_rejects_tampered_validation(tmp_path: Path) -> None:
    arts = default_artifacts(REPO)
    # Copia mínima: geojson + provenance reais, validation adulterada
    geo = tmp_path / "parana_uf_2025.geojson"
    prov = tmp_path / "parana_uf_2025.provenance.json"
    val = tmp_path / "parana_uf_2025.validation.json"
    geo.write_bytes(arts.geojson_path.read_bytes())
    prov.write_bytes(arts.provenance_path.read_bytes())
    val.write_text(
        '{"source_crs":"EPSG:4326","validation":{"feature_count":1,"crs":"EPSG:4326","all_valid":true}}',
        encoding="utf-8",
    )
    from geoai.db.import_parana import ImportArtifacts

    with pytest.raises(ValueError, match="CRS"):
        validate_preconditions(
            ImportArtifacts(geojson_path=geo, provenance_path=prov, validation_path=val)
        )


def test_validate_rejects_derived_sha_mismatch(tmp_path: Path) -> None:
    import json

    from geoai.db.import_parana import ImportArtifacts

    arts = default_artifacts(REPO)
    geo = tmp_path / "parana_uf_2025.geojson"
    prov = tmp_path / "parana_uf_2025.provenance.json"
    val = tmp_path / "parana_uf_2025.validation.json"
    geo.write_bytes(arts.geojson_path.read_bytes())
    val.write_bytes(arts.validation_path.read_bytes())
    provenance = json.loads(arts.provenance_path.read_text(encoding="utf-8"))
    provenance["derived_geojson_sha256"] = "0" * 64
    prov.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        validate_preconditions(
            ImportArtifacts(geojson_path=geo, provenance_path=prov, validation_path=val)
        )


def test_database_url_required_message() -> None:
    from geoai.db.config import require_database_url

    monkey_key = "DATABASE_URL"
    old = os.environ.pop(monkey_key, None)
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            require_database_url()
    finally:
        if old is not None:
            os.environ[monkey_key] = old
