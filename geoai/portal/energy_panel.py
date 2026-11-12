"""Serviços do painel energético SIGA (sem Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_aggregate import (
    PHASE_OPERACAO,
    EnergyPanelBundle,
    load_energy_panel_bundle,
)
from geoai.portal.municipal_explorer import MunicipalityLayerBundle
from geoai.portal.paths import derived_dir, repo_root_from_here

__all__ = [
    "PHASE_OPERACAO",
    "EnergyPanelBundle",
    "compare_municipal_energy",
    "energy_attribution_lines",
    "energy_map_html",
    "load_energy_panel_bundle",
    "municipalities_ranked",
    "plants_table_path",
    "project_municipality_metrics",
]


def energy_attribution_lines(bundle: EnergyPanelBundle) -> tuple[str, ...]:
    prov = bundle.provenance
    qual = bundle.quality
    dat = qual.get("dat_conjunto_sample") or "n/d"
    totals = bundle.panel.get("totals") or {}
    lines = [
        "Fonte: ANEEL — SIGA (Sistema de Informações de Geração)",
        f"Licença: {prov.get('license_note') or 'ODbL (Dados Abertos ANEEL)'}",
        f"Recuperado em: {prov.get('retrieved_at') or 'indisponível'}",
        f"DatGeracaoConjuntoDados (amostra): {dat}",
        "Métrica: capacidade fiscalizada conhecida (MW) — ausente ≠ zero; "
        "não é geração em MWh.",
        "Escopo: geração centralizada SIGA; MMGD fora deste MVP.",
        f"Fase padrão: {PHASE_OPERACAO}",
        f"Referência espacial: {bundle.panel.get('spatial_reference') or 'qgis'}",
        f"Municípios no painel: {bundle.panel.get('municipality_count')} "
        f"(esperado {EXPECTED_PR_MUNICIPALITY_COUNT})",
        f"Cobertura da soma MW: {totals.get('soma_cobertura', 'n/d')}",
    ]
    if bundle.panel.get("nao_associados_limitation_pt"):
        lines.append(str(bundle.panel["nao_associados_limitation_pt"]))
    if bundle.panel.get("totals_caveat_pt"):
        lines.append(str(bundle.panel["totals_caveat_pt"]))
    if bundle.qgis_report:
        eng = bundle.qgis_report.get("engine") or {}
        lines.append(
            "Join espacial QGIS: "
            f"{eng.get('qgis_version', '?')} / GDAL {eng.get('gdal_version', '?')} "
            f"/ PROJ {eng.get('proj_version', '?')}"
        )
    recon = qual.get("spatial_reconciliation") or {}
    if recon:
        lines.append(
            "Reconciliação CodCEG→CD_MUN QGIS↔GeoPandas: "
            f"ok={recon.get('ok')} · divergências="
            f"{(recon.get('agreement') or {}).get('cd_mun_divergences')}"
        )
    return tuple(lines)


def _tipo_metrics(row: dict[str, Any], tipo: str) -> dict[str, Any] | None:
    por = row.get("por_tipo") or {}
    hit = por.get(tipo)
    if hit is None:
        return None
    if isinstance(hit, dict):
        return hit
    # legado: por_tipo era Contagem simples
    return {
        "n": int(hit),
        "potencia_fiscalizada_mw": None,
        "n_potencia_fiscalizada_ausente": 0,
    }


def project_municipality_metrics(
    row: dict[str, Any],
    *,
    tipo: str | None = None,
) -> dict[str, Any]:
    """Projeta n/MW do município no escopo total ou de uma tecnologia."""

    out = dict(row)
    if not tipo:
        out["metric_scope"] = "todas_tecnologias"
        out["display_n"] = int(row.get("n_empreendimentos") or 0)
        out["display_mw"] = float(row.get("potencia_fiscalizada_mw") or 0.0)
        out["display_ausente"] = int(row.get("n_potencia_fiscalizada_ausente") or 0)
        out["display_completa"] = bool(row.get("potencia_fiscalizada_completa", True))
        return out
    metrics = _tipo_metrics(row, tipo)
    if metrics is None:
        out["metric_scope"] = f"tipo:{tipo}"
        out["display_n"] = 0
        out["display_mw"] = 0.0
        out["display_ausente"] = 0
        out["display_completa"] = True
        out["status_dados"] = "sem_empreendimento"
        return out
    n = int(metrics.get("n") or 0)
    mw = metrics.get("potencia_fiscalizada_mw")
    aus = int(metrics.get("n_potencia_fiscalizada_ausente") or 0)
    out["metric_scope"] = f"tipo:{tipo}"
    out["display_n"] = n
    out["display_mw"] = float(mw or 0.0)
    out["display_ausente"] = aus
    out["display_completa"] = aus == 0
    out["n_empreendimentos"] = n
    out["potencia_fiscalizada_mw"] = float(mw or 0.0)
    out["n_potencia_fiscalizada_ausente"] = aus
    out["potencia_fiscalizada_completa"] = aus == 0
    if n == 0:
        out["status_dados"] = "sem_empreendimento"
    else:
        out["status_dados"] = "agregado"
    return out


def municipalities_ranked(
    bundle: EnergyPanelBundle,
    *,
    metric: str = "potencia_fiscalizada_mw",
    only_with_plants: bool = True,
    tipo: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Ranking com MW/contagens no escopo do filtro de tecnologia."""

    rows = [
        project_municipality_metrics(r, tipo=tipo)
        for r in (bundle.panel.get("municipalities") or [])
    ]
    if only_with_plants:
        rows = [r for r in rows if int(r.get("display_n") or 0) > 0]
    if metric == "potencia_fiscalizada_mw":
        rows.sort(key=lambda r: float(r.get("display_mw") or 0.0), reverse=True)
    else:
        rows.sort(key=lambda r: float(r.get(metric) or 0.0), reverse=True)
    return rows[: max(0, limit)]


