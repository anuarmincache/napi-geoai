"""Sobre a arquitetura da UI e prontidão de deploy (sem publicar)."""

from __future__ import annotations

import streamlit as st
from geoai.portal import demo_connection_policy, future_supabase_policy_stub

from _bootstrap import (
    configure_page,
    page_header,
    page_link,
    render_footer,
    sidebar_brand,
)

configure_page("Sobre e deploy")
sidebar_brand()

page_header(
    "Sobre o projeto",
    "O que é o NAPI GeoAI, quem faz e como a plataforma é construída.",
    art_kind="docs",
    eyebrow="Transparência",
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

    demo = demo_connection_policy()
    future = future_supabase_policy_stub()

    st.subheader("Backend da demonstração (agora)")
    st.json(demo.to_dict())

    st.subheader("Backend remoto futuro (não ativo)")
    st.json(future.to_dict())

    st.subheader("Checklist Community Cloud (manual)")
    st.markdown(
        """
    1. Conta Streamlit Cloud do **responsável**, vinculada ao GitHub.
    2. App nova → repo `anuarmincache/napi-geoai`, branch **`main`** (após merge
       aprovado) ou branch de prévia autorizada.
    3. **Main file path:** `app/Home.py`
    4. Python **3.12**; dependências auto: `app/requirements.txt` (`-e ..[ui]`).
    5. Sem `DATABASE_URL`; sem segredos no Git.
    6. Nome/URL da aplicação: **aprovar antes** de tornar pública.
    7. Rollback: redeploy do commit anterior ou pausar o app no painel.
    8. Guia completo: `docs/MVP08_DEPLOY.md`

    Esta página **não** dispara deploy. Supabase **não** é provisionado aqui.
    """
    )

    st.warning(
        "PostgreSQL/PostGIS local na porta 5433 permanece intacto e fora da Internet."
    )

render_footer()
