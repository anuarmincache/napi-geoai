"""CLI: baixa e valida a malha municipal do Paraná (399 municípios IBGE)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geoai.boundaries.municipalities import (  # noqa: E402
    prepare_parana_municipalities,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Obtém os 399 municípios do Paraná (IBGE municipio_2025), valida "
            "contagem/CRS/geometria e exporta GeoJSON leve de apresentação."
        )
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "ibge",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "data"
        / "derived"
        / "parana_municipios_2025_presentation.geojson",
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        default=ROOT / "data" / "derived" / "parana_municipios_2025.provenance.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data" / "derived" / "parana_municipios_2025.validation.json",
    )
    args = parser.parse_args()

    path, source, report = prepare_parana_municipalities(
        args.output,
        raw_dir=args.raw_dir,
        provenance_path=args.provenance,
        report_path=args.report,
    )
    print(f"output={path}")
    print(f"zip_sha256={source.content_sha256}")
    print(f"crs={report.crs}")
    print(f"features={report.feature_count}")
    print(f"all_valid={report.all_valid}")
    print("note=malha_municipal_apresentacao_nao_aptidao_solar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
