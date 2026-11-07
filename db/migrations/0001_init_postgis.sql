-- NAPI GeoAI — migração inicial PostGIS (MVP 04)
-- Compatível com PostgreSQL local e Supabase (extensões em schema extensions).
-- Idempotente na criação de schemas/extensão; tabelas com IF NOT EXISTS + constraints.

BEGIN;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS geoai;

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;

-- Registrar migrações aplicadas
CREATE TABLE IF NOT EXISTS geoai.schema_migrations (
    version       text PRIMARY KEY,
    applied_at    timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    description   text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS geoai.data_sources (
    source_id              text PRIMARY KEY,
    organization           text NOT NULL,
    product                text NOT NULL,
    license_note           text NOT NULL,
    entry_url              text,
    download_url           text,
    verification_policy    text,
    edition                text,
    status                 text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'deprecated', 'catalogued', 'prototype')),
    created_at             timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at             timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS geoai.ingestion_runs (
    id                     bigserial PRIMARY KEY,
    source_id              text NOT NULL REFERENCES geoai.data_sources (source_id),
    started_at             timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    finished_at            timestamptz,
    status                 text NOT NULL
        CHECK (status IN ('running', 'succeeded', 'failed', 'rolled_back')),
    records_processed      integer NOT NULL DEFAULT 0 CHECK (records_processed >= 0),
    error_summary          text,
    CONSTRAINT ingestion_runs_finished_ck CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status <> 'running' AND finished_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ingestion_runs_source_idx
    ON geoai.ingestion_runs (source_id, started_at DESC);

CREATE TABLE IF NOT EXISTS geoai.data_artifacts (
    id                     bigserial PRIMARY KEY,
    source_id              text NOT NULL REFERENCES geoai.data_sources (source_id),
    version_label          text NOT NULL,
    content_sha256         text NOT NULL CHECK (char_length(content_sha256) = 64),
    content_bytes          bigint NOT NULL CHECK (content_bytes >= 0),
    format                 text NOT NULL,
    retrieved_at           timestamptz,
    last_checked_at        timestamptz,
    storage_ref            text NOT NULL,
    crs                    text,
    metadata               jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at             timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    UNIQUE (source_id, version_label, content_sha256)
);

CREATE INDEX IF NOT EXISTS data_artifacts_source_idx
    ON geoai.data_artifacts (source_id);

CREATE TABLE IF NOT EXISTS geoai.territorial_units (
    id                     bigserial PRIMARY KEY,
    ibge_code              text NOT NULL,
    uf_sigla               text NOT NULL CHECK (char_length(uf_sigla) = 2),
    name                   text NOT NULL,
    mesh_edition           text NOT NULL,
    geom                   extensions.geometry(MultiPolygon, 4674) NOT NULL,
    artifact_id            bigint REFERENCES geoai.data_artifacts (id),
    attributes             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at             timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at             timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    UNIQUE (ibge_code, mesh_edition)
);

CREATE INDEX IF NOT EXISTS territorial_units_geom_gix
    ON geoai.territorial_units USING GIST (geom);

CREATE INDEX IF NOT EXISTS territorial_units_uf_idx
    ON geoai.territorial_units (uf_sigla);

INSERT INTO geoai.schema_migrations (version, description)
VALUES (
    '0001_init_postgis',
    'schemas extensions/geoai, PostGIS, data_sources, ingestion_runs, data_artifacts, territorial_units'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
