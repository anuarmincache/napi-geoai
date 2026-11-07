"""Preparação do limite oficial do Paraná a partir da malha IBGE."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd

from geoai.boundaries.validate import (
    BoundaryValidationError,
    GeometryValidationReport,
    assert_exportable,
    validate_polygon_layer,
)
from geoai.connectors.ibge import (
    EXPECTED_SOURCE_CRS,
    IBGE_PR_UF_2025_URL,
    IbgeMalhaSource,
    download_ibge_zip,
)

# SIRGAS 2000 / UTM zone 22S — adequado à maior parte do Paraná (centro-leste).
# A faixa oeste do estado (aprox. oeste de ~54°W) cai na zona UTM 21S (EPSG:31981).
# EPSG:31982 NÃO deve ser usado para área estadual total sem justificativa explícita.
MAP_CRS = "EPSG:31982"
MAP_CRS_WEST_NOTE = (
    "EPSG:31982 (UTM 22S) cobre a maior parte do Paraná; a porção ocidental "
    "pertence à zona UTM 21S (EPSG:31981). Medições métricas estaduais (área "
    "total, comprimento de limites) exigem projeção apropriada/justificada "
    "(ex.: Albers ou cálculo por zona), não UTM 22S isolado."
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _rel_to_repo(path: Path) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _find_vector_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".shp", ".gpkg", ".geojson", ".json"))
        ]
    if not names:
        raise FileNotFoundError(f"Nenhum vetor encontrado em {zip_path}")
    for name in names:
        if name.lower().endswith(".shp") and "uf" in name.lower():
            return name
    return names[0]


def read_ibge_uf_zip(
    zip_path: Path,
    *,
    assume_crs: str | None = None,
) -> gpd.GeoDataFrame:
    """Lê a camada vetorial contida no ZIP IBGE.

    Por padrão, CRS ausente gera erro explícito. Apenas com
    ``assume_crs='EPSG:4674'`` (opção excepcional documentada) o CRS é
    atribuído — nunca de forma silenciosa.
    """

    member = _find_vector_member(zip_path)
    vsizip = f"/vsizip/{zip_path.resolve().as_posix()}/{member}"
    gdf = gpd.read_file(vsizip)
    if gdf.crs is None:
        if assume_crs is None:
            raise BoundaryValidationError(
                "CRS ausente no vetor IBGE. Recuse inferência silenciosa; "
                "reesporte a malha com CRS ou chame "
                "read_ibge_uf_zip(..., assume_crs='EPSG:4674') de forma explícita."
            )
        gdf = gdf.set_crs(assume_crs)
    return gdf


def prepare_parana_boundary(
    output_geojson: Path,
    *,
    raw_dir: Path,
    provenance_path: Path,
    report_path: Path,
    url: str = IBGE_PR_UF_2025_URL,
    repair: bool = True,
    assume_crs_if_missing: str | None = None,
) -> tuple[Path, IbgeMalhaSource, GeometryValidationReport]:
    """Baixa, valida e exporta o limite do Paraná em GeoJSON.

    O produto é um limite territorial técnico — não um mapa de aptidão solar.
    Qualquer falha de validação impede a exportação (erro fatal).
    """

    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "PR_UF_2025.zip"

    source = download_ibge_zip(url, zip_path)
    # Proveniência portátil: caminho relativo ao repositório quando possível.
    portable = source.to_dict()
    portable["local_zip"] = _rel_to_repo(zip_path)
    provenance_path = Path(provenance_path)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(
        json.dumps(portable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    gdf = read_ibge_uf_zip(zip_path, assume_crs=assume_crs_if_missing)
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
        raise BoundaryValidationError(
            "Nenhuma feição do Paraná encontrada na malha IBGE."
        )

    validated, report = validate_polygon_layer(
        gdf, expected_crs=EXPECTED_SOURCE_CRS, repair=repair
    )
    assert_exportable(report, context="prepare_parana_boundary")

    output_geojson = Path(output_geojson)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    validated.to_file(output_geojson, driver="GeoJSON")

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "product": "limite_territorial_parana",
        "not_a_solar_suitability_map": True,
        "source_crs": report.crs,
        "recommended_map_crs": MAP_CRS,
        "map_crs_limitation": MAP_CRS_WEST_NOTE,
        "units_note": (
            "Fonte em graus (EPSG:4674). Para visualização métrica local, "
            f"{MAP_CRS} (metros) é adequado à maior parte do PR; ver "
            "map_crs_limitation para área estadual."
        ),
        "validation": report.to_dict(),
        "validation_exportable": report.is_exportable,
        "output_geojson": _rel_to_repo(output_geojson),
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output_geojson, source, report
