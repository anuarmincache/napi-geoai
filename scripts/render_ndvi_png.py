"""Gera os PNG de um COG NDVI já validado. Não baixa nem publica."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geoai.preview.ndvi_png import render_cog_previews  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cog", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ibge", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--acquisition", required=True)
    parser.add_argument("--image-date", required=True)
    parser.add_argument("--image-date-label", required=True)
    parser.add_argument("--satellite", required=True)
    args = parser.parse_args()
    manifest = render_cog_previews(
        args.cog,
        args.output,
        expected_sha256=args.sha256,
        identity={
            "ibge": args.ibge,
            "name": args.name,
            "acquisition_id": args.acquisition,
            "image_date": args.image_date,
            "image_date_label": args.image_date_label,
            "satellite": args.satellite,
        },
    )
    print(json.dumps({"anomalous": manifest["counts"]["anomalous"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
