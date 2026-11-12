"""Associação espacial SIGA → municípios (GeoPandas; QGIS é a evidência oficial)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import Point

from geoai.boundaries.municipalities import read_ibge_municipios_zip
from geoai.connectors.ibge import EXPECTED_SOURCE_CRS
from geoai.energy.siga_normalize import NormalizedPlant


def plants_to_geodataframe(plants: list[NormalizedPlant]) -> gpd.GeoDataFrame:
    rows: list[dict[str, Any]] = []
    geoms: list[Point | None] = []
    for plant in plants:
        rows.append(
            {
                "CodCEG": plant.cod_ceg,
                "NomEmpreendimento": plant.name,
                "DscFaseUsina": plant.phase,
                "SigTipoGeracao": plant.tipo_geracao,
                "DscOrigemCombustivel": plant.origem_combustivel,
                "potencia_outorgada_kw": plant.potencia_outorgada_kw,
                "potencia_fiscalizada_kw": plant.potencia_fiscalizada_kw,
                "municipios_declarados": plant.municipios_declarados,
                "coord_ok": plant.coord_ok,
            }
        )
        if plant.coord_ok and plant.lon is not None and plant.lat is not None:
            geoms.append(Point(plant.lon, plant.lat))
        else:
            geoms.append(None)
    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
    # Malha IBGE: EPSG:4674 (SIRGAS 2000) — alinhamento geográfico.
    return gdf.to_crs(EXPECTED_SOURCE_CRS)


def join_plants_to_municipalities(
    plants: list[NormalizedPlant],
    *,
    municipios_zip: Path,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """Point-in-polygon (within). Retorna GDF joined + estatísticas."""

    mun = read_ibge_municipios_zip(municipios_zip)
    mun = mun[["CD_MUN", "NM_MUN", "geometry"]].copy()
    mun["CD_MUN"] = mun["CD_MUN"].astype(str).str.strip()
    mun["NM_MUN"] = mun["NM_MUN"].astype(str).str.strip()

    pts = plants_to_geodataframe(plants)
    with_coord = pts[pts.geometry.notna() & ~pts.geometry.is_empty].copy()
    without_coord = pts[pts.geometry.isna() | pts.geometry.is_empty].copy()

    joined = gpd.sjoin(
        with_coord,
        mun,
        how="left",
        predicate="within",
    )
    # sjoin pode duplicar se tocar múltiplos polígonos (raro com within estrito)
    dup_mask = joined.index.duplicated(keep=False)
    ambiguous_codes = sorted(
        {str(c) for c in joined.loc[dup_mask, "CodCEG"].tolist()}
    )
    # Mantém primeira correspondência; marca ambíguos no relatório.
    joined = joined[~joined.index.duplicated(keep="first")].copy()

    matched = joined[joined["CD_MUN"].notna()].copy()
    unmatched_geom = joined[joined["CD_MUN"].isna()].copy()

    stats = {
        "engine": "geopandas.sjoin/within",
        "plants_input": len(plants),
        "with_coordinates": int(len(with_coord)),
        "without_coordinates": int(len(without_coord)),
        "matched": int(len(matched)),
        "unmatched_geometry": int(len(unmatched_geom)),
        "ambiguous_codes": ambiguous_codes,
        "crs_points": EXPECTED_SOURCE_CRS,
        "crs_municipalities": str(mun.crs) if mun.crs else None,
        "note": (
            "Implementação complementar GeoPandas. "
            "Relatório QGIS (native join) é a evidência oficial do MVP 10."
        ),
    }
    matched["match_status"] = "matched"
    unmatched_geom["match_status"] = "unmatched_geometry"
    without_coord = without_coord.copy()
    without_coord["CD_MUN"] = None
    without_coord["NM_MUN"] = None
    without_coord["match_status"] = "missing_coordinates"

    out = gpd.GeoDataFrame(
        pd_concat_frames([matched, unmatched_geom, without_coord]),
        crs=EXPECTED_SOURCE_CRS,
    )
    return out, stats


def pd_concat_frames(frames: list[gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    import pandas as pd

    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=EXPECTED_SOURCE_CRS)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
