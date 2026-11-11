"""Preparação da malha municipal do Paraná (IBGE municipio_2025)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import geopandas as gpd

from geoai.boundaries.parana import MAP_CRS, MAP_CRS_WEST_NOTE, REPO_ROOT, _rel_to_repo
from geoai.boundaries.validate import (
    BoundaryValidationError,
    GeometryValidationReport,
    assert_exportable,
    validate_polygon_layer,
)
from geoai.connectors.ibge import (
    EXPECTED_PR_MUNICIPALITY_COUNT,
    EXPECTED_SOURCE_CRS,
    IBGE_MUNICIPIOS_SOURCE_ID,
    IBGE_PR_MUNICIPIOS_2025_URL,
    IbgeMalhaSource,
    download_ibge_zip,
)

# Tolerância em graus (~EPSG:4674) só para apresentação Streamlit/Cloud.
PRESENTATION_SIMPLIFY_TOLERANCE_DEG = 0.002
KEEP_COLUMNS = ("CD_MUN", "NM_MUN", "SIGLA_UF", "CD_UF", "AREA_KM2")


def _find_municipios_shp(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    shp = [
        n
        for n in names
        if n.lower().endswith(".shp") and "municip" in n.lower()
    ]
    if not shp:
        raise FileNotFoundError(f"Shapefile municipal ausente em {zip_path}")
    return shp[0]


def read_ibge_municipios_zip(
    zip_path: Path,
    *,
    assume_crs: str | None = None,
) -> gpd.GeoDataFrame:
    member = _find_municipios_shp(zip_path)
    vsizip = f"/vsizip/{zip_path.resolve().as_posix()}/{member}"
    gdf = gpd.read_file(vsizip)
    if gdf.crs is None:
        if assume_crs is None:
            raise BoundaryValidationError(
                "CRS ausente na malha municipal IBGE. Sem inferência silenciosa."
            )
        gdf = gdf.set_crs(assume_crs)
    return gdf


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_parana_municipalities(
    output_geojson: Path,
    *,
    raw_dir: Path,
    provenance_path: Path,
    report_path: Path,
    url: str = IBGE_PR_MUNICIPIOS_2025_URL,
    repair: bool = True,
    simplify_tolerance_deg: float = PRESENTATION_SIMPLIFY_TOLERANCE_DEG,
    assume_crs_if_missing: str | None = None,
) -> tuple[Path, IbgeMalhaSource, GeometryValidationReport]:
    """Baixa, valida 399 municípios e exporta GeoJSON leve de apresentação.

    ``AREA_KM2`` é o atributo oficial da malha IBGE (não inventado).
    A simplificação geométrica é só para UI; o ZIP bruto permanece a referência
    de alta fidelidade regenerável.
    """

    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "PR_Municipios_2025.zip"

    source = download_ibge_zip(
        url,
        zip_path,
        source_id=IBGE_MUNICIPIOS_SOURCE_ID,
        timeout_s=300.0,
    )

    gdf = read_ibge_municipios_zip(zip_path, assume_crs=assume_crs_if_missing)
    missing = [c for c in KEEP_COLUMNS if c not in gdf.columns]
    if missing:
        raise BoundaryValidationError(
            f"Colunas obrigatórias ausentes na malha municipal: {missing}"
        )

    gdf = gdf.loc[:, list(KEEP_COLUMNS) + ["geometry"]].copy()
    gdf["CD_MUN"] = gdf["CD_MUN"].astype(str).str.strip()
    gdf["NM_MUN"] = gdf["NM_MUN"].astype(str).str.strip()
    gdf["SIGLA_UF"] = gdf["SIGLA_UF"].astype(str).str.upper().str.strip()
    gdf["CD_UF"] = gdf["CD_UF"].astype(str).str.strip()
    gdf["AREA_KM2"] = gdf["AREA_KM2"].astype(float)

    gdf = gdf[gdf["SIGLA_UF"] == "PR"]
    uf_codes = {str(c).lstrip("0") or "0" for c in gdf["CD_UF"].unique()}
    if uf_codes != {"41"}:
        raise BoundaryValidationError(
            f"CD_UF inesperado fora do Paraná (41): {sorted(uf_codes)}"
        )

    if len(gdf) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise BoundaryValidationError(
            f"Esperado {EXPECTED_PR_MUNICIPALITY_COUNT} municípios; "
            f"obtido {len(gdf)}."
        )
    if gdf["CD_MUN"].nunique() != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise BoundaryValidationError("CD_MUN não é único para todos os municípios.")

    validated, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=repair
    )
    assert_exportable(report, context="prepare_parana_municipalities")

    presentation = validated.copy()
    presentation["geometry"] = presentation.geometry.simplify(
        simplify_tolerance_deg,
        preserve_topology=True,
    )
    if int(presentation.geometry.is_empty.sum()) > 0:
        raise BoundaryValidationError(
            "Simplificação produziu geometria vazia — reduza a tolerância."
        )
    _, report_pres = validate_polygon_layer(
        presentation, expected_crs=EXPECTED_SOURCE_CRS, repair=False
    )
    assert_exportable(report_pres, context="presentation_simplify")

    output_geojson = Path(output_geojson)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    presentation.to_file(output_geojson, driver="GeoJSON")
    derived_sha = _sha256_file(output_geojson)

    portable = source.to_dict()
    portable["local_zip"] = _rel_to_repo(zip_path)
    portable["source_id"] = IBGE_MUNICIPIOS_SOURCE_ID
    portable["feature_count_expected"] = EXPECTED_PR_MUNICIPALITY_COUNT
    portable["feature_count"] = int(len(presentation))
    portable["derived_geojson"] = _rel_to_repo(output_geojson)
    portable["derived_geojson_sha256"] = derived_sha
    portable["derived_geojson_bytes"] = int(output_geojson.stat().st_size)
    portable["presentation_simplify_tolerance_deg"] = simplify_tolerance_deg
    portable["presentation_note"] = (
        "GeoJSON versionado é simplificado para UI/Cloud; "
        "alta fidelidade = ZIP IBGE regenerável em data/raw/ibge/."
    )
    portable["area_attribute"] = "AREA_KM2"
    portable["area_attribute_source"] = (
        "Campo oficial da Malha Municipal Digital IBGE (não calculado em graus)."
    )
    provenance_path = Path(provenance_path)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(
        json.dumps(portable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    payload = {
        "product": "malha_municipal_parana",
        "not_a_solar_suitability_map": True,
        "source_id": IBGE_MUNICIPIOS_SOURCE_ID,
        "source_crs": report.crs,
        "recommended_map_crs": MAP_CRS,
        "map_crs_limitation": MAP_CRS_WEST_NOTE,
        "feature_count": int(len(presentation)),
        "unique_cd_mun": int(presentation["CD_MUN"].nunique()),
        "area_km2_attribute": "AREA_KM2",
        "area_km2_note": (
            "Área oficial publicada na malha IBGE (km²). "
            "Não recalcular em EPSG:4674; UTM 22S não cobre sozinha o oeste do PR."
        ),
        "presentation_simplify_tolerance_deg": simplify_tolerance_deg,
        "validation_full": report.to_dict(),
        "validation_presentation": report_pres.to_dict(),
        "validation_exportable": report_pres.is_exportable,
        "output_geojson": _rel_to_repo(output_geojson),
        "repo_root_note": str(REPO_ROOT.name),
    }
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_geojson, source, report_pres
