"""Navegação didática dos quatro domínios temáticos."""

from __future__ import annotations

import streamlit as st

from _bootstrap import (
    cached_domain_cards,
    configure_page,
    render_status_badge,
    sidebar_brand,
)

configure_page("Domínios")
sidebar_brand()

st.title("Domínios temáticos")
st.caption(
    "Textos e disponibilidade vêm de `geoai.domains` — a UI não duplica "
    "a lógica de negócio."
)

cards = cached_domain_cards()
labels = {c.spec.title_pt: c for c in cards}
choice = st.selectbox("Domínio", list(labels.keys()))
card = labels[choice]

st.markdown(
    f"### {card.spec.title_pt} {render_status_badge(card.availability.status)}",
    unsafe_allow_html=True,
)
st.write(card.spec.summary_pt)
st.write(f"**Título (EN):** {card.spec.title_en}")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Disponível agora")
    for item in card.availability.available_now_pt:
        st.markdown(f"- {item}")
    st.markdown("#### Infra compartilhada")
    for item in card.spec.shared_infrastructure:
        st.markdown(f"- `{item}`")
with c2:
    st.markdown("#### Planejado / fora de escopo agora")
    for item in card.availability.planned_pt:
        st.markdown(f"- {item}")
    for item in card.spec.out_of_scope_now:
        st.markdown(f"- _{item}_")

st.markdown("#### Indicadores (contratos — não calculados)")
if not card.indicators:
    st.warning("Nenhum IndicatorSpec cadastrado para este domínio ainda.")
else:
    for ind in card.indicators:
        with st.expander(ind.indicator_id):
            st.markdown(f"**Pergunta:** {ind.question_pt}")
            st.markdown(f"**Público:** {ind.audience_pt}")
            st.markdown(f"**Cobertura:** {ind.coverage_pt}")
            if ind.source_ids:
                fontes = ", ".join(f"`{s}`" for s in ind.source_ids)
                st.markdown(f"**Fontes:** {fontes}")
            st.markdown("**Limitações:**")
            for lim in ind.limitations_pt:
                st.markdown(f"- {lim}")
