"""Catálogo de fontes e snapshot de qualidade (contratos existentes)."""

from __future__ import annotations

import streamlit as st
from geoai.connectors.catalog import list_sources
from geoai.portal import quality_snapshot_for_demo

from _bootstrap import cached_parana_layer, configure_page, render_footer, sidebar_brand

configure_page("Fontes e qualidade")
sidebar_brand()

st.title("Fontes oficiais e qualidade")
st.caption(
    "Catálogo MVP 03 (`geoai.connectors.catalog`) + snapshot tabular MVP 06. "
    "Sem novos downloads neste rerun."
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
st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader("Qualidade — piloto territorial PR")
bundle = cached_parana_layer()
snap = quality_snapshot_for_demo(bundle)
st.json(snap)
st.markdown(
    """
**Escopo:** `validate_tabular_record` avalia atributos do registro, não a
geometria PostGIS. A validação geométrica já está no artefato
`parana_uf_2025.validation.json` (MVP 02). Metadados ausentes aparecem como
qualidade **não determinada** — a UI não inventa datas nem atributos.
"""
)
render_footer()
