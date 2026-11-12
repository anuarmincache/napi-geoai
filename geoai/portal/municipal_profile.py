"""Ficha municipal demográfica/energética (serviços portáveis)."""

from __future__ import annotations

import json
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.population.panel import (
    PopulationPanelBundle,
    load_population_panel_bundle,
)
from geoai.portal.municipal_explorer import MunicipalityLayerBundle

__all__ = [
    "PopulationPanelBundle",
    "compare_municipal_profiles",
    "load_population_panel_bundle",
    "population_attribution_lines",
    "population_map_html",
    "profile_for_code",
]


def population_attribution_lines(bundle: PopulationPanelBundle) -> tuple[str, ...]:
    prov = bundle.provenance
    qual = bundle.quality
    lines = [
        "Fonte demográfica: IBGE — Estimativas da população residente",
        f"Referência: {prov.get('reference_date') or '2026-07-01'} "
        f"(não é Censo Demográfico)",
        f"Edição: {prov.get('edition_id') or qual.get('edition_id') or 'n/d'}",
        f"Recuperado em: {prov.get('retrieved_at') or 'indisponível'}",
        f"SHA XLSX: {(prov.get('content_sha256') or '')[:16]}…",
        f"Municípios: {bundle.panel.get('municipality_count')}/"
        f"{EXPECTED_PR_MUNICIPALITY_COUNT}",
        "Área: AREA_KM2 malha IBGE municipio_2025",
        "Energia: SIGA/ANEEL MW fiscalizada conhecida (centralizada, Operação); "
        "não MMGD; não MWh",
    ]
    if bundle.panel.get("nao_associados_limitation_pt"):
        lines.append(str(bundle.panel["nao_associados_limitation_pt"]))
    return tuple(lines)


def profile_for_code(
    bundle: PopulationPanelBundle,
    code: str,
) -> dict[str, Any] | None:
    code = str(code).strip()
    for row in bundle.panel.get("municipalities") or []:
        if str(row.get("CD_MUN")) == code:
            return dict(row)
    return None


def compare_municipal_profiles(
    bundle: PopulationPanelBundle,
    code_a: str,
    code_b: str,
) -> dict[str, Any]:
    a = profile_for_code(bundle, code_a)
    b = profile_for_code(bundle, code_b)
    if a is None or b is None:
        return {"ok": False, "message": "Código ausente no painel populacional."}

    def _delta(key: str) -> float | None:
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            return None
        try:
            return round(float(va) - float(vb), 6)
        except (TypeError, ValueError):
            return None

    return {
        "ok": True,
        "a": a,
        "b": b,
        "deltas": {
            "populacao_estimada_2026_hab": _delta("populacao_estimada_2026_hab"),
            "densidade_demografica_estimada_2026_hab_km2": _delta(
                "densidade_demografica_estimada_2026_hab_km2"
            ),
            "potencia_fiscalizada_conhecida_mw": _delta(
                "potencia_fiscalizada_conhecida_mw"
            ),
            "potencia_fiscalizada_conhecida_kw_por_habitante": _delta(
                "potencia_fiscalizada_conhecida_kw_por_habitante"
            ),
            "area_km2_ibge_2025": _delta("area_km2_ibge_2025"),
        },
        "units": {
            "populacao_estimada_2026_hab": "hab (estimativa 01/07/2026)",
            "densidade_demografica_estimada_2026_hab_km2": (
                "hab/km² (est. 2026 ÷ área 2025)"
            ),
            "potencia_fiscalizada_conhecida_mw": "MW (SIGA conhecida)",
            "potencia_fiscalizada_conhecida_kw_por_habitante": "kW/hab",
            "area_km2_ibge_2025": "km²",
        },
        "disclaimer_pt": (
            "Comparação de estimativa populacional IBGE 2026, área malha 2025 e "
            "capacidade SIGA conhecida. n/d ≠ zero. Não é Censo, MWh, MMGD "
            "nem aptidão solar."
        ),
    }