def compare_municipal_energy(
    bundle: EnergyPanelBundle,
    code_a: str,
    code_b: str,
    *,
    tipo: str | None = None,
) -> dict[str, Any]:
    by_code = {
        str(r["CD_MUN"]): r for r in (bundle.panel.get("municipalities") or [])
    }
    raw_a = by_code.get(str(code_a).strip())
    raw_b = by_code.get(str(code_b).strip())
    if raw_a is None or raw_b is None:
        return {
            "ok": False,
            "message": "Código municipal ausente no painel SIGA.",
        }
    a = project_municipality_metrics(raw_a, tipo=tipo)
    b = project_municipality_metrics(raw_b, tipo=tipo)
    scope = a.get("metric_scope") or "todas_tecnologias"
    return {
        "ok": True,
        "a": a,
        "b": b,
        "metric_scope": scope,
        "delta_fiscalizada_mw_a_minus_b": round(
            float(a.get("display_mw") or 0) - float(b.get("display_mw") or 0),
            6,
        ),
        "delta_n_a_minus_b": int(a.get("display_n") or 0)
        - int(b.get("display_n") or 0),
        "disclaimer_pt": (
            "Comparação de capacidade fiscalizada SIGA conhecida (MW) e "
            f"contagem no escopo «{scope}». Não é geração MWh, MMGD "
            "nem aptidão solar. Ausência de potência ≠ zero."
        ),
    }


def energy_choropleth_geojson(
    mun_bundle: MunicipalityLayerBundle,
    energy: EnergyPanelBundle,
    *,
    metric: str = "potencia_fiscalizada_mw",
    tipo: str | None = None,
) -> dict[str, Any]:
    """GeoJSON de apresentação com propriedades energéticas (UI leve)."""

    if not mun_bundle.available or not energy.available:
        raise FileNotFoundError("malha ou painel energético indisponível")
    by_code = {
        str(r["CD_MUN"]): project_municipality_metrics(r, tipo=tipo)
        for r in (energy.panel.get("municipalities") or [])
    }
    gdf = mun_bundle.gdf.copy()
    status = []
    metric_vals = []
    n_vals = []
    scopes = []
    for _, row in gdf.iterrows():
        code = str(row["CD_MUN"])
        hit = by_code.get(code) or {}
        status.append(hit.get("status_dados") or "sem_empreendimento")
        if metric == "potencia_fiscalizada_mw":
            metric_vals.append(hit.get("display_mw"))
        else:
            metric_vals.append(hit.get(metric))
        n_vals.append(int(hit.get("display_n") or 0))
        scopes.append(hit.get("metric_scope") or "todas_tecnologias")
    gdf["status_dados"] = status
    gdf[metric] = metric_vals
    gdf["n_empreendimentos"] = n_vals
    gdf["metric_scope"] = scopes
    gdf_plot = gdf.to_crs(epsg=4326)
    return json.loads(gdf_plot.to_json())


def energy_map_html(
    mun_bundle: MunicipalityLayerBundle,
    energy: EnergyPanelBundle,
    *,
    metric: str = "potencia_fiscalizada_mw",
    selected_code: str | None = None,
    fill_opacity: float = 0.55,
    tipo: str | None = None,
) -> str:
    try:
        import folium
        from branca.colormap import LinearColormap
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("folium necessário: pip install 'napi-geoai[ui]'") from exc

    data = energy_choropleth_geojson(
        mun_bundle, energy, metric=metric, tipo=tipo
    )
    values = [
        float(f["properties"].get(metric) or 0)
        for f in data.get("features") or []
        if (f.get("properties") or {}).get("status_dados") == "agregado"
    ]
    vmax = max(values) if values else 1.0
    scope = f"tipo {tipo}" if tipo else "todas as tecnologias"
    cmap = LinearColormap(
        colors=["#f7fbff", "#6baed6", "#08306b"],
        vmin=0.0,
        vmax=vmax if vmax > 0 else 1.0,
        caption=(
            f"Capacidade fiscalizada conhecida (MW) — escopo: {scope}"
        ),
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
        status = props.get("status_dados")
        selected = selected_code and code == str(selected_code)
        if status != "agregado":
            base = {
                "fillColor": "#e2e8f0",
                "color": "#94a3b8",
                "weight": 0.6,
                "fillOpacity": 0.25,
            }
        else:
            val = float(props.get(metric) or 0.0)
            base = {
                "fillColor": cmap(val),
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
        name="Capacidade fiscalizada SIGA (MW)",
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "NM_MUN",
                "CD_MUN",
                "n_empreendimentos",
                metric,
                "status_dados",
                "metric_scope",
            ],
            aliases=[
                "Município",
                "Código",
                "Nº empreendimentos (escopo)",
                "MW fiscalizada conhecida",
                "Status dados",
                "Escopo métrica",
            ],
        ),
    ).add_to(fmap)
    cmap.add_to(fmap)
    if selected_code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(selected_code)]
        if not hit.empty:
            b = hit.total_bounds
            fmap.fit_bounds([[b[1], b[0]], [b[3], b[2]]], padding=(28, 28))
        else:
            fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
    else:
        fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
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


def plants_table_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_here()
    return derived_dir(root) / "siga_pr_operacao_plants.json"
