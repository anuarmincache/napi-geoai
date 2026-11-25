"""Catálogo de fontes e retrato de qualidade dos dados preparados."""

from __future__ import annotations

import streamlit as st
from geoai.connectors.catalog import list_sources
from geoai.portal import quality_snapshot_for_demo

from _bootstrap import (
    cached_parana_layer,
    configure_page,
    page_header,
    render_footer,
    sidebar_brand,
)

configure_page("Fontes e qualidade")
sidebar_brand()

page_header(
    "Fontes e qualidade dos dados",
    "De onde vem cada dado, quando foi coletado e como foi conferido.",
    art_kind="docs",
    eyebrow="Transparência",
    banner="banner-fontes.webp",
    banner_alt="Notebook mostrando o painel do projeto com o mapa do Paraná",
    chips=(
        "Fontes oficiais",
        "Data da coleta",
        "Licença",
        "Impressão digital",
    ),
)
st.caption(
    "Catálogo das fontes oficiais usadas ou previstas, com licença, "
    "periodicidade e situação de cada uma. As fontes são conferidas na "
    "preparação dos dados, não a cada visita."
)

sources = list_sources()
rows = [
    {
        "source_id": s.source_id,
        "organização": s.organization,
        "produto": s.product,
        "status": s.status.value,
        "modo": s.access_mode.value,
        "cobertura": s.spatial_coverage,
    }
    for s in sources
]
st.dataframe(rows, width="stretch", hide_index=True)

with st.expander("Detalhes técnicos: verificação de qualidade do contorno estadual"):
    bundle = cached_parana_layer()
    snap = quality_snapshot_for_demo(bundle)
    st.json(snap)
    st.markdown(
        """
    **O que esta checagem cobre:** ela avalia os atributos de cada registro, não a
    geometria PostGIS. A validação geométrica já está no artefato
    `parana_uf_2025.validation.json` (MVP 02). Metadados ausentes aparecem como
    qualidade **não determinada** — a UI não inventa datas nem atributos.
    """
    )

render_footer()
