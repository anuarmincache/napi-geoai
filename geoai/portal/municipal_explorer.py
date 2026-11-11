"""Explorador territorial municipal — serviços portáveis (sem Streamlit)."""

from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd

from geoai.boundaries.validate import crs_equals
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT, EXPECTED_SOURCE_CRS
from geoai.portal.paths import (
    municipalities_geojson_path,
    municipalities_provenance_path,
    municipalities_validation_path,
    repo_root_from_here,
)
from geoai.qgis.municipal_report import (
    cross_check_qgis_report,
    load_qgis_municipal_report,
)
from geoai.quality import is_sha256_hex, verify_content_sha256

# Atalhos regionais — NÃO são ranking comercial (Issue #20 / #26).
POLO_CITIES: tuple[tuple[str, str], ...] = (
    ("4106902", "Curitiba"),
    ("4125506", "São José dos Pinhais"),
    ("4101804", "Araucária"),
    ("4118204", "Paranaguá"),
    ("4119905", "Ponta Grossa"),
    ("4127106", "Telêmaco Borba"),
    ("4109401", "Guarapuava"),
    ("4104303", "Campo Mourão"),
    ("4110706", "Irati"),
    ("4113700", "Londrina"),
    ("4101408", "Apucarana"),
    ("4111803", "Jacarezinho"),
    ("4115200", "Maringá"),
    ("4118402", "Paranavaí"),
    ("4128104", "Umuarama"),
    ("4104808", "Cascavel"),
    ("4127700", "Toledo"),
    ("4108304", "Foz do Iguaçu"),
    ("4108403", "Francisco Beltrão"),
    ("4118501", "Pato Branco"),
)


def _strip_accents(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _norm_name(text: str) -> str:
    return " ".join(_strip_accents(text).casefold().split())


@dataclass(frozen=True, slots=True)
class MunicipalityRecord:
    code: str
    name: str
    area_km2: float
    uf: str


@dataclass(frozen=True, slots=True)
class MunicipalityLayerBundle:
    gdf: gpd.GeoDataFrame
    provenance: dict[str, Any]
    validation: dict[str, Any]
    geojson_path: Path
    available: bool
    missing_reason_pt: str | None = None
    content_sha256_ok: bool | None = None

    @property
    def feature_count(self) -> int:
        return int(len(self.gdf)) if self.available else 0

    @property
    def validated_for_map(self) -> bool:
        return self.available


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _empty() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[], crs=None)



def area_km2_values_ok(values: Any) -> bool:
    """True somente se todos os valores forem finitos e > 0 (rejeita ±inf/NaN)."""

    try:
        return all(math.isfinite(float(v)) and float(v) > 0 for v in values)
    except (TypeError, ValueError):
        return False


