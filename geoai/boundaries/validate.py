"""Validação geométrica mínima para camadas poligonais territoriais."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import geopandas as gpd
from shapely.validation import explain_validity, make_valid


@dataclass(frozen=True, slots=True)
class GeometryValidationReport:
    """Relatório objetivo de integridade geométrica e CRS."""

    feature_count: int
    crs: str | None
    is_geographic: bool | None
    all_valid: bool
    invalid_count: int
    empty_count: int
    non_polygon_count: int
    has_z: bool
    explanations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_polygon_layer(
    gdf: gpd.GeoDataFrame,
    *,
    expected_crs: str | None = None,
    repair: bool = False,
) -> tuple[gpd.GeoDataFrame, GeometryValidationReport]:
    """Valida geometrias poligonais e, opcionalmente, aplica ``make_valid``.

    Não altera atributos além da geometria quando ``repair=True``.
    """

    if gdf.geometry is None:
        raise ValueError("GeoDataFrame sem coluna de geometria.")

    working = gdf.copy()
    if repair:
        working["geometry"] = working.geometry.map(
            lambda geom: make_valid(geom) if geom is not None else geom
        )

    invalid_mask = ~working.geometry.is_valid
    empty_mask = working.geometry.is_empty | working.geometry.isna()
    non_polygon_mask = ~working.geometry.geom_type.isin(["Polygon", "MultiPolygon"])

    explanations: list[str] = []
    for idx in working.index[invalid_mask]:
        geom = working.loc[idx, "geometry"]
        explanations.append(f"{idx}: {explain_validity(geom)}")

    crs_str = working.crs.to_string() if working.crs is not None else None
    if expected_crs is not None and crs_str is not None:
        # Aceita equivalência EPSG:4674 == SIRGAS 2000.
        expected_norm = expected_crs.upper().replace(" ", "")
        actual_norm = crs_str.upper().replace(" ", "")
        if expected_norm not in actual_norm and actual_norm not in expected_norm:
            if "4674" not in actual_norm or "4674" not in expected_norm:
                explanations.append(
                    f"CRS divergente: esperado {expected_crs}, obtido {crs_str}"
                )

    has_z = bool(working.geometry.has_z.any()) if len(working) else False
    report = GeometryValidationReport(
        feature_count=len(working),
        crs=crs_str,
        is_geographic=bool(working.crs.is_geographic) if working.crs else None,
        all_valid=bool((~invalid_mask).all()) if len(working) else True,
        invalid_count=int(invalid_mask.sum()),
        empty_count=int(empty_mask.sum()),
        non_polygon_count=int(non_polygon_mask.sum()),
        has_z=has_z,
        explanations=tuple(explanations[:20]),
    )
    return working, report
