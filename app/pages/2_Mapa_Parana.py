"""Mapa interativo do contorno oficial do Paraná (IBGE)."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from geoai.portal import attribution_lines, didactic_copy_text, folium_map_html
from geoai.presentation import AudienceLevel

from _bootstrap import cached_parana_layer, configure_page, render_footer, sidebar_brand

configure_page("Mapa Paraná")
sidebar_brand()

st.title("Mapa do Paraná")
st.caption(
    "Geometria real versionada em `data/derived/parana_uf_2025.geojson`. "
    "Sem camada de aptidão solar fictícia."
)

bundle = cached_parana_layer()
if not bundle.validated_for_map:
    st.error(
        bundle.missing_reason_pt
        or "Camada não validada — mapa bloqueado (fail-closed)."
    )
    st.warning(
        "A interface não apresenta geometria não verificada "
        "(SHA, CRS ou validação)."
    )
    render_footer()
    st.stop()

level_label = st.radio(
    "Nível didático",
    options=[
        (AudienceLevel.BASIC, "Básico"),
        (AudienceLevel.INTERMEDIATE, "Intermediário"),
        (AudienceLevel.TECHNICAL, "Técnico"),
    ],
    format_func=lambda item: item[1],
    horizontal=True,
    help="Altera apenas o texto didático, não a geometria.",
)
level = level_label[0]
title, description = didactic_copy_text(bundle, level)
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
    st.success("Camada validada para exibição (SHA + CRS + geometria).")

with c1:
    try:
        html = folium_map_html(
            bundle,
            fill_opacity=float(fill_opacity),
            line_weight=float(line_weight),
        )
        components.html(html, height=int(map_height), scrolling=False)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Falha ao renderizar mapa: {exc}")

st.info(
    "Controles: nível didático, estilo do contorno e altura do iframe. "
    "Não há filtro temático adicional — só a feição UF."
)
render_footer()