def load_municipality_layer(repo_root: Path | None = None) -> MunicipalityLayerBundle:
    """Carrega malha municipal de apresentação com fail-closed (SHA/CRS/contagem)."""

    root = repo_root or repo_root_from_here()
    geo_path = municipalities_geojson_path(root)
    prov_path = municipalities_provenance_path(root)
    val_path = municipalities_validation_path(root)

    if not geo_path.is_file():
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance={},
            validation={},
            geojson_path=geo_path,
            available=False,
            missing_reason_pt=(
                "GeoJSON municipal ausente. Gere com "
                "scripts/prepare_parana_municipalities.py."
            ),
            content_sha256_ok=None,
        )

    provenance = _read_json(prov_path) if prov_path.is_file() else {}
    validation = _read_json(val_path) if val_path.is_file() else {}
    gdf = gpd.read_file(geo_path)
    if gdf.crs is None:
        declared = validation.get("source_crs")
        if declared:
            gdf = gdf.set_crs(declared)
        else:
            return MunicipalityLayerBundle(
                gdf=_empty(),
                provenance=provenance,
                validation=validation,
                geojson_path=geo_path,
                available=False,
                missing_reason_pt="CRS ausente no GeoJSON e na validação.",
                content_sha256_ok=None,
            )

    derived_sha = provenance.get("derived_geojson_sha256")
    sha_ok: bool | None
    if isinstance(derived_sha, str) and is_sha256_hex(derived_sha):
        sha_ok = verify_content_sha256(derived_sha, geo_path.read_bytes())
    else:
        sha_ok = None

    if sha_ok is False:
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt="SHA-256 do GeoJSON municipal diverge da proveniência.",
            content_sha256_ok=False,
        )

    if "CD_MUN" not in gdf.columns or "NM_MUN" not in gdf.columns:
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt="Colunas CD_MUN/NM_MUN ausentes.",
            content_sha256_ok=sha_ok,
        )

    declared_crs = validation.get("source_crs")
    if not declared_crs:
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt="validation.source_crs ausente.",
            content_sha256_ok=sha_ok,
        )
    if not crs_equals(declared_crs, EXPECTED_SOURCE_CRS):
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt=(
                f"validation.source_crs incompatível: {declared_crs} "
                f"(esperado {EXPECTED_SOURCE_CRS})."
            ),
            content_sha256_ok=sha_ok,
        )
    if not crs_equals(gdf.crs, declared_crs):
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt=(
                f"CRS efetivo {gdf.crs} diverge de validation.source_crs "
                f"{declared_crs}."
            ),
            content_sha256_ok=sha_ok,
        )
    if not crs_equals(gdf.crs, EXPECTED_SOURCE_CRS):
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt=(
                f"CRS divergente: esperado {EXPECTED_SOURCE_CRS}, "
                f"obtido {gdf.crs}."
            ),
            content_sha256_ok=sha_ok,
        )

    if "AREA_KM2" not in gdf.columns:
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt="Coluna AREA_KM2 ausente (atributo oficial IBGE).",
            content_sha256_ok=sha_ok,
        )

    gdf = gdf.copy()
    gdf["CD_MUN"] = gdf["CD_MUN"].astype(str).str.strip()
    gdf["NM_MUN"] = gdf["NM_MUN"].astype(str).str.strip()
    gdf["AREA_KM2"] = gdf["AREA_KM2"].astype(float)

    prefix_ok = bool(gdf["CD_MUN"].str.fullmatch(r"41\d{5}").all())
    area_ok = area_km2_values_ok(gdf["AREA_KM2"])
    geom_present_ok = bool(
        (~gdf.geometry.isna()).all() and (~gdf.geometry.is_empty).all()
    )

    count_ok = len(gdf) == EXPECTED_PR_MUNICIPALITY_COUNT
    unique_ok = gdf["CD_MUN"].nunique() == EXPECTED_PR_MUNICIPALITY_COUNT
    geom_ok = validation.get("validation_presentation", {}).get("all_valid")
    if geom_ok is None:
        geom_ok = validation.get("validation_exportable")

    qgis_problems: list[str] = []
    qgis_report = load_qgis_municipal_report(root)
    if qgis_report is not None:
        qgis_problems = cross_check_qgis_report(
            qgis_report,
            provenance,
            validation=validation,
        )

    if not (
        count_ok
        and unique_ok
        and geom_ok is True
        and sha_ok is True
        and prefix_ok
        and area_ok
        and geom_present_ok
        and not qgis_problems
    ):
        reasons = []
        if not count_ok:
            reasons.append(f"contagem={len(gdf)} (esperado 399)")
        if not unique_ok:
            reasons.append("CD_MUN não únicos")
        if not prefix_ok:
            reasons.append("CD_MUN fora do padrão 41xxxxx (PR)")
        if not area_ok:
            reasons.append("AREA_KM2 inválida (não finita ou <=0)")
        if not geom_present_ok:
            reasons.append("geometrias nulas ou vazias")
        if geom_ok is not True:
            reasons.append("validação geométrica não confirmada")
        if sha_ok is not True:
            reasons.append("SHA derivado ausente/não verificado")
        if qgis_problems:
            reasons.append("relatório QGIS inconsistente: " + "; ".join(qgis_problems))
        return MunicipalityLayerBundle(
            gdf=_empty(),
            provenance=provenance,
            validation=validation,
            geojson_path=geo_path,
            available=False,
            missing_reason_pt="Camada municipal rejeitada: " + "; ".join(reasons),
            content_sha256_ok=sha_ok,
        )

    return MunicipalityLayerBundle(
        gdf=gdf,
        provenance=provenance,
        validation=validation,
        geojson_path=geo_path,
        available=True,
        missing_reason_pt=None,
        content_sha256_ok=True,
    )


