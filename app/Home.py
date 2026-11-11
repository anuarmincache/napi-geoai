"""Entrada Streamlit — NAPI GeoAI (MVP 07)."""

from __future__ import annotations

import streamlit as st

from _bootstrap import (
    cached_domain_cards,
    cached_parana_layer,
    configure_page,
    render_status_badge,
    sidebar_brand,
)

configure_page("Início")
sidebar_brand()

st.markdown(
    """
<div class="napi-hero">
  <h1 style="margin:0 0 0.35rem 0;">NAPI GeoAI</h1>
  <p style="margin:0; color:#334155; font-size:1.05rem;">
    Plataforma de inteligência geoespacial para planejamento energético e
    empreendedorismo sustentável — demonstração didática com dados oficiais.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
Esta interface **reutiliza** os contratos e artefatos dos MVPs 01–06.
Não calcula aptidão solar, não inventa indicadores e **não** publica
dados no Supabase neste MVP.
"""
)

bundle = cached_parana_layer()
col_a, col_b, col_c = st.columns(3)
col_a.metric(
    "Camada PR (IBGE)",
    "disponível" if bundle.available else "ausente",
)
col_b.metric("Feições no mapa", bundle.feature_count)
col_c.metric(
    "SHA GeoJSON",
    "ok"
    if bundle.content_sha256_ok
    else ("pendente" if bundle.content_sha256_ok is None else "divergente"),
)

st.subheader("Quatro domínios")
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
        with st.expander("O que já existe / o que é planejado"):
            st.markdown("**Disponível agora**")
            for item in card.availability.available_now_pt:
                st.markdown(f"- {item}")
            st.markdown("**Planejado**")
            for item in card.availability.planned_pt:
                st.markdown(f"- {item}")

st.info(
    "Use o menu lateral: **Domínios**, **Mapa Paraná**, "
    "**Fontes e qualidade**, **Sobre e deploy**."
)
