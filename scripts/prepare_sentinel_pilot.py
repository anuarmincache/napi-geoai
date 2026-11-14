"""Estágio incompleto do NDVI de Maringá.

Mesmo com B04, B08 e SCL locais, este comando não recorta, não alinha SCL
e não publica raster. Credencial de download, se existir, não conclui o piloto.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NDVI piloto Maringá; o pipeline real ainda não publica"
    )
    parser.add_argument("--b04", default="")
    parser.add_argument("--b08", default="")
    parser.add_argument("--scl", default="")
    args = parser.parse_args(argv)
    paths = [args.b04, args.b08, args.scl]
    if not all(paths) or not all(Path(item).is_file() for item in paths):
        print("Bandas locais ausentes. ndvi_published falso.", file=sys.stderr)
        print("ndvi_published", False)
        return 2
    print(
        "Os três caminhos existem, mas o pipeline georreferenciado "
        "(recorte, SCL nearest, reflectância, NDVI e COG) não está "
        "implementado. Este comando não publica raster.",
        file=sys.stderr,
    )
    print("ndvi_published", False)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
