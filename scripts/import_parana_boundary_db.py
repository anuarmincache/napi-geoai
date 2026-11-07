#!/usr/bin/env python3
"""Importa o limite UF Paraná (MVP 02) para PostGIS de forma idempotente."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geoai.db.config import require_database_url  # noqa: E402
from geoai.db.import_parana import (  # noqa: E402
    ImportArtifacts,
    default_artifacts,
    import_parana_boundary,
    validate_preconditions,
)
from geoai.db.migrate import apply_migrations  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Não aplica migrações antes da importação.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida artefatos sem gravar no banco (não exige DATABASE_URL).",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=None,
        help="Override do caminho do GeoJSON derivado.",
    )
    args = parser.parse_args(argv)

    arts = default_artifacts(ROOT)
    if args.geojson is not None:
        derived = args.geojson.parent
        arts = ImportArtifacts(
            geojson_path=args.geojson,
            provenance_path=derived / "parana_uf_2025.provenance.json",
            validation_path=derived / "parana_uf_2025.validation.json",
        )

    if args.dry_run:
        payload = validate_preconditions(arts)
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "content_sha256": payload["content_sha256"],
                    "ibge_code": payload["ibge_code"],
                    "uf_sigla": payload["uf_sigla"],
                    "mesh_edition": payload["mesh_edition"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    cfg = require_database_url()
    if not args.skip_migrate:
        apply_migrations(cfg)

    result = import_parana_boundary(cfg, artifacts=arts)
    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": result.run_id,
                "artifact_id": result.artifact_id,
                "territorial_unit_id": result.territorial_unit_id,
                "content_sha256": result.content_sha256,
                "already_present": result.already_present,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
