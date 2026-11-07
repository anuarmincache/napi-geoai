#!/usr/bin/env python3
"""Aplica migrações SQL em db/migrations/ usando DATABASE_URL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geoai.db.config import require_database_url  # noqa: E402
from geoai.db.migrate import apply_migrations, discovery_migrations  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-list",
        action="store_true",
        help="Lista migrações descobertas sem conectar ao banco.",
    )
    args = parser.parse_args(argv)

    if args.dry_list:
        for version, path in discovery_migrations():
            print(f"{version}\t{path}")
        return 0

    cfg = require_database_url()
    applied = apply_migrations(cfg)
    if not applied:
        print("Nenhuma migração pendente.")
    else:
        for version in applied:
            print(f"Aplicada: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
