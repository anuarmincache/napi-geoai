"""Camada territorial do Paraná — carregamento portável (sem Streamlit).

Fail-closed: a camada só fica ``available=True`` quando integridade SHA,
geometria legível e CRS verificável estão ok. Sem isso a UI não deve
apresentar o mapa como validado.
"""

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
from geoai.quality import is_sha256_hex, verify_content_sha256

EXPECTED_SOURCE_CRS = "EPSG:4674"


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
        if self.gdf.crs is None:
            return None
        try:
            code = self.gdf.crs.to_epsg()
        except Exception:  # noqa: BLE001
            return str(self.gdf.crs)
        return f"EPSG:{code}" if code else str(self.gdf.crs)

    @property
    def validated_for_map(self) -> bool:
        """Alias explícito: só True quando a UI pode exibir o mapa."""

        return self.available


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _empty_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[], crs=None)


def _reject(
    *,
    geo_path: Path,
    root: Path,
    reason: str,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    content_sha256_ok: bool | None = None,
    gdf: gpd.GeoDataFrame | None = None,
) -> ParanaLayerBundle:
    return ParanaLayerBundle(
        gdf=gdf if gdf is not None else _empty_gdf(),
        provenance=dict(provenance or {}),
        validation=dict(validation or {}),
        didactic=didactic_metadata_for_territorial_pr(repo_root=root),
        geojson_path=geo_path,
        available=False,
        missing_reason_pt=reason,
        content_sha256_ok=content_sha256_ok,
    )


