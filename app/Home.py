"""Entrada Streamlit — NAPI GeoAI (MVP 08)."""

from __future__ import annotations

import streamlit as st

from _bootstrap import (
    cached_domain_cards,
    cached_parana_layer,
    configure_page,
    render_footer,
    render_status_badge,
    sidebar_brand,
)

configure_page("Início")
sidebar_brand()

st.markdown(
    """
<div class="napi-hero" role="banner">
  <h1 style="margin:0 0 0.4rem 0;">NAPI GeoAI</h1>
  <p>
    Plataforma de inteligência geoespacial para planejamento energético e
    empreendedorismo sustentável — demonstração institucional com dados
    oficiais versionados.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
Esta interface **reutiliza** contratos e artefatos dos MVPs 01–07 via
`geoai.portal`. Não calcula aptidão solar, não inventa indicadores e **não**
conecta Supabase nesta etapa. Pronta para revisão visual antes de qualquer
publicação no Streamlit Community Cloud.
"""
)

bundle = cached_parana_layer()
col_a, col_b, col_c = st.columns(3)
col_a.metric(
    "Camada PR (IBGE)",
    "disponível" if bundle.available else "ausente",
    help="Artefato versionado em data/derived — fail-closed se inválido.",
)
col_b.metric(
    "Feições no mapa",
    bundle.feature_count,
    help="Contagem apenas se a camada passou na validação.",
)
col_c.metric(
    "SHA GeoJSON",
    "ok"
    if bundle.content_sha256_ok
    else ("pendente" if bundle.content_sha256_ok is None else "divergente"),
    help="Integridade do arquivo derivado frente ao checksum registrado.",
)

st.subheader("Quatro domínios")
st.caption(
    "Status disponível / parcial / planejado vem dos contratos — "
    "a UI não redefine regras de negócio."
)
cards = cached_domain_cards()
cols = st.columns(2)
for idx, card in enumerate(cards):
    with cols[idx % 2]:
        st.markdown(
            f"#### {card.spec.title_pt} "
            f"{render_status_badge(card.availability.status)}",
            unsafe_allow_html=True,
        )
        st.write(card.spec.summary_pt)
        with st.expander("O que já existe / o que é planejado", expanded=False):
            st.markdown("**Disponível agora**")
            for item in card.availability.available_now_pt:
                st.markdown(f"- {item}")
            st.markdown("**Planejado**")
            for item in card.availability.planned_pt:
                st.markdown(f"- {item}")

st.info(
    "Navegação: **Domínios**, **Mapa Paraná**, **Explorador territorial**, "
    "**Fontes e qualidade**, **Sobre e deploy**. Em telas estreitas, abra o "
    "menu lateral (☰)."
)
render_footer()