def list_municipalities(
    bundle: MunicipalityLayerBundle,
) -> tuple[MunicipalityRecord, ...]:
    if not bundle.available:
        return ()
    rows: list[MunicipalityRecord] = []
    for _, row in bundle.gdf.sort_values("NM_MUN").iterrows():
        rows.append(
            MunicipalityRecord(
                code=str(row["CD_MUN"]),
                name=str(row["NM_MUN"]),
                area_km2=float(row["AREA_KM2"]) if "AREA_KM2" in row else float("nan"),
                uf=str(row.get("SIGLA_UF", "PR")),
            )
        )
    return tuple(rows)


def municipality_label(rec: MunicipalityRecord) -> str:
    """Rótulo estável para seletores: Nome (código IBGE)."""

    return f"{rec.name} ({rec.code})"


def search_municipalities(
    bundle: MunicipalityLayerBundle,
    query: str,
    *,
    limit: int | None = None,
) -> tuple[MunicipalityRecord, ...]:
    """Busca por substring de nome (sem acento) ou código IBGE.

    - Consulta vazia: devolve o catálogo completo (todos os 399), salvo
      ``limit`` explícito.
    - Consulta sem correspondência: devolve tupla vazia (sem fallback).
    """

    rows = list_municipalities(bundle)
    q = _norm_name(query or "")
    if not q:
        hits = rows
    else:
        hits = tuple(
            rec
            for rec in rows
            if q in _norm_name(rec.name) or q in rec.code
        )
    if limit is not None:
        hits = hits[: max(0, int(limit))]
    return tuple(hits)


def get_municipality(
    bundle: MunicipalityLayerBundle,
    code: str,
) -> MunicipalityRecord | None:
    code = str(code).strip()
    for rec in list_municipalities(bundle):
        if rec.code == code:
            return rec
    return None


def polo_city_records(
    bundle: MunicipalityLayerBundle,
) -> tuple[MunicipalityRecord, ...]:
    """Resolve atalhos de cidades-polo contra a malha (sem inventar códigos)."""

    found: list[MunicipalityRecord] = []
    for code, _label in POLO_CITIES:
        rec = get_municipality(bundle, code)
        if rec is not None:
            found.append(rec)
    return tuple(found)


def compare_municipalities(
    bundle: MunicipalityLayerBundle,
    code_a: str,
    code_b: str,
) -> dict[str, Any]:
    """Compara só atributos verificáveis da malha (sem indicadores inventados)."""

    a = get_municipality(bundle, code_a)
    b = get_municipality(bundle, code_b)
    if a is None or b is None:
        return {
            "ok": False,
            "message": "Um ou ambos os códigos não existem na malha validada.",
            "a": a,
            "b": b,
        }
    area_delta = None
    if a.area_km2 == a.area_km2 and b.area_km2 == b.area_km2:  # not NaN
        area_delta = round(a.area_km2 - b.area_km2, 3)
    return {
        "ok": True,
        "a": {
            "code": a.code,
            "name": a.name,
            "area_km2": a.area_km2,
            "uf": a.uf,
        },
        "b": {
            "code": b.code,
            "name": b.name,
            "area_km2": b.area_km2,
            "uf": b.uf,
        },
        "area_km2_delta_a_minus_b": area_delta,
        "area_source": bundle.provenance.get("area_attribute_source")
        or "AREA_KM2 da Malha Municipal Digital IBGE",
        "disclaimer_pt": (
            "Comparação administrativa territorial apenas. "
            "Não implica aptidão solar, PIB, população nem oportunidade comercial."
        ),
    }


