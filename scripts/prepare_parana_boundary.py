"""CLI: baixa e valida o limite oficial do Paraná (IBGE Malha Municipal 2025)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geoai.boundaries.parana import prepare_parana_boundary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Obtém o limite do Paraná a partir da malha IBGE e valida geometria/CRS. "
            "Produto técnico territorial — não é mapa de aptidão solar."
        )
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "ibge",
        help="Diretório para o ZIP bruto (não versionado).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "derived" / "parana_uf_2025.geojson",
        help="GeoJSON derivado (pode ser versionado se pequeno).",
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        default=ROOT / "data" / "derived" / "parana_uf_2025.provenance.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data" / "derived" / "parana_uf_2025.validation.json",
    )
    args = parser.parse_args()

    path, source, report = prepare_parana_boundary(
        args.output,
        raw_dir=args.raw_dir,
        provenance_path=args.provenance,
        report_path=args.report,
    )
    print(f"output={path}")
    print(f"sha256={source.content_sha256}")
    print(f"crs={report.crs}")
    print(f"features={report.feature_count}")
    print(f"all_valid={report.all_valid}")
    print("note=produto_tecnico_limites_nao_aptidao_solar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
