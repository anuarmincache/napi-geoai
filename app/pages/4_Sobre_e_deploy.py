"""Sobre a arquitetura da UI e prontidão de deploy (sem publicar)."""

from __future__ import annotations

import streamlit as st
from geoai.portal import demo_connection_policy, future_supabase_policy_stub

from _bootstrap import configure_page, sidebar_brand

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

st.subheader("Como publicar depois (Streamlit Community Cloud)")
st.markdown(
    """
1. Conectar o repositório GitHub à conta Streamlit Cloud do responsável.
2. **Main file path / entry point:** `app/Home.py` (obrigatório).
3. Python 3.12; `requirements-streamlit.txt` ou `pip install -e ".[ui]"`.
4. A Cloud **não** alcança Postgres WSL `:5433` — use só artefatos em
   `data/derived` (ou backend remoto futuro autorizado).
5. Não definir `DATABASE_URL` local na Cloud.
6. Segredos só no painel Streamlit — nunca no Git / CI.
7. Supabase: não criar projeto nesta etapa.
8. Esta página **não** dispara deploy automático.
"""
)

st.warning(
    "PostgreSQL/PostGIS local na porta 5433 permanece intacto e fora da Internet."
)