def municipality_map_html(
    bundle: MunicipalityLayerBundle,
    *,
    selected_code: str | None = None,
    fill_opacity: float = 0.25,
    line_weight: float = 1.0,
) -> str:
    if not bundle.available:
        raise FileNotFoundError(
            bundle.missing_reason_pt or "camada municipal não validada"
        )
    try:
        import folium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Pacote folium necessário. Instale: pip install 'napi-geoai[ui]'"
        ) from exc

    gdf_plot = bundle.gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf_plot.total_bounds
    center = [(miny + maxy) / 2.0, (minx + maxx) / 2.0]
    fmap = folium.Map(
        location=center,
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    selected = str(selected_code).strip() if selected_code else None

    def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
        code = str(feat.get("properties", {}).get("CD_MUN", ""))
        if selected and code == selected:
            return {
                "fillColor": "#c45c26",
                "color": "#7c2d12",
                "weight": max(line_weight, 2.5),
                "fillOpacity": min(fill_opacity + 0.35, 0.85),
            }
        return {
            "fillColor": "#1f4e79",
            "color": "#0b2545",
            "weight": line_weight,
            "fillOpacity": fill_opacity,
        }

    folium.GeoJson(
        data=json.loads(gdf_plot.to_json()),
        name="Municípios PR — IBGE",
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                c
                for c in ("NM_MUN", "CD_MUN", "AREA_KM2")
                if c in gdf_plot.columns
            ],
            aliases=["Município", "Código IBGE", "Área (km² IBGE)"],
        ),
    ).add_to(fmap)

    # Enquadramento: Paraná inteiro na 1ª visita; seleção com padding
    # (evita zoom excessivo / faixa preta no iframe Streamlit).
    if selected:
        hit = gdf_plot[gdf_plot["CD_MUN"].astype(str) == selected]
        if not hit.empty:
            b = hit.total_bounds
            fmap.fit_bounds([[b[1], b[0]], [b[3], b[2]]], padding=(28, 28))
        else:
            fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
    else:
        fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))

    # Fundo claro no container Leaflet — reduz retângulo preto no iframe.
    try:
        from branca.element import Element

        fmap.get_root().html.add_child(
            Element(
                "<style>"
                "html,body{margin:0;height:100%;background:#e8eef5;}"
                ".leaflet-container{background:#e8eef5!important;}"
                "</style>"
            )
        )
    except Exception:  # pragma: no cover - branca sempre presente com folium
        pass

    return fmap.get_root().render()


def explorer_attribution_lines(bundle: MunicipalityLayerBundle) -> tuple[str, ...]:
    lines = [
        "Fonte: IBGE — Malhas Territoriais / Malhas Municipais",
        f"Edição: {bundle.provenance.get('edition') or 'indisponível'}",
        f"Feições: {bundle.feature_count} (esperado {EXPECTED_PR_MUNICIPALITY_COUNT})",
    ]
    retrieved = bundle.provenance.get("retrieved_at")
    if retrieved:
        lines.append(f"Recuperado em: {retrieved}")
    else:
        lines.append("Data de recuperação: indisponível")
    tol = bundle.provenance.get("presentation_simplify_tolerance_deg")
    if tol is not None:
        lines.append(f"Simplificação de apresentação: {tol}° (preserve_topology)")
    lines.append(
        "Área (km²): atributo oficial AREA_KM2 da malha IBGE — "
        "não é aptidão solar nem viabilidade comercial."
    )
    license_note = bundle.provenance.get("license_note")
    if license_note:
        lines.append(f"Licença / uso: {license_note}")
    return tuple(lines)
