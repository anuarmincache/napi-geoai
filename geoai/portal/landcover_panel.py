"""Serviço de apresentação: cobertura e uso da terra (MapBiomas Coleção 11)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.landcover.mapbiomas_col11 import CONTENT_SHA256
from geoai.portal.municipal_explorer import MunicipalityLayerBundle
from geoai.portal.paths import (
    landcover_panel_path,
    landcover_provenance_path,
    landcover_quality_path,
    repo_root_from_here,
)

__all__ = [
    "LandcoverBundle",
    "landcover_attribution_lines",
    "landcover_change",
    "landcover_composition",
    "landcover_map_html",
    "landcover_ranked",
    "landcover_share",
    "load_landcover_bundle",
]


@dataclass(frozen=True, slots=True)
class LandcoverBundle:
    available: bool
    panel: dict[str, Any]
    provenance: dict[str, Any]
    quality: dict[str, Any]
    missing_reason_pt: str | None = None


def _fail(reason: str) -> LandcoverBundle:
    return LandcoverBundle(False, {}, {}, {}, reason)


def load_landcover_bundle(repo_root: Path | None = None) -> LandcoverBundle:
    root = Path(repo_root) if repo_root is not None else repo_root_from_here()
    paths = (
        landcover_panel_path(root),
        landcover_provenance_path(root),
        landcover_quality_path(root),
    )
    if not all(p.is_file() for p in paths):
        return _fail(
            "Artefatos MapBiomas ausentes. Gere com "
            "scripts/prepare_mapbiomas_parana.py (sem download no Streamlit)."
        )
    try:
        panel, provenance, quality = (
            json.loads(p.read_text(encoding="utf-8")) for p in paths
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _fail(f"Artefato MapBiomas ilegível/corrompido: {exc}")
    if panel.get("schema_version") != 1 or panel.get("collection") != 11:
        return _fail("Painel MapBiomas de versão ou coleção desconhecida.")
    if len(panel.get("municipalities") or {}) != EXPECTED_PR_MUNICIPALITY_COUNT:
        return _fail("Painel MapBiomas sem os 399 municípios.")
    if not quality.get("reconcile_ok"):
        return _fail("quality.reconcile_ok ≠ true — painel rejeitado.")
    if provenance.get("content_sha256") != CONTENT_SHA256:
        return _fail("SHA-256 da proveniência difere do contrato da Coleção 11.")
    return LandcoverBundle(True, panel, provenance, quality, None)


def _slot(bundle: LandcoverBundle, code: str | None, year: int) -> dict[str, float]:
    if code is None:
        return dict(bundle.panel["totals_ha"].get(str(year)) or {})
    row = bundle.panel["municipalities"].get(str(code)) or {}
    return dict((row.get("groups_ha") or {}).get(str(year)) or {})


def landcover_composition(
    bundle: LandcoverBundle, code: str | None, year: int
) -> list[dict[str, Any]]:
    """Grupos com hectares e percentual da área mapeada. ``code`` None = PR."""

    slot = _slot(bundle, code, year)
    total = sum(slot.values())
    rows = []
    for group in bundle.panel["groups"]:
        hectares = float(slot.get(group["key"], 0.0))
        rows.append(
            {
                "key": group["key"],
                "label_pt": group["label_pt"],
                "color": group["color"],
                "hectares": hectares,
                "percent": (100.0 * hectares / total) if total > 0 else None,
            }
        )
    return rows


def landcover_share(
    bundle: LandcoverBundle, code: str | None, group: str, year: int
) -> float | None:
    slot = _slot(bundle, code, year)
    total = sum(slot.values())
    if total <= 0:
        return None
    return 100.0 * float(slot.get(group, 0.0)) / total


def landcover_change(
    bundle: LandcoverBundle, code: str | None, year_a: int, year_b: int
) -> list[dict[str, Any]]:
    """Diferença de estoque entre dois anos do painel. Não é desmatamento."""

    a = {r["key"]: r for r in landcover_composition(bundle, code, year_a)}
    rows = []
    for item in landcover_composition(bundle, code, year_b):
        before = a[item["key"]]
        rows.append(
            {
                "label_pt": item["label_pt"],
                "hectares_a": before["hectares"],
                "hectares_b": item["hectares"],
                "delta_ha": item["hectares"] - before["hectares"],
                "delta_pp": (
                    item["percent"] - before["percent"]
                    if item["percent"] is not None and before["percent"] is not None
                    else None
                ),
            }
        )
    return rows


def landcover_ranked(
    bundle: LandcoverBundle,
    group: str,
    year: int,
    names: dict[str, str],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = []
    for code in bundle.panel["municipalities"]:
        share = landcover_share(bundle, code, group, year)
        if share is not None:
            rows.append(
                {"CD_MUN": code, "NM_MUN": names.get(code, code), "percent": share}
            )
    rows.sort(key=lambda r: (-r["percent"], r["CD_MUN"]))
    return rows[: max(0, limit)]


def _pct(value: object) -> str:
    return f"{100 * float(value or 0):.2f}%".replace(".", ",")


def landcover_attribution_lines(bundle: LandcoverBundle) -> tuple[str, ...]:
    if not bundle.available:
        return ()
    prov, quality = bundle.provenance, bundle.quality
    delta = quality.get("area_delta_vs_ibge") or {}
    return (
        str(prov.get("citation_pt") or ""),
        f"{prov.get('product')}. {prov.get('release')}. Sensor "
        f"{prov.get('sensor')}, {prov.get('resolution_m')} m, hectares.",
        f"Arquivo {prov.get('file_name')}, SHA-256 "
        f"{str(prov.get('content_sha256'))[:16]}…, aba {prov.get('sheet')}, "
        f"{quality.get('rows_parana')} linhas do Paraná.",
        "Diferença entre área mapeada e área IBGE: mediana "
        f"{_pct(delta.get('median_abs'))}, máxima {_pct(delta.get('max_abs'))}, "
        f"{delta.get('municipalities_above_1_percent')} municípios acima de 1%. "
        "Nenhum valor foi reescalado.",
        str(prov.get("license_note") or ""),
        str(bundle.panel.get("year_rule_pt") or ""),
    )


def landcover_map_html(
    mun_bundle: MunicipalityLayerBundle,
    bundle: LandcoverBundle,
    group: str,
    year: int,
    *,
    selected_code: str | None = None,
    fill_opacity: float = 0.72,
) -> str:
    try:
        import folium
        from branca.colormap import LinearColormap
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("folium necessário: pip install 'napi-geoai[ui]'") from exc
    if not mun_bundle.available or not bundle.available:
        raise FileNotFoundError("malha ou painel MapBiomas indisponível")
    meta = next(g for g in bundle.panel["groups"] if g["key"] == group)
    gdf = mun_bundle.gdf.to_crs(epsg=4326).copy()
    shares = [
        landcover_share(bundle, code, group, year) for code in gdf["CD_MUN"].astype(str)
    ]
    gdf["lc_value"] = [s if s is not None else 0.0 for s in shares]
    gdf["lc_has"] = [s is not None for s in shares]
    gdf["lc_text"] = [
        f"{s:.1f}%".replace(".", ",") if s is not None else "sem dado" for s in shares
    ]
    known = [s for s in shares if s is not None]
    vmax = max(known) if known else 1.0
    cmap = LinearColormap(
        colors=["#f8fafc", meta["color"]],
        vmin=0.0,
        vmax=vmax if vmax > 0 else 1.0,
        caption=f"{meta['label_pt']}: % da área mapeada do município, {year}",
    )
    minx, miny, maxx, maxy = gdf.total_bounds
    fmap = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        base = {
            "fillColor": cmap(float(props.get("lc_value") or 0.0))
            if props.get("lc_has")
            else "#cbd5e1",
            "color": "#475569",
            "weight": 0.5,
            "fillOpacity": fill_opacity if props.get("lc_has") else 0.3,
        }
        if selected_code and str(props.get("CD_MUN")) == str(selected_code):
            base.update({"color": "#0ea5e9", "weight": 2.8})
        return base

    folium.GeoJson(
        data=json.loads(gdf.to_json()),
        name=meta["label_pt"],
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["NM_MUN", "CD_MUN", "lc_text"],
            aliases=["Município", "Código IBGE", f"{meta['label_pt']} ({year})"],
        ),
    ).add_to(fmap)
    cmap.add_to(fmap)
    bounds = [[miny, minx], [maxy, maxx]]
    if selected_code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(selected_code)]
        if not hit.empty:
            b = hit.total_bounds
            bounds = [[b[1], b[0]], [b[3], b[2]]]
    fmap.fit_bounds(bounds, padding=(20, 20))
    return fmap.get_root().render()