def population_choropleth_geojson(
    mun_bundle: MunicipalityLayerBundle,
    pop_bundle: PopulationPanelBundle,
    *,
    metric: str = "populacao_estimada_2026_hab",
) -> dict[str, Any]:
    if not mun_bundle.available or not pop_bundle.available:
        raise FileNotFoundError("malha ou painel populacional indisponível")
    by_code = {
        str(r["CD_MUN"]): r for r in (pop_bundle.panel.get("municipalities") or [])
    }
    gdf = mun_bundle.gdf.copy()
    values = []
    pops = []
    dens = []
    kw = []
    for _, row in gdf.iterrows():
        hit = by_code.get(str(row["CD_MUN"])) or {}
        values.append(hit.get(metric))
        pops.append(hit.get("populacao_estimada_2026_hab"))
        dens.append(hit.get("densidade_demografica_estimada_2026_hab_km2"))
        kw.append(hit.get("potencia_fiscalizada_conhecida_kw_por_habitante"))
    gdf[metric] = values
    gdf["populacao_estimada_2026_hab"] = pops
    gdf["densidade_demografica_estimada_2026_hab_km2"] = dens
    gdf["potencia_fiscalizada_conhecida_kw_por_habitante"] = kw
    return json.loads(gdf.to_crs(epsg=4326).to_json())


def population_map_html(
    mun_bundle: MunicipalityLayerBundle,
    pop_bundle: PopulationPanelBundle,
    *,
    metric: str = "populacao_estimada_2026_hab",
    selected_code: str | None = None,
    fill_opacity: float = 0.55,
) -> str:
    try:
        import folium
        from branca.colormap import LinearColormap
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("folium necessário: pip install 'napi-geoai[ui]'") from exc

    captions = {
        "populacao_estimada_2026_hab": "População estimada IBGE 2026 (hab)",
        "densidade_demografica_estimada_2026_hab_km2": (
            "Densidade estimada 2026 (hab/km²; área malha 2025)"
        ),
        "potencia_fiscalizada_conhecida_kw_por_habitante": (
            "kW/hab SIGA conhecida (centralizada; não MMGD/MWh)"
        ),
    }
    data = population_choropleth_geojson(
        mun_bundle, pop_bundle, metric=metric
    )
    values = [
        float(f["properties"].get(metric))
        for f in data.get("features") or []
        if f.get("properties", {}).get(metric) is not None
    ]
    vmin = min(values) if values else 0.0
    vmax = max(values) if values else 1.0
    if vmax <= vmin:
        vmax = vmin + 1.0
    cmap = LinearColormap(
        colors=["#f7fbff", "#6baed6", "#08306b"],
        vmin=vmin,
        vmax=vmax,
        caption=captions.get(metric, metric),
    )

    import geopandas as gpd

    gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
    minx, miny, maxx, maxy = gdf.total_bounds
    fmap = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        code = str(props.get("CD_MUN") or "")
        selected = selected_code and code == str(selected_code)
        raw = props.get(metric)
        if raw is None:
            base = {
                "fillColor": "#e2e8f0",
                "color": "#94a3b8",
                "weight": 0.6,
                "fillOpacity": 0.25,
            }
        else:
            base = {
                "fillColor": cmap(float(raw)),
                "color": "#0b2545",
                "weight": 0.7,
                "fillOpacity": fill_opacity,
            }
        if selected:
            base["color"] = "#c45c26"
            base["weight"] = 2.5
            base["fillOpacity"] = min(fill_opacity + 0.2, 0.9)
        return base

    folium.GeoJson(
        data=data,
        name=captions.get(metric, metric),
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "NM_MUN",
                "CD_MUN",
                "populacao_estimada_2026_hab",
                "densidade_demografica_estimada_2026_hab_km2",
                "potencia_fiscalizada_conhecida_kw_por_habitante",
            ],
            aliases=[
                "Município",
                "Código",
                "Pop. estimada 2026 (hab)",
                "Densidade est. (hab/km²)",
                "kW/hab SIGA",
            ],
        ),
    ).add_to(fmap)
    cmap.add_to(fmap)
    fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
    if selected_code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(selected_code)]
        if not hit.empty:
            b = hit.total_bounds
            fmap.fit_bounds([[b[1], b[0]], [b[3], b[2]]], padding=(28, 28))
    try:
        from branca.element import Element

        fmap.get_root().html.add_child(
            Element(
                "<style>html,body{margin:0;background:#e8eef5;}"
                ".leaflet-container{background:#e8eef5!important;}</style>"
            )
        )
    except Exception:  # pragma: no cover
        pass
    return fmap.get_root().render()
