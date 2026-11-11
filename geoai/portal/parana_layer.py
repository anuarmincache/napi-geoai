"""Camada territorial do Paraná — carregamento portável (sem Streamlit)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd

from geoai.portal.paths import (
    parana_geojson_path,
    parana_provenance_path,
    parana_validation_path,
    repo_root_from_here,
)
from geoai.presentation import (
    AudienceLevel,
    DidacticMetadata,
    didactic_metadata_for_territorial_pr,
)
from geoai.quality import (
    QualityStatus,
    is_sha256_hex,
    territorial_pr_uf_schema,
    validate_tabular_record,
    verify_content_sha256,
)


@dataclass(frozen=True, slots=True)
class ParanaLayerBundle:
    """Pacote pronto para qualquer UI (Streamlit, FastAPI, portal)."""

    gdf: gpd.GeoDataFrame
    provenance: dict[str, Any]
    validation: dict[str, Any]
    didactic: DidacticMetadata
    geojson_path: Path
    available: bool
    missing_reason_pt: str | None = None
    content_sha256_ok: bool | None = None

    @property
    def feature_count(self) -> int:
        return int(len(self.gdf)) if self.available else 0

    @property
    def crs_epsg(self) -> str | None:
        if not self.available or self.gdf.crs is None:
            return None
        try:
            code = self.gdf.crs.to_epsg()
        except Exception:  # noqa: BLE001
            return str(self.gdf.crs)
        return f"EPSG:{code}" if code else str(self.gdf.crs)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_parana_layer(repo_root: Path | None = None) -> ParanaLayerBundle:
    """Carrega GeoJSON + metadados versionados; não consulta PostGIS."""

    root = repo_root or repo_root_from_here()
    geo_path = parana_geojson_path(root)
    prov_path = parana_provenance_path(root)
    val_path = parana_validation_path(root)

    if not geo_path.is_file():
        empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4674")
        return ParanaLayerBundle(
            gdf=empty,
            provenance={},
            validation={},
            didactic=didactic_metadata_for_territorial_pr(repo_root=root),
            geojson_path=geo_path,
            available=False,
            missing_reason_pt=(
                f"Artefato ausente: {geo_path.as_posix()}. "
                "Incorpore o GeoJSON derivado do IBGE sem inventar geometria."
            ),
            content_sha256_ok=None,
        )

    provenance = _read_json(prov_path) if prov_path.is_file() else {}
    validation = _read_json(val_path) if val_path.is_file() else {}
    gdf = gpd.read_file(geo_path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4674")

    sha_ok: bool | None = None
    derived_sha = provenance.get("derived_geojson_sha256")
    if isinstance(derived_sha, str) and is_sha256_hex(derived_sha):
        sha_ok = verify_content_sha256(derived_sha, geo_path.read_bytes())

    didactic = didactic_metadata_for_territorial_pr(repo_root=root)
    return ParanaLayerBundle(
        gdf=gdf,
        provenance=provenance,
        validation=validation,
        didactic=didactic,
        geojson_path=geo_path,
        available=True,
        missing_reason_pt=None,
        content_sha256_ok=sha_ok,
    )


def didactic_copy_text(
    bundle: ParanaLayerBundle,
    level: AudienceLevel | str,
) -> tuple[str, str]:
    """Retorna (título, descrição) para o nível didático."""

    lvl = AudienceLevel(level) if not isinstance(level, AudienceLevel) else level
    copy = bundle.didactic.copy_for(lvl)
    return copy.title, copy.description


def attribution_lines(bundle: ParanaLayerBundle) -> tuple[str, ...]:
    """Linhas de atribuição/legenda a partir dos contratos + proveniência."""

    d = bundle.didactic
    lines = [
        f"Legenda: {d.legend_pt}",
        f"Fonte: {d.source_attribution_pt}",
    ]
    edition = bundle.provenance.get("edition") or d.extra.get("edition")
    if edition:
        lines.append(f"Edição: {edition}")
    if d.updated_at:
        lines.append(f"Recuperado em: {d.updated_at}")
    else:
        lines.append("Data de recuperação: indisponível")
    if d.update_policy:
        lines.append(f"Política de atualização: {d.update_policy}")
    lines.append(f"Incerteza / limites: {d.uncertainty_pt}")
    license_note = bundle.provenance.get("license_note")
    if license_note:
        lines.append(f"Licença / uso: {license_note}")
    return tuple(lines)


def quality_snapshot_for_demo(bundle: ParanaLayerBundle) -> dict[str, Any]:
    """Relatório tabular ilustrativo (não valida geometria PostGIS)."""

    schema = territorial_pr_uf_schema()
    if not bundle.available:
        return {
            "status": QualityStatus.REJECTED.value,
            "scope": "tabular_record_only",
            "message": bundle.missing_reason_pt,
        }
    edition = str(bundle.provenance.get("edition") or "municipio_2025")
    collected = str(
        bundle.provenance.get("retrieved_at") or "2026-11-07T00:00:00+00:00"
    )
    sha = bundle.provenance.get("content_sha256")
    report = validate_tabular_record(
        schema,
        {
            "ibge_code": "41",
            "name": "Paraná",
            "mesh_edition": edition,
            "srid": 4674,
        },
        version_label=edition,
        collected_at=collected,
        content_sha256=sha if isinstance(sha, str) else None,
        limitations=("UI demo: sem inspeção PostGIS",),
    )
    return {
        "status": report.status.value,
        "scope": report.extra.get("scope"),
        "findings": [f.to_dict() for f in report.findings],
        "content_sha256_ok": bundle.content_sha256_ok,
        "validation_all_valid": bundle.validation.get("validation", {}).get(
            "all_valid"
        ),
    }


def folium_map_html(
    bundle: ParanaLayerBundle,
    *,
    fill_opacity: float = 0.35,
    line_weight: float = 2.0,
) -> str:
    """Gera HTML Folium do contorno PR (dependência opcional ``folium``)."""

    if not bundle.available:
        raise FileNotFoundError(bundle.missing_reason_pt or "camada ausente")

    try:
        import folium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Pacote folium necessário para o mapa. "
            "Instale: pip install 'napi-geoai[ui]'"
        ) from exc

    gdf_plot = bundle.gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = gdf_plot.total_bounds
    center = [(miny + maxy) / 2.0, (minx + maxx) / 2.0]
    fmap = folium.Map(location=center, zoom_start=6, tiles="OpenStreetMap")

    tooltip_fields = [
        c for c in ("NM_UF", "SIGLA_UF", "CD_UF") if c in gdf_plot.columns
    ]
    tooltip_aliases = {
        "NM_UF": "Nome",
        "SIGLA_UF": "UF",
        "CD_UF": "Código IBGE",
    }
    geojson_kwargs: dict[str, Any] = {
        "data": json.loads(gdf_plot.to_json()),
        "name": "Paraná (UF) — IBGE",
        "style_function": lambda _feat: {
            "fillColor": "#1f4e79",
            "color": "#0b2545",
            "weight": line_weight,
            "fillOpacity": fill_opacity,
        },
    }
    if tooltip_fields:
        geojson_kwargs["tooltip"] = folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=[tooltip_aliases[f] for f in tooltip_fields],
        )
    folium.GeoJson(**geojson_kwargs).add_to(fmap)
    folium.LayerControl().add_to(fmap)
    fmap.fit_bounds([[miny, minx], [maxy, maxx]])
    return fmap.get_root().render()
