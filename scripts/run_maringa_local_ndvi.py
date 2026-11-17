"""NDVI local e offline de Maringá. Não é o comando de medição.

Não lê credencial, não abre rede e não altera o catálogo científico.
Os seis JP2 e a malha precisam ser caminhos explícitos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.sentinel.gdal_scene import (  # noqa: E402
    municipality_bounds,
    raster_info,
    rasterize_municipality,
)
from geoai.sentinel.grid import snap_aoi_grid  # noqa: E402
from geoai.sentinel.integrity import band_contract  # noqa: E402
from geoai.sentinel.local_ndvi import (  # noqa: E402
    TILES,
    bind_bands,
    run_local_ndvi,
    validate_local_bands,
)

BANDS = ("B04_10m", "B08_10m", "SCL_20m")
MUNICIPALITY = "4115200"
APPROVED_ACQUISITION = "S2B_20261112T133149_R081"


def _contracts(catalog: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (tile, band): band_contract(catalog, tile, band)
        for tile in TILES
        for band in BANDS
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NDVI local de Maringá, sem rede")
    parser.add_argument("--b04", required=True)
    parser.add_argument("--b08-22kcv", required=True)
    parser.add_argument("--scl-22kcv", required=True)
    parser.add_argument("--b04-22kdv", required=True)
    parser.add_argument("--b08-22kdv", required=True)
    parser.add_argument("--scl-22kdv", required=True)
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    bands = bind_bands(
        b04_22kcv=Path(args.b04),
        b08_22kcv=Path(args.b08_22kcv),
        scl_22kcv=Path(args.scl_22kcv),
        b04_22kdv=Path(args.b04_22kdv),
        b08_22kdv=Path(args.b08_22kdv),
        scl_22kdv=Path(args.scl_22kdv),
    )
    mesh = Path(args.mesh)
    catalog_path = Path(args.catalog)
    try:
        for path in bands.values():
            if not path.is_file():
                raise FileNotFoundError(path.name)
        if not mesh.is_file():
            raise FileNotFoundError("malha_ausente")
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        if catalog.get("measured_acquisition_id") != APPROVED_ACQUISITION:
            raise RuntimeError("passagem_recusada")
        contracts = _contracts(catalog)
        validate_local_bands(bands, contracts)
        reference = raster_info(bands[("22KCV", "B04_10m")])
        bounds = municipality_bounds(mesh, MUNICIPALITY, reference["projection"])
        grid = snap_aoi_grid(bounds, reference["geotransform"])
        aoi = rasterize_municipality(
            mesh,
            MUNICIPALITY,
            grid["geotransform"],
            int(grid["cols"]),
            int(grid["rows"]),
            reference["projection"],
        )
        payload = run_local_ndvi(
            bands,
            contracts,
            aoi,
            grid["geotransform"],
            Path(args.output),
            Path(args.manifest),
            allow_download=False,
            catalog_path=catalog_path,
        )
    except Exception as error:
        text = str(error) or type(error).__name__
        if any(part in text for part in ("Bearer", "access_token", "CDSE_PASSWORD")):
            text = type(error).__name__
        print(text, file=sys.stderr)
        print("ndvi_published False")
        print("cog null")
        return 2
    print(f"n_aoi={payload['counts']['n_aoi']}")
    print(f"n_valid={payload['counts']['n_valid']}")
    print("ndvi_published False")
    print("cog null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
