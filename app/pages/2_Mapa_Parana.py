"""Mapa interativo do contorno oficial do Paraná (IBGE)."""

from __future__ import annotations

import streamlit as st
from geoai.portal import attribution_lines, didactic_copy_text, folium_map_html
from geoai.presentation import AudienceLevel

from _bootstrap import (
    cached_parana_layer,
    configure_page,
    page_header,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Mapa Paraná")
sidebar_brand()

page_header(
    "Mapa do Paraná",
    "Contorno oficial do estado, segundo o IBGE.",
    art_kind="map",
    eyebrow="Território",
)
st.caption(
    "Limite estadual oficial do IBGE (malha 2025). Não há camada de aptidão "
    "solar nesta versão."
)

bundle = cached_parana_layer()
if not bundle.validated_for_map:
    st.error(
        bundle.missing_reason_pt
        or "O contorno não passou na validação e não será exibido."
    )
    st.warning(
        "O portal só mostra mapas cujo arquivo foi conferido contra a "
        "fonte oficial."
    )
    render_footer()
    st.stop()

level = st.radio(
    "Nível didático",
    options=[
        AudienceLevel.BASIC,
        AudienceLevel.INTERMEDIATE,
        AudienceLevel.TECHNICAL,
    ],
    format_func={
        AudienceLevel.BASIC: "Básico",
        AudienceLevel.INTERMEDIATE: "Intermediário",
        AudienceLevel.TECHNICAL: "Técnico",
    }.__getitem__,
    horizontal=True,
    help="Altera apenas o texto didático, não a geometria.",
)
title, description = didactic_copy_text(bundle, level)
if title.strip().casefold() != "mapa do paraná":
    st.subheader(title)
st.write(description)

c1, c2 = st.columns([2, 1])
with c2:
    fill_opacity = st.slider(
        "Opacidade do preenchimento",
        0.05,
        0.85,
        0.35,
        0.05,
        help="Contraste visual do polígono sobre o mapa-base OSM.",
    )
    line_weight = st.slider(
        "Espessura do contorno",
        1.0,
        5.0,
        2.0,
        0.5,
    )
    map_height = st.select_slider(
        "Altura do mapa (px)",
        options=[360, 420, 480, 560, 640],
        value=560,
        help="Ajuste para notebooks ou telas estreitas.",
    )
    st.markdown("#### Metadados")
    for line in attribution_lines(bundle):
        st.markdown(f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True)
    crs_src = bundle.validation.get("source_crs") or bundle.crs_epsg
    map_crs = bundle.validation.get("recommended_map_crs")
    st.markdown(
        f'<p class="napi-meta">CRS da fonte: {crs_src}</p>',
        unsafe_allow_html=True,
    )
    if map_crs:
        st.markdown(
            f'<p class="napi-meta">CRS sugerido p/ mapa métrico: {map_crs}</p>',
            unsafe_allow_html=True,
        )
    lim = bundle.validation.get("map_crs_limitation")
    if lim:
        st.caption(lim)
    st.success("Contorno conferido contra o arquivo oficial do IBGE.")

with c1:
    try:
        html = folium_map_html(
            bundle,
            fill_opacity=float(fill_opacity),
            line_weight=float(line_weight),
        )
        render_html_map(html, height=int(map_height))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Falha ao renderizar mapa: {exc}")

st.info(
    "Controles: nível didático, estilo do contorno e altura do iframe. "
    "Não há filtro temático adicional — só a feição UF."
)
render_footer()
