"""Leitura de um município na malha oficial IBGE já arquivada no repositório."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


def sirgas_utm_epsg(longitude: float, latitude: float) -> int:
    """EPSG SIRGAS 2000 / UTM a partir do centroide. Sul: 31960+zona."""

    if not -180.0 <= longitude < 180.0 or not -90.0 <= latitude <= 90.0:
        raise ValueError("centroide fora do intervalo geográfico")
    zone = int((longitude + 180.0) / 6.0) + 1
    base = 31936 if latitude >= 0 else 31960
    return base + zone


def _mun_code(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


@dataclass(frozen=True)
class OfficialMunicipality:
    name: str
    cd_mun: str
    area_km2_official: float
    crs: str
    bbox: list[float]
    geometry: BaseGeometry
    coverage_crs: str
    geometry_valid: bool
    geometry_source: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cd_mun": self.cd_mun,
            "area_km2_official": self.area_km2_official,
            "crs": self.crs,
            "bbox": self.bbox,
            "geometry_valid": self.geometry_valid,
            "coverage_crs": self.coverage_crs,
            "geometry_source": self.geometry_source,
        }


def load_official_municipality(mesh_zip: Path, cd_mun: str) -> OfficialMunicipality:
    """Área oficial é o atributo AREA_KM2. O bbox sai da geometria dessa feição."""

    import geopandas as gpd

    frame = gpd.read_file(mesh_zip)
    if frame.crs is None:
        raise ValueError(f"{mesh_zip} não declara CRS")
    wanted = _mun_code(cd_mun)
    codes = frame["CD_MUN"].map(_mun_code)
    rows = frame[codes == wanted]
    if len(rows) != 1:
        raise ValueError(f"CD_MUN {wanted}: {len(rows)} feições em {mesh_zip.name}")
    row = rows.iloc[0]
    geom = row.geometry
    if geom is None or geom.is_empty:
        raise ValueError(f"CD_MUN {wanted} sem geometria")
    minx, miny, maxx, maxy = geom.bounds
    centroid = geom.centroid
    epsg = sirgas_utm_epsg(float(centroid.x), float(centroid.y))
    source = mesh_zip.as_posix()
    return OfficialMunicipality(
        name=str(row["NM_MUN"]).strip(),
        cd_mun=wanted,
        area_km2_official=float(row["AREA_KM2"]),
        crs=frame.crs.to_string(),
        bbox=[float(minx), float(miny), float(maxx), float(maxy)],
        geometry=geom,
        coverage_crs=f"EPSG:{epsg}",
        geometry_valid=bool(geom.is_valid),
        geometry_source=source,
    )


def footprint_coverage_m2(
    scene_geometry: dict[str, Any],
    municipality: OfficialMunicipality,
) -> float:
    """Fração da área municipal no CRS métrico. A cena STAC entra como EPSG:4326."""

    import geopandas as gpd

    scene = shape(scene_geometry)
    if not scene.is_valid:
        from shapely import make_valid

        scene = make_valid(scene)
    aoi_m = gpd.GeoSeries([municipality.geometry], crs=municipality.crs).to_crs(
        municipality.coverage_crs
    )
    scene_m = gpd.GeoSeries([scene], crs="EPSG:4326").to_crs(municipality.coverage_crs)
    aoi_area = float(aoi_m.iloc[0].area)
    if aoi_area <= 0:
        raise ValueError("área métrica da AOI é nula")
    return float(scene_m.iloc[0].intersection(aoi_m.iloc[0]).area / aoi_area)


def union_coverage_m2(
    scene_geometries: list[dict[str, Any]],
    municipality: OfficialMunicipality,
) -> float:
    """Fração da AOI coberta pela união dos footprints. Não escolhe cena."""

    import geopandas as gpd
    from shapely import make_valid
    from shapely.ops import unary_union

    parts = []
    for geometry in scene_geometries:
        scene = shape(geometry)
        if not scene.is_valid:
            scene = make_valid(scene)
        parts.append(scene)
    if not parts:
        return 0.0
    united = unary_union(parts)
    aoi_m = gpd.GeoSeries([municipality.geometry], crs=municipality.crs).to_crs(
        municipality.coverage_crs
    )
    scene_m = gpd.GeoSeries([united], crs="EPSG:4326").to_crs(municipality.coverage_crs)
    aoi_area = float(aoi_m.iloc[0].area)
    if aoi_area <= 0:
        raise ValueError("área métrica da AOI é nula")
    covered = scene_m.iloc[0].intersection(aoi_m.iloc[0]).area
    return float(covered / aoi_area)