def _normalize_crs_code(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace(" ", "")
    if not text:
        return None
    if text.isdigit():
        return f"EPSG:{text}"
    if text.startswith("EPSG:"):
        return text
    return text


def _resolve_crs(
    gdf: gpd.GeoDataFrame,
    validation: dict[str, Any],
) -> tuple[gpd.GeoDataFrame | None, str | None]:
    """Resolve CRS sem inventar. Retorna (gdf, erro)."""

    declared = _normalize_crs_code(validation.get("source_crs"))
    current = None
    if gdf.crs is not None:
        try:
            epsg = gdf.crs.to_epsg()
            current = f"EPSG:{epsg}" if epsg else _normalize_crs_code(gdf.crs)
        except Exception:  # noqa: BLE001
            current = _normalize_crs_code(gdf.crs)

    if current is None:
        if declared == EXPECTED_SOURCE_CRS:
            # Evidência externa verificável (arquivo de validação MVP 02).
            return gdf.set_crs(EXPECTED_SOURCE_CRS), None
        return None, (
            "GeoJSON sem CRS e sem source_crs verificável na validação; "
            "não atribuir EPSG:4674 silenciosamente."
        )

    if declared and current != declared:
        return None, (
            f"CRS do GeoJSON ({current}) diverge de source_crs da validação "
            f"({declared})."
        )

    if current != EXPECTED_SOURCE_CRS:
        return None, (
            f"CRS incompatível para o piloto PR: {current} "
            f"(esperado {EXPECTED_SOURCE_CRS})."
        )
    return gdf, None


def load_parana_layer(repo_root: Path | None = None) -> ParanaLayerBundle:
    """Carrega GeoJSON + metadados; fail-closed para exibição no mapa."""

    root = repo_root or repo_root_from_here()
    geo_path = parana_geojson_path(root)
    prov_path = parana_provenance_path(root)
    val_path = parana_validation_path(root)

    if not geo_path.is_file():
        return _reject(
            geo_path=geo_path,
            root=root,
            reason=(
                f"Artefato ausente: {geo_path.as_posix()}. "
                "Incorpore o GeoJSON derivado do IBGE sem inventar geometria."
            ),
        )

    provenance = _read_json(prov_path) if prov_path.is_file() else {}
    validation = _read_json(val_path) if val_path.is_file() else {}

    try:
        gdf = gpd.read_file(geo_path)
    except Exception as exc:  # noqa: BLE001
        return _reject(
            geo_path=geo_path,
            root=root,
            reason=f"GeoJSON inválido ou ilegível: {exc}",
            provenance=provenance,
            validation=validation,
        )

    if gdf.empty or gdf.geometry.isna().all():
        return _reject(
            geo_path=geo_path,
            root=root,
            reason="GeoJSON sem geometrias utilizáveis.",
            provenance=provenance,
            validation=validation,
            gdf=gdf,
        )

    gdf_crs, crs_err = _resolve_crs(gdf, validation)
    if crs_err is not None:
        return _reject(
            geo_path=geo_path,
            root=root,
            reason=crs_err,
            provenance=provenance,
            validation=validation,
            gdf=gdf,
        )
    assert gdf_crs is not None
    gdf = gdf_crs

    geom_ok = validation.get("validation", {}).get("all_valid")
    if geom_ok is False:
        return _reject(
            geo_path=geo_path,
            root=root,
            reason=(
                "Arquivo de validação indica geometrias inválidas "
                "(all_valid=false)."
            ),
            provenance=provenance,
            validation=validation,
            gdf=gdf,
        )

    derived_sha = provenance.get("derived_geojson_sha256")
    if not isinstance(derived_sha, str) or not is_sha256_hex(derived_sha):
        return _reject(
            geo_path=geo_path,
            root=root,
            reason=(
                "Proveniência sem derived_geojson_sha256 (64 hex); "
                "camada não pode ser apresentada como validada."
            ),
            provenance=provenance,
            validation=validation,
            gdf=gdf,
            content_sha256_ok=None,
        )

    sha_ok = verify_content_sha256(derived_sha, geo_path.read_bytes())
    if not sha_ok:
        return _reject(
            geo_path=geo_path,
            root=root,
            reason=(
                "SHA-256 do GeoJSON diverge da proveniência "
                "(derived_geojson_sha256). Mapa bloqueado."
            ),
            provenance=provenance,
            validation=validation,
            gdf=gdf,
            content_sha256_ok=False,
        )

    didactic = didactic_metadata_for_territorial_pr(repo_root=root)
    return ParanaLayerBundle(
        gdf=gdf,
        provenance=provenance,
        validation=validation,
        didactic=didactic,
        geojson_path=geo_path,
        available=True,
        missing_reason_pt=None,
        content_sha256_ok=True,
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
    else:
        lines.append("Edição: indisponível na proveniência")
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
    """Integridade/proveniência dos artefatos — sem inventar coleta ou atributos.

    Não monta registro tabular fictício nem data de recuperação presumida.
    """

    retrieved_at = bundle.provenance.get("retrieved_at")
    edition = bundle.provenance.get("edition")
    zip_sha = bundle.provenance.get("content_sha256")
    derived_sha = bundle.provenance.get("derived_geojson_sha256")
    missing: list[str] = []
    if not retrieved_at:
        missing.append("retrieved_at")
    if not edition:
        missing.append("edition")
    if not isinstance(zip_sha, str) or not is_sha256_hex(str(zip_sha)):
        missing.append("content_sha256")
    if not isinstance(derived_sha, str) or not is_sha256_hex(str(derived_sha)):
        missing.append("derived_geojson_sha256")

    geom_flag = bundle.validation.get("validation", {}).get("all_valid")
    if not bundle.available:
        return {
            "status": "undetermined"
            if bundle.content_sha256_ok is not False
            else "rejected",
            "determined": False,
            "layer_validated_for_display": False,
            "message": bundle.missing_reason_pt,
            "retrieved_at": retrieved_at if retrieved_at else None,
            "edition": edition if edition else None,
            "missing_provenance_fields": missing,
            "content_sha256_ok": bundle.content_sha256_ok,
            "validation_all_valid": geom_flag,
            "note": (
                "Sem simulação de registro tabular nem data de coleta inventada."
            ),
        }

    determined = (
        bundle.content_sha256_ok is True
        and not missing
        and geom_flag is True
    )
    return {
        "status": "valid" if determined else "undetermined",
        "determined": determined,
        "layer_validated_for_display": True,
        "retrieved_at": retrieved_at,
        "edition": edition,
        "missing_provenance_fields": missing,
        "content_sha256_ok": bundle.content_sha256_ok,
        "validation_all_valid": geom_flag,
        "source_crs": bundle.validation.get("source_crs") or bundle.crs_epsg,
        "note": (
            "Status baseado só em artefatos/proveniência reais; "
            "não há atributos municipais inventados neste snapshot."
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
        raise FileNotFoundError(
            bundle.missing_reason_pt or "camada não validada para exibição"
        )

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
