"""Bootstrap compartilhado das páginas Streamlit (somente UI)."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import streamlit as st
from geoai.portal import (
    demo_connection_policy,
    list_domain_cards,
    load_energy_panel_bundle,
    load_mmgd_panel_bundle,
    load_municipality_layer,
    load_parana_layer,
    load_population_panel_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_MAP_HTML_CACHE = Path(tempfile.gettempdir()) / "napi_geoai_streamlit_maps"

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
  background: #ffffff;
}
section[data-testid="stSidebar"] .napi-side-brand {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--napi-navy);
  margin: 0 0 0.25rem 0;
}

/* ---------- Portal (Home e navegação) ---------- */
.napi-hero-xl {
  position: relative;
  padding: 2.6rem 2.4rem 2.3rem 2.4rem;
  border-radius: 20px;
  color: #f8fafc;
  background:
    radial-gradient(700px 320px at 88% 0%, rgba(245, 158, 11, 0.38), transparent 60%),
    radial-gradient(600px 300px at 0% 100%, rgba(16, 185, 129, 0.28), transparent 60%),
    linear-gradient(135deg, #071a33 0%, #0b2545 45%, #14406b 100%);
  box-shadow: 0 18px 40px -22px rgba(11, 37, 69, 0.7);
  margin-bottom: 1.2rem;
  overflow: hidden;
}
.napi-hero-xl .eyebrow {
  font-size: 0.8rem; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: #fbbf24; margin: 0 0 0.7rem 0;
}
.napi-hero-xl h1 {
  color: #ffffff; font-size: clamp(1.9rem, 3.6vw, 3rem);
  line-height: 1.08; margin: 0 0 0.9rem 0; max-width: 46rem;
  letter-spacing: -0.03em; padding: 0;
}
.napi-hero-xl h1 em { font-style: normal; color: #fbbf24; }
.napi-hero-xl p.lead {
  color: #dbe7f5; font-size: 1.13rem; line-height: 1.55;
  max-width: 44rem; margin: 0;
}
.napi-hero-xl .pill {
  display: inline-block; margin-top: 1.1rem; padding: 0.3rem 0.8rem;
  border-radius: 999px; font-size: 0.82rem; font-weight: 600;
  color: #e2e8f0; background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.22);
}
.napi-kpi {
  background: #ffffff; border: 1px solid rgba(11, 37, 69, 0.10);
  border-radius: 16px; padding: 1.05rem 1.15rem 0.95rem 1.15rem;
  height: 100%; box-shadow: 0 8px 22px -18px rgba(11, 37, 69, 0.55);
  border-top: 4px solid var(--kpi, #1f4e79);
}
.napi-kpi .k-label {
  font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: #475569; margin: 0;
}
.napi-kpi .k-value {
  font-size: 2.05rem; font-weight: 700; color: #0b2545;
  line-height: 1.15; margin: 0.25rem 0 0.1rem 0; letter-spacing: -0.02em;
}
.napi-kpi .k-sub { font-size: 0.95rem; color: #1e293b; margin: 0 0 0.45rem 0; }
.napi-kpi .k-src { font-size: 0.78rem; color: #64748b; margin: 0; line-height: 1.35; }
.napi-card {
  background: #ffffff; border: 1px solid rgba(11, 37, 69, 0.10);
  border-radius: 16px; padding: 1.1rem 1.2rem; height: 100%;
  margin-bottom: 0.4rem;
}
.napi-card h4 { margin: 0 0 0.35rem 0; font-size: 1.08rem; padding: 0; }
.napi-card p { margin: 0; color: #475569; font-size: 0.96rem; line-height: 1.5; }
.napi-card .icon { font-size: 1.5rem; display: block; margin-bottom: 0.35rem; }
.napi-section-title { margin: 1.9rem 0 0.2rem 0; }
.napi-section-sub { color: #475569; margin: 0 0 0.9rem 0; font-size: 1rem; }
.napi-steps {
  display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.4rem 0 0.2rem 0;
}
.napi-steps span {
  background: #ffffff; border: 1px solid rgba(11,37,69,0.14);
  border-radius: 999px; padding: 0.32rem 0.85rem; font-size: 0.9rem;
  color: #0b2545; font-weight: 600;
}
.napi-steps span b { color: #b45309; margin-right: 0.35rem; }
section[data-testid="stSidebar"] .napi-side-group {
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: #64748b; margin: 0.9rem 0 0.1rem 0;
}
@media (max-width: 768px) {
  .napi-hero-xl { padding: 1.6rem 1.25rem; border-radius: 14px; }
  .napi-kpi .k-value { font-size: 1.6rem; }
}
</style>
"""


