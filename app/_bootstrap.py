"""Bootstrap compartilhado das páginas Streamlit (somente UI)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st
from geoai.portal import (
    demo_connection_policy,
    list_domain_cards,
    load_parana_layer,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&display=swap');
html, body, [class*="css"]  {
  font-family: "Source Sans 3", "IBM Plex Sans", sans-serif;
}
.stApp {
  background: linear-gradient(180deg, #f4f7fb 0%, #e8eef5 45%, #f7f9fc 100%);
}
h1, h2, h3 {
  color: #0b2545;
  letter-spacing: -0.02em;
}
.napi-hero {
  padding: 1.25rem 1.5rem;
  border-left: 6px solid #1f4e79;
  background: rgba(255,255,255,0.72);
  border-radius: 0 12px 12px 0;
  margin-bottom: 1.25rem;
}
.napi-badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  margin-right: 0.35rem;
}
.badge-partial { background: #d9e8f7; color: #0b2545; }
.badge-planned { background: #eceff3; color: #445566; }
.badge-available { background: #d7f0e0; color: #14532d; }
.napi-meta {
  font-size: 0.92rem;
  color: #334155;
  line-height: 1.45;
}
</style>
"""


def configure_page(title: str, *, icon: str = "🗺️") -> None:
    st.set_page_config(
        page_title=f"NAPI GeoAI — {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def sidebar_brand() -> None:
    st.sidebar.markdown("### NAPI GeoAI")
    st.sidebar.caption(
        "Inteligência geoespacial para empreendedorismo sustentável. "
        "Interface demonstrativa (MVP 07) — motor científico em `geoai/`."
    )
    policy = demo_connection_policy()
    st.sidebar.info(policy.description_pt)


@lru_cache(maxsize=1)
def cached_parana_layer():
    return load_parana_layer(REPO_ROOT)


@lru_cache(maxsize=1)
def cached_domain_cards():
    return list_domain_cards()


def render_status_badge(status: str) -> str:
    from geoai.portal import status_label_pt

    css = {
        "available": "badge-available",
        "partial": "badge-partial",
        "planned": "badge-planned",
    }.get(status, "badge-planned")
    label = status_label_pt(status)
    return f'<span class="napi-badge {css}">{label}</span>'
