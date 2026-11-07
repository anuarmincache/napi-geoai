"""Importação idempotente do limite UF Paraná (MVP 02 → PostGIS)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from geoai.db.config import DatabaseConfig

SOURCE_ID = "ibge_bcim_uf_2025"
EXPECTED_IBGE_CODE = "41"
EXPECTED_UF = "PR"
EXPECTED_CRS = "EPSG:4674"
EXPECTED_FEATURE_COUNT = 1


@dataclass(frozen=True)
class ImportArtifacts:
    geojson_path: Path
    provenance_path: Path
    validation_path: Path


@dataclass(frozen=True)
class ImportResult:
    run_id: int
    artifact_id: int
    territorial_unit_id: int
    content_sha256: str
    status: str
    already_present: bool


def default_artifacts(repo_root: Path | None = None) -> ImportArtifacts:
    root = repo_root or Path(__file__).resolve().parents[2]
    derived = root / "data" / "derived"
    return ImportArtifacts(
        geojson_path=derived / "parana_uf_2025.geojson",
        provenance_path=derived / "parana_uf_2025.provenance.json",
        validation_path=derived / "parana_uf_2025.validation.json",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON raiz deve ser objeto: {path}")
    return data


def validate_preconditions(artifacts: ImportArtifacts) -> dict[str, Any]:
    """
    Valida artefatos MVP 02 antes de tocar no banco.

    Retorna o GeoJSON já carregado (FeatureCollection).
    """
    for path in (
        artifacts.geojson_path,
        artifacts.provenance_path,
        artifacts.validation_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(f"Artefato ausente: {path}")

    validation_doc = load_json(artifacts.validation_path)
    # MVP 02: métricas podem estar aninhadas em "validation" ou no topo.
    metrics = validation_doc.get("validation")
    if not isinstance(metrics, dict):
        metrics = validation_doc
    crs = metrics.get("crs") or validation_doc.get("source_crs")
    if crs != EXPECTED_CRS:
        raise ValueError(
            f"CRS inesperado em validation.json: {crs!r} (esperado {EXPECTED_CRS})"
        )
    if metrics.get("feature_count") != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"feature_count inesperado: {metrics.get('feature_count')!r}"
        )
    geom_ok = metrics.get("all_valid") is True or metrics.get("geometry_valid") is True
    if not geom_ok:
        raise ValueError("geometria deve constar como válida no validation.json")

    provenance = load_json(artifacts.provenance_path)
    # Provenance do ZIP IBGE; o SHA do GeoJSON derivado é recalculado e
    # confrontado com um sidecar opcional ou com o próprio arquivo.
    actual_sha = sha256_file(artifacts.geojson_path)
    declared_geojson_sha = provenance.get("derived_geojson_sha256")
    if isinstance(declared_geojson_sha, str) and len(declared_geojson_sha) == 64:
        if declared_geojson_sha.lower() != actual_sha.lower():
            raise ValueError(
                "SHA-256 do GeoJSON diverge do provenance.derived_geojson_sha256: "
                f"arquivo={actual_sha} provenance={declared_geojson_sha}"
            )
    zip_sha = provenance.get("content_sha256")
    if zip_sha is not None and (
        not isinstance(zip_sha, str) or len(zip_sha) != 64
    ):
        raise ValueError("provenance.content_sha256 (ZIP) inválido")

    geojson = load_json(artifacts.geojson_path)
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON deve ser FeatureCollection")
    features = geojson.get("features")
    if not isinstance(features, list) or len(features) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"Esperado {EXPECTED_FEATURE_COUNT} feature(s); "
            f"obtido {0 if not isinstance(features, list) else len(features)}"
        )

    feature = features[0]
    props = feature.get("properties") or {}
    geom = feature.get("geometry")
    if not isinstance(geom, dict) or geom.get("type") not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise ValueError("Geometria deve ser Polygon ou MultiPolygon")

    code = str(props.get("CD_UF") or props.get("codigo") or EXPECTED_IBGE_CODE)
    if code != EXPECTED_IBGE_CODE:
        raise ValueError(f"CD_UF inesperado: {code!r}")
    sigla = str(props.get("SIGLA_UF") or props.get("sigla") or EXPECTED_UF).upper()
    if sigla != EXPECTED_UF:
        raise ValueError(f"SIGLA_UF inesperada: {sigla!r}")

    return {
        "geojson": geojson,
        "feature": feature,
        "properties": props,
        "geometry": geom,
        "provenance": provenance,
        "validation": validation_doc,
        "content_sha256": actual_sha,
        "content_bytes": artifacts.geojson_path.stat().st_size,
        "ibge_code": code,
        "uf_sigla": sigla,
        "name": str(props.get("NM_UF") or props.get("nome") or "Paraná"),
        "mesh_edition": str(
            provenance.get("edition")
            or provenance.get("mesh_edition")
            or validation_doc.get("mesh_edition")
            or "municipio_2025"
        ),
        "download_url": provenance.get("url") or provenance.get("download_url"),
        "entry_url": provenance.get("entry_url") or provenance.get("url"),
    }


def _utcnow() -> datetime:
    return datetime.now(UTC)


def import_parana_boundary(
    cfg: DatabaseConfig,
    *,
    artifacts: ImportArtifacts | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """
    Upsert idempotente: mesma (ibge_code, mesh_edition) + mesmo SHA não duplica.

    Em reexecução com mesmo SHA: status succeeded, already_present=True.
    Em reexecução com SHA diferente: atualiza geom/artifact e registra novo run.
    """
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Pacote psycopg não instalado. Execute: pip install -e '.[db]'"
        ) from exc

    arts = artifacts or default_artifacts()
    payload = validate_preconditions(arts)
    if dry_run:
        return ImportResult(
            run_id=0,
            artifact_id=0,
            territorial_unit_id=0,
            content_sha256=payload["content_sha256"],
            status="dry_run",
            already_present=False,
        )

    geom_json = json.dumps(payload["geometry"], ensure_ascii=False)
    storage_ref = str(arts.geojson_path.as_posix())
    version_label = payload["mesh_edition"]
    now = _utcnow()

    with psycopg.connect(cfg.database_url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO geoai.data_sources (
                        source_id, organization, product, license_note,
                        entry_url, download_url, verification_policy,
                        edition, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, 'active'
                    )
                    ON CONFLICT (source_id) DO UPDATE SET
                        updated_at = EXCLUDED.updated_at,
                        edition = COALESCE(EXCLUDED.edition, geoai.data_sources.edition)
                    """,
                    (
                        SOURCE_ID,
                        "IBGE",
                        "Malha territorial / BCIM UF",
                        "Uso conforme termos IBGE; cite a fonte.",
                        payload.get("entry_url"),
                        payload.get("download_url"),
                        "sha256_geojson+validation_mvp02",
                        version_label,
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO geoai.ingestion_runs (
                        source_id, started_at, status, records_processed
                    ) VALUES (%s, %s, 'running', 0)
                    RETURNING id
                    """,
                    (SOURCE_ID, now),
                )
                run_id = int(cur.fetchone()[0])

                cur.execute(
                    """
                    SELECT id, content_sha256
                    FROM geoai.data_artifacts
                    WHERE source_id = %s AND version_label = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (SOURCE_ID, version_label),
                )
                existing_art = cur.fetchone()
                already = bool(
                    existing_art and existing_art[1] == payload["content_sha256"]
                )

                if already:
                    artifact_id = int(existing_art[0])
                else:
                    cur.execute(
                        """
                        INSERT INTO geoai.data_artifacts (
                            source_id, version_label, content_sha256, content_bytes,
                            format, retrieved_at, last_checked_at, storage_ref,
                            crs, metadata
                        ) VALUES (
                            %s, %s, %s, %s, 'geojson', %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (source_id, version_label, content_sha256)
                        DO UPDATE SET last_checked_at = EXCLUDED.last_checked_at
                        RETURNING id
                        """,
                        (
                            SOURCE_ID,
                            version_label,
                            payload["content_sha256"],
                            payload["content_bytes"],
                            now,
                            now,
                            storage_ref,
                            EXPECTED_CRS,
                            Jsonb(
                                {
                                    "provenance": payload["provenance"],
                                    "validation": payload["validation"],
                                }
                            ),
                        ),
                    )
                    artifact_id = int(cur.fetchone()[0])

                # MultiPolygon via ST_Multi + ST_SetSRID(ST_GeomFromGeoJSON)
                cur.execute(
                    """
                    INSERT INTO geoai.territorial_units (
                        ibge_code, uf_sigla, name, mesh_edition, geom,
                        artifact_id, attributes, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        extensions.ST_Multi(
                            extensions.ST_SetSRID(
                                extensions.ST_GeomFromGeoJSON(%s),
                                4674
                            )
                        ),
                        %s, %s, %s
                    )
                    ON CONFLICT (ibge_code, mesh_edition) DO UPDATE SET
                        name = EXCLUDED.name,
                        geom = EXCLUDED.geom,
                        artifact_id = EXCLUDED.artifact_id,
                        attributes = EXCLUDED.attributes,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """,
                    (
                        payload["ibge_code"],
                        payload["uf_sigla"],
                        payload["name"],
                        payload["mesh_edition"],
                        geom_json,
                        artifact_id,
                        Jsonb(payload["properties"]),
                        now,
                    ),
                )
                unit_id = int(cur.fetchone()[0])

                # Integridade espacial pós-carga
                cur.execute(
                    """
                    SELECT
                        extensions.ST_IsValid(geom),
                        extensions.ST_SRID(geom),
                        extensions.GeometryType(geom),
                        extensions.ST_NumGeometries(geom)
                    FROM geoai.territorial_units
                    WHERE id = %s
                    """,
                    (unit_id,),
                )
                valid, srid, gtype, ngeoms = cur.fetchone()
                if not valid:
                    raise RuntimeError("Geometria inválida após carga PostGIS")
                if int(srid) != 4674:
                    raise RuntimeError(f"SRID inesperado após carga: {srid}")
                if str(gtype).upper() != "MULTIPOLYGON":
                    raise RuntimeError(f"Tipo geométrico inesperado: {gtype}")
                if int(ngeoms) < 1:
                    raise RuntimeError("MultiPolygon vazio após carga")

                finished = _utcnow()
                cur.execute(
                    """
                    UPDATE geoai.ingestion_runs
                    SET finished_at = %s,
                        status = 'succeeded',
                        records_processed = 1
                    WHERE id = %s
                    """,
                    (finished, run_id),
                )

        return ImportResult(
            run_id=run_id,
            artifact_id=artifact_id,
            territorial_unit_id=unit_id,
            content_sha256=payload["content_sha256"],
            status="succeeded",
            already_present=already,
        )