def configure_page(title: str, *, icon: str = "🗺️") -> None:
    st.set_page_config(
        page_title=f"NAPI GeoAI — {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def render_html_map(html: str, *, height: int) -> None:
    """Exibe HTML Folium/Leaflet via ``st.iframe`` (API atual do Streamlit).

    Grava o HTML em cache local efêmero (fora do Git) e embute por caminho.
    """

    digest = hashlib.sha1(html.encode("utf-8")).hexdigest()[:20]
    _MAP_HTML_CACHE.mkdir(parents=True, exist_ok=True)
    path = _MAP_HTML_CACHE / f"{digest}.html"
    if not path.is_file():
        path.write_text(html, encoding="utf-8")
    st.iframe(path, height=int(height), width="stretch")


NAV_GROUPS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "Comece aqui",
        (
            ("Home.py", "Início", "🏠"),
            ("pages/7_Ficha_Municipal.py", "Ficha municipal", "📍"),
            ("pages/5_Explorador_Territorial.py", "Explorador territorial", "🧭"),
        ),
    ),
    (
        "Energia",
        (
            ("pages/8_Energia_MMGD.py", "Geração distribuída (MMGD)", "☀️"),
            ("pages/6_Energia_SIGA.py", "Geração centralizada (SIGA)", "⚡"),
            ("pages/11_Ferramentas.py", "Ferramentas de cálculo", "🧮"),
        ),
    ),
    (
        "Território",
        (
            ("pages/10_Agricultura.py", "Agricultura", "🌾"),
            ("pages/9_Meio_Ambiente.py", "Meio ambiente", "🌳"),
            ("pages/2_Mapa_Parana.py", "Mapa do Paraná", "🗺️"),
        ),
    ),
    (
        "Transparência",
        (
            ("pages/1_Dominios.py", "Domínios e roadmap", "🧩"),
            ("pages/3_Fontes_e_qualidade.py", "Fontes e qualidade", "🔎"),
            ("pages/4_Sobre_e_deploy.py", "Sobre o projeto", "ℹ️"),
        ),
    ),
)


def page_link(path: str, label: str, icon: str | None = None, **kwargs) -> None:
    """``st.page_link`` tolerante: fora do app multipágina vira texto."""

    try:
        st.page_link(path, label=label, icon=icon, **kwargs)
    except Exception:  # noqa: BLE001 — teste isolado de página / versão antiga
        st.markdown(f"{icon or ''} {label}".strip())


def sidebar_brand() -> None:
    sb = st.sidebar
    sb.markdown(
        '<p class="napi-side-brand">NAPI GeoAI</p>',
        unsafe_allow_html=True,
    )
    sb.caption("Inteligência territorial e energética do Paraná.")
    for group, items in NAV_GROUPS:
        sb.markdown(
            f'<p class="napi-side-group">{group}</p>', unsafe_allow_html=True
        )
        with sb:
            for path, label, icon in items:
                page_link(path, label, icon)
    sb.divider()
    policy = demo_connection_policy()
    with sb.expander("Sobre os dados desta versão"):
        st.caption(policy.description_pt)
        st.caption(
            "Dados oficiais versionados (snapshots), não tempo real. "
            "Aptidão solar **não** é exibida nesta versão. "
            "Falta de dado aparece como falta de dado."
        )


def render_footer() -> None:
    st.markdown(
        """
<div class="napi-footer" role="contentinfo">
  <strong>NAPI GeoAI</strong> · NAPI Energia Zero Carbono · Paraná, Brasil.
  Dados oficiais (IBGE, ANEEL) em snapshots versionados, com proveniência e
  validação fail-closed. Os indicadores apoiam a investigação e não
  substituem estudos de viabilidade técnica, ambiental ou econômica.
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


@st.cache_resource(show_spinner="Carregando painel MMGD…")
def cached_mmgd_panel():
    return load_mmgd_panel_bundle(REPO_ROOT)


@st.cache_resource(show_spinner="Carregando população IBGE 2026…")
def cached_population_panel():
    return load_population_panel_bundle(REPO_ROOT)


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
