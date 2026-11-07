"""Validação geométrica mínima para camadas poligonais territoriais."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import geopandas as gpd
from pyproj import CRS
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity, make_valid

POLYGON_TYPES = frozenset({"Polygon", "MultiPolygon"})


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
    crs_missing: bool
    crs_mismatch: bool
    explanations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def is_exportable(self) -> bool:
        """True somente quando o relatório permite exportação segura."""

        return (
            self.feature_count > 0
            and self.all_valid
            and self.invalid_count == 0
            and self.empty_count == 0
            and self.non_polygon_count == 0
            and not self.crs_missing
            and not self.crs_mismatch
        )


class BoundaryValidationError(ValueError):
    """Falha fatal de validação territorial antes da exportação."""


def crs_equals(actual: object | None, expected: str) -> bool:
    """Compara CRS via ``pyproj.CRS.equals`` (sem matching por substring)."""

    if actual is None:
        return False
    try:
        return CRS.from_user_input(actual).equals(CRS.from_user_input(expected))
    except Exception:
        return False


def _flatten_polygons(parts: list[BaseGeometry]) -> list[Polygon]:
    flat: list[Polygon] = []
    for part in parts:
        if isinstance(part, Polygon):
            flat.append(part)
        elif isinstance(part, MultiPolygon):
            flat.extend(list(part.geoms))
    return flat


def _polygonal_component(geom: BaseGeometry | None) -> BaseGeometry | None:
    """Extrai apenas componentes Polygon/MultiPolygon de um ``make_valid``."""

    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in POLYGON_TYPES:
        return geom
    if isinstance(geom, GeometryCollection):
        polys = [
            part
            for part in geom.geoms
            if part.geom_type in POLYGON_TYPES and not part.is_empty
        ]
        flat = _flatten_polygons(polys)
        if not flat:
            return None
        if len(flat) == 1:
            return flat[0]
        return MultiPolygon(flat)
    return None


def validate_polygon_layer(
    gdf: gpd.GeoDataFrame,
    *,
    expected_crs: str | None = None,
    repair: bool = False,
) -> tuple[gpd.GeoDataFrame, GeometryValidationReport]:
    """Valida geometrias poligonais e, opcionalmente, aplica ``make_valid``.

    Se ``repair=True`` e o resultado for ``GeometryCollection`` com linhas/pontos,
    somente componentes poligonais são mantidos; ausência de polígono conta como
    não poligonal/vazio.
    """

    if gdf.geometry is None:
        raise ValueError("GeoDataFrame sem coluna de geometria.")

    working = gdf.copy()
    if repair:
        repaired: list[BaseGeometry | None] = []
        for geom in working.geometry:
            if geom is None:
                repaired.append(None)
                continue
            fixed = make_valid(geom)
            repaired.append(_polygonal_component(fixed))
        working["geometry"] = repaired

    invalid_mask = ~working.geometry.is_valid.fillna(False)
    empty_mask = working.geometry.is_empty.fillna(True) | working.geometry.isna()
    non_polygon_mask = ~working.geometry.geom_type.isin(list(POLYGON_TYPES)).fillna(
        False
    )

    explanations: list[str] = []
    for idx in working.index[invalid_mask]:
        geom = working.loc[idx, "geometry"]
        if geom is None or (hasattr(geom, "is_empty") and geom.is_empty):
            explanations.append(f"{idx}: empty or null geometry")
        else:
            explanations.append(f"{idx}: {explain_validity(geom)}")

    crs_missing = working.crs is None
    crs_str = working.crs.to_string() if working.crs is not None else None
    crs_mismatch = False
    if expected_crs is not None:
        if crs_missing:
            crs_mismatch = True
            explanations.append(f"CRS ausente; esperado {expected_crs}")
        elif not crs_equals(working.crs, expected_crs):
            crs_mismatch = True
            explanations.append(
                f"CRS divergente: esperado {expected_crs}, obtido {crs_str}"
            )

    has_z = bool(working.geometry.has_z.fillna(False).any()) if len(working) else False
    report = GeometryValidationReport(
        feature_count=len(working),
        crs=crs_str,
        is_geographic=bool(working.crs.is_geographic) if working.crs else None,
        all_valid=bool((~invalid_mask).all()) if len(working) else False,
        invalid_count=int(invalid_mask.sum()),
        empty_count=int(empty_mask.sum()),
        non_polygon_count=int(non_polygon_mask.sum()),
        has_z=has_z,
        crs_missing=crs_missing,
        crs_mismatch=crs_mismatch,
        explanations=tuple(explanations[:20]),
    )
    return working, report


def assert_exportable(
    report: GeometryValidationReport,
    *,
    context: str = "boundary validation",
) -> None:
    """Levanta ``BoundaryValidationError`` se o relatório não for exportável."""

    if report.is_exportable:
        return
    details = "; ".join(report.explanations) or repr(report.to_dict())
    raise BoundaryValidationError(
        f"{context}: validação fatal "
        f"(features={report.feature_count}, valid={report.all_valid}, "
        f"empty={report.empty_count}, non_polygon={report.non_polygon_count}, "
        f"crs_missing={report.crs_missing}, crs_mismatch={report.crs_mismatch}): "
        f"{details}"
    )
