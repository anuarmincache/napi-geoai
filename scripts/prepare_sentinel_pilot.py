"""Prepara o NDVI do piloto. Não baixa e não publica sem bandas locais.

Com o Python do QGIS, passe --b04, --b08 e --scl apontando para JP2 locais.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.sentinel.catalog import load_pilot_catalog  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NDVI piloto Pinhais, só com arquivos locais"
    )
    parser.add_argument("--b04", default="")
    parser.add_argument("--b08", default="")
    parser.add_argument("--scl", default="")
    args = parser.parse_args(argv)
    catalog = load_pilot_catalog(REPO)
    paths = [args.b04, args.b08, args.scl]
    if not all(paths) or not all(Path(item).is_file() for item in paths):
        message = catalog.get("public_message_pt") or "bandas locais ausentes"
        print(message, file=sys.stderr)
        print("ndvi_published", False)
        return 2
    print(
        "Arquivos locais presentes, mas o recorte GDAL georreferenciado "
        "ainda não foi executado nesta entrega porque o download oficial "
        "não foi autorizado.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
