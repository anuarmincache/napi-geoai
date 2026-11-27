"""Catálogo de fontes e retrato de qualidade dos dados preparados."""

from __future__ import annotations

import streamlit as st
from geoai.connectors.catalog import list_sources
from geoai.portal.formatos import modo_de_acesso, situacao_da_fonte
from geoai.portal.relatorios import relatorios_tecnicos

from _bootstrap import (
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
    banner_alt=(
        "Logos de IBGE, ANEEL, INPE, MapBiomas, ONS e Governo do Paraná sobre "
        "um notebook com o painel do projeto"
    ),
    # Os logos ficam à esquerda da arte: sem isso o recorte da tela estreita
    # corta justamente as instituições que fornecem o dado.
    banner_pos="center left",
    # As três primeiras alimentam o site hoje. INPE e ONS estão catalogadas e
    # ainda não foram coletadas, e a tabela desta página diz isso em detalhe.
    chips=(
        "IBGE",
        "ANEEL",
        "MapBiomas",
        "INPE (previsto)",
        "ONS (previsto)",
    ),
)
st.caption(
    "Catálogo das fontes oficiais usadas ou previstas, com licença, "
    "periodicidade e situação de cada uma. As fontes são conferidas na "
    "preparação dos dados, não a cada visita. Em uso no site significa que a "
    "fonte alimenta alguma página hoje; catalogada significa que ela está "
    "prevista e ainda não foi coletada."
)

sources = list_sources()
rows = [
    {
        "Organização": s.organization,
        "Produto": s.product,
        "Situação": situacao_da_fonte(s.status.value),
        "Como é obtida": modo_de_acesso(s.access_mode.value),
        "Cobertura": s.spatial_coverage,
    }
    for s in sources
]
st.dataframe(rows, width="stretch", hide_index=True)

st.markdown("### Relatórios técnicos")
st.caption(
    "As duas verificações que sustentam os números das outras páginas. O "
    "arquivo original de cada uma fica disponível para quem quiser conferir "
    "fora daqui."
)

for relatorio in relatorios_tecnicos():
    with st.expander(relatorio.titulo):
        st.write(relatorio.resumo)
        st.dataframe(
            [
                {"O que foi verificado": rotulo, "Resultado": valor}
                for rotulo, valor in relatorio.linhas
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            f"Gerado em {relatorio.gerado_em} com {relatorio.motor}. As versões "
            "ficam registradas porque mudança de biblioteca pode alterar "
            "resultado de reprojeção."
        )
        if relatorio.arquivo is not None and relatorio.arquivo.exists():
            st.download_button(
                "Baixar o relatório completo",
                data=relatorio.arquivo.read_bytes(),
                file_name=relatorio.nome_do_arquivo,
                mime="application/json",
                key=f"baixar-{relatorio.nome_do_arquivo}",
            )

render_footer()
