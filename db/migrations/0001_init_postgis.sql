-- NAPI GeoAI — migração inicial PostGIS (MVP 04)
-- Portátil: PostGIS pode estar em schema "public" (imagem Docker) ou
-- "extensions" (instalação limpa / alinhamento Supabase). Não hardcode
-- o tipo geometry com schema fixo — resolve-se no schema real da extensão.
-- timestamptz usa DEFAULT now() (instante absoluto; exibir em UTC na app).

BEGIN;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS geoai;

-- Instala PostGIS apenas se ausente. Preferência: schema extensions (Supabase).
-- Se a imagem já trouxe postgis em public, IF NOT EXISTS não move a extensão.
DO $ext$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
        CREATE EXTENSION postgis WITH SCHEMA extensions;
    END IF;
END
$ext$;

CREATE TABLE IF NOT EXISTS geoai.schema_migrations (
    version       text PRIMARY KEY,
    applied_at    timestamptz NOT NULL DEFAULT now(),
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
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS geoai.ingestion_runs (
    id                     bigserial PRIMARY KEY,
    source_id              text NOT NULL REFERENCES geoai.data_sources (source_id),
    started_at             timestamptz NOT NULL DEFAULT now(),
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
    created_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, version_label, content_sha256)
);

CREATE INDEX IF NOT EXISTS data_artifacts_source_idx
    ON geoai.data_artifacts (source_id);

-- territorial_units: tipo geometry resolvido no schema real do PostGIS.
DO $tu$
DECLARE
    postgis_schema text;
BEGIN
    SELECT n.nspname INTO postgis_schema
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'postgis';

    IF postgis_schema IS NULL THEN
        RAISE EXCEPTION 'extensão postgis não encontrada após CREATE EXTENSION';
    END IF;

    EXECUTE format(
        $sql$
        CREATE TABLE IF NOT EXISTS geoai.territorial_units (
            id                     bigserial PRIMARY KEY,
            ibge_code              text NOT NULL,
            uf_sigla               text NOT NULL CHECK (char_length(uf_sigla) = 2),
            name                   text NOT NULL,
            mesh_edition           text NOT NULL,
            geom                   %I.geometry(MultiPolygon, 4674) NOT NULL,
            artifact_id            bigint REFERENCES geoai.data_artifacts (id),
            attributes             jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at             timestamptz NOT NULL DEFAULT now(),
            updated_at             timestamptz NOT NULL DEFAULT now(),
            UNIQUE (ibge_code, mesh_edition)
        )
        $sql$,
        postgis_schema
    );
END
$tu$;

CREATE INDEX IF NOT EXISTS territorial_units_geom_gix
    ON geoai.territorial_units USING GIST (geom);

CREATE INDEX IF NOT EXISTS territorial_units_uf_idx
    ON geoai.territorial_units (uf_sigla);

INSERT INTO geoai.schema_migrations (version, description)
VALUES (
    '0001_init_postgis',
    'schemas extensions/geoai, PostGIS portátil, data_sources, ingestion_runs, data_artifacts, territorial_units'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
