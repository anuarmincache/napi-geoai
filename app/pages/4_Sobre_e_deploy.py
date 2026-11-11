"""Sobre a arquitetura da UI e prontidão de deploy (sem publicar)."""

from __future__ import annotations

import streamlit as st
from geoai.portal import demo_connection_policy, future_supabase_policy_stub

from _bootstrap import configure_page, render_footer, sidebar_brand

configure_page("Sobre e deploy")
sidebar_brand()

st.title("Arquitetura da interface e deploy")
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
4. Python **3.12**; requirements: `requirements-streamlit.txt`
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
