"""Bootstrap compartilhado das páginas Streamlit (somente UI)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from geoai.portal import (
    demo_connection_policy,
    list_domain_cards,
    load_energy_panel_bundle,
    load_municipality_layer,
    load_parana_layer,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&display=swap');

:root {
  --napi-navy: #0b2545;
  --napi-accent: #1f4e79;
  --napi-ink: #1e293b;
  --napi-muted: #475569;
  --napi-surface: rgba(255, 255, 255, 0.86);
  --napi-focus: #0ea5e9;
}

html, body, [class*="css"] {
  font-family: "Source Sans 3", "IBM Plex Sans", "Segoe UI", sans-serif;
  color: var(--napi-ink);
}

.stApp {
  background:
    radial-gradient(1200px 420px at 8% -10%, rgba(31, 78, 121, 0.10), transparent 55%),
    linear-gradient(180deg, #f4f7fb 0%, #e8eef5 42%, #f7f9fc 100%);
}

/* Foco visível — teclado / leitores */
a:focus-visible,
button:focus-visible,
[role="button"]:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible,
.stSlider:focus-within {
  outline: 3px solid var(--napi-focus) !important;
  outline-offset: 2px !important;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}

h1, h2, h3 {
  color: var(--napi-navy);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.napi-hero {
  padding: 1.35rem 1.5rem;
  border-left: 6px solid var(--napi-accent);
  background: var(--napi-surface);
  border-radius: 0 14px 14px 0;
  margin-bottom: 1.1rem;
  box-shadow: 0 1px 0 rgba(11, 37, 69, 0.06);
}

.napi-hero p {
  margin: 0;
  color: var(--napi-muted);
  font-size: 1.05rem;
  max-width: 52rem;
  line-height: 1.5;
}

.napi-badge {
  display: inline-block;
  padding: 0.18rem 0.6rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  margin-right: 0.35rem;
  border: 1px solid transparent;
}

.badge-partial {
  background: #d9e8f7;
  color: #0b2545;
  border-color: #b7d0ea;
}
.badge-planned {
  background: #eceff3;
  color: #334155;
  border-color: #d5dbe3;
}
.badge-available {
  background: #d7f0e0;
  color: #14532d;
  border-color: #b7dfc6;
}

.napi-meta {
  font-size: 0.92rem;
  color: var(--napi-muted);
  line-height: 1.45;
}

.napi-footer {
  margin-top: 2rem;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(11, 37, 69, 0.12);
  color: var(--napi-muted);
  font-size: 0.86rem;
  line-height: 1.45;
}

/* Densidade mobile */
@media (max-width: 768px) {
  .napi-hero {
    padding: 1rem 1.1rem;
  }
  .napi-hero h1 {
    font-size: 1.55rem !important;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.15rem !important;
  }
}

/* Sidebar legível */
section[data-testid="stSidebar"] {
  background: rgba(255, 255, 255, 0.92);
}
section[data-testid="stSidebar"] .napi-side-brand {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--napi-navy);
  margin: 0 0 0.25rem 0;
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
    st.sidebar.markdown(
        '<p class="napi-side-brand">NAPI GeoAI</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(
        "Inteligência geoespacial para empreendedorismo sustentável. "
        "Interface demonstrativa (MVP 08) — motor científico em `geoai/`, "
        "serviços portáveis em `geoai.portal`."
    )
    policy = demo_connection_policy()
    st.sidebar.info(policy.description_pt)
    st.sidebar.caption(
        "Aptidão solar **não** é exibida nesta demo. "
        "Publicação na Cloud só após aprovação do responsável."
    )


def render_footer() -> None:
    st.markdown(
        """
<div class="napi-footer" role="contentinfo">
  NAPI GeoAI — demonstração institucional com artefatos IBGE versionados.
  Proveniência e validação fail-closed preservadas. Sem banco local exposto,
  sem Supabase nesta etapa. Interface desacoplada do motor científico.
</div>
""",
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner="Carregando camada territorial…")
def cached_parana_layer():
    """Cache de processo — adequado à Cloud (artefato estático no repo)."""

    return load_parana_layer(REPO_ROOT)


@st.cache_resource(show_spinner="Carregando municípios do Paraná…")
def cached_municipality_layer():
    return load_municipality_layer(REPO_ROOT)


@st.cache_resource(show_spinner="Carregando painel energético SIGA…")
def cached_energy_panel():
    return load_energy_panel_bundle(REPO_ROOT)


@st.cache_resource(show_spinner=False)
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
    # Texto no badge: não depende só da cor (a11y).
    return (
        f'<span class="napi-badge {css}" title="Status: {label}">'
        f"{label}</span>"
    )
