"""Preparação do limite oficial do Paraná a partir da malha IBGE."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd

from geoai.boundaries.validate import GeometryValidationReport, validate_polygon_layer
from geoai.connectors.ibge import (
    EXPECTED_SOURCE_CRS,
    IBGE_PR_UF_2025_URL,
    IbgeMalhaSource,
    download_ibge_zip,
    write_provenance,
)

# SIRGAS 2000 / UTM zone 22S — métrico, adequado à maior parte do Paraná.
MAP_CRS = "EPSG:31982"


def _find_vector_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".shp", ".gpkg", ".geojson", ".json"))
        ]
    if not names:
        raise FileNotFoundError(f"Nenhum vetor encontrado em {zip_path}")
    # Preferir shapefile da UF.
    for name in names:
        if name.lower().endswith(".shp") and "uf" in name.lower():
            return name
    return names[0]


def read_ibge_uf_zip(zip_path: Path) -> gpd.GeoDataFrame:
    """Lê a camada vetorial contida no ZIP IBGE."""

    member = _find_vector_member(zip_path)
    # pyogrio/fiona leem /vsizip/ paths.
    vsizip = f"/vsizip/{zip_path.resolve().as_posix()}/{member}"
    gdf = gpd.read_file(vsizip)
    if gdf.crs is None:
        gdf = gdf.set_crs(EXPECTED_SOURCE_CRS)
    return gdf


def prepare_parana_boundary(
    output_geojson: Path,
    *,
    raw_dir: Path,
    provenance_path: Path,
    report_path: Path,
    url: str = IBGE_PR_UF_2025_URL,
    repair: bool = True,
) -> tuple[Path, IbgeMalhaSource, GeometryValidationReport]:
    """Baixa, valida e exporta o limite do Paraná em GeoJSON.

    O produto é um limite territorial técnico — não um mapa de aptidão solar.
    """

    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "PR_UF_2025.zip"

    source = download_ibge_zip(url, zip_path)
    write_provenance(source, provenance_path)

    gdf = read_ibge_uf_zip(zip_path)
    # Manter apenas feições do Paraná quando o atributo existir.
    for col in ("SIGLA_UF", "NM_UF", "CD_UF"):
        if col in gdf.columns:
            if col == "SIGLA_UF":
                gdf = gdf[gdf[col].astype(str).str.upper() == "PR"]
            elif col == "NM_UF":
                gdf = gdf[gdf[col].astype(str).str.upper().str.contains("PARAN")]
            elif col == "CD_UF":
                gdf = gdf[gdf[col].astype(str).isin(["41", "041"])]
            break

    if gdf.empty:
        raise ValueError("Nenhuma feição do Paraná encontrada na malha IBGE.")

    validated, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=repair
    )
    if report.invalid_count and not repair:
        raise ValueError(f"Geometrias inválidas: {report.explanations}")

    output_geojson = Path(output_geojson)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    # Exportar no CRS de origem (SIRGAS 2000) para fidelidade à fonte.
    validated.to_file(output_geojson, driver="GeoJSON")

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "product": "limite_territorial_parana",
        "not_a_solar_suitability_map": True,
        "source_crs": report.crs,
        "recommended_map_crs": MAP_CRS,
        "units_note": (
            "Fonte em graus (EPSG:4674). Para medidas métricas no mapa técnico, "
            f"usar {MAP_CRS} (metros)."
        ),
        "validation": report.to_dict(),
        "output_geojson": str(output_geojson.resolve()),
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output_geojson, source, report
