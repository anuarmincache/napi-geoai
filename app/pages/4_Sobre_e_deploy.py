"""Sobre a arquitetura da UI e prontidão de deploy (sem publicar)."""

from __future__ import annotations

import streamlit as st

from _bootstrap import (
    configure_page,
    page_header,
    page_link,
    render_footer,
    sidebar_brand,
)

configure_page("Sobre o projeto")
sidebar_brand()

page_header(
    "Sobre o projeto",
    "O que é o NAPI GeoAI, quem faz e como a plataforma é construída.",
    art_kind="docs",
    eyebrow="Transparência",
    banner="banner-sobre.webp",
    banner_alt="Notebook em um mirante, com o mapa do Paraná em destaque",
    chips=(
        "Objetivos",
        "Quem faz",
        "Dados e tecnologias",
        "Como é construída",
    ),
)
st.markdown(
    """
### O que é

O **NAPI GeoAI** reúne dados públicos que normalmente ficam espalhados em
vários órgãos e os apresenta por município: território, população, energia,
agropecuária e cobertura da terra. A ideia é ajudar pesquisadores,
empreendedores, cooperativas e gestores públicos a conhecer o território do
Paraná e a escolher o que merece um estudo mais profundo.

### O que a plataforma não faz

Ela não declara viabilidade econômica, não recomenda onde investir e não
substitui projeto, licenciamento ou parecer técnico. Os indicadores servem
para priorizar investigações.

### Como tratamos os dados

- Só dados de fontes oficiais, com a fonte e a data ao lado de cada número.
- Quando um dado não existe, a página diz que não existe. Nada é preenchido.
- Cada número é classificado: dado oficial, indicador calculado ou simulação.
- Os dados são retratos datados, não tempo real.
"""
)

c1, c2 = st.columns(2)
with c1.container(border=True):
    st.markdown("##### Quem faz")
    st.markdown(
        "Iniciativa de pesquisa e desenvolvimento no contexto do **NAPI "
        "Energia Zero-Carbono**, com a Universidade Estadual de Maringá (UEM) "
        "e a Fundação Araucária."
    )
    st.caption("Idealização e liderança técnica: Anuar José Mincache.")
with c2.container(border=True):
    st.markdown("##### Código aberto")
    st.markdown(
        "O código, os testes e a documentação de cada etapa estão em "
        "[github.com/anuarmincache/napi-geoai]"
        "(https://github.com/anuarmincache/napi-geoai)."
    )
    page_link("pages/1_Dominios.py", "Domínios e roteiro", "🧩")
    page_link("pages/2_Mapa_Parana.py", "Mapa do Paraná", "🗺️")

with st.expander("Detalhes técnicos: arquitetura e publicação"):
    st.markdown(
        """
    ### Separação interface / motor

    | Camada | Pacote | Papel |
    |---|---|---|
    | Motor científico | `geoai.*` | conectores, qualidade, domínios, PostGIS |
    | Serviços de portal | `geoai.portal` | artefatos/visões sem Streamlit |
    | UI | `app/` | Streamlit apenas |

    Migração futura para site próprio / FastAPI deve reutilizar `geoai.portal`
    sem reescrever contratos.
    """
    )

    st.markdown(
        """
    O portal lê apenas arquivos de dados já preparados e conferidos. Ele não
    baixa nada durante a navegação e não depende de banco de dados.

    O processo de publicação está descrito na documentação do repositório.
    """
    )

render_footer()
