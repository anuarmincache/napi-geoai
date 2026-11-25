# ruff: noqa: E501
"""Folha de estilo do portal. Cores derivadas do logotipo NAPI Energia Zero-Carbono."""

from __future__ import annotations

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Source+Sans+3:wght@400;600;700&display=swap');

:root {
  --ezc-forest: #2f4a33;
  --ezc-green: #455b40;
  --ezc-moss: #5b8a3a;
  --ezc-leaf: #73a535;
  --ezc-lime: #a8cf5f;
  --ezc-sun: #fcc817;
  --ezc-ink: #1f2a24;
  --ezc-muted: #55655a;
  --ezc-paper: #f6f8f3;
  --ezc-card: #ffffff;
  --ezc-line: rgba(47, 74, 51, 0.14);
  --ezc-focus: #0b7285;
  /* nomes antigos, mantidos para as páginas existentes */
  --napi-navy: var(--ezc-forest);
  --napi-accent: var(--ezc-moss);
  --napi-ink: var(--ezc-ink);
  --napi-muted: var(--ezc-muted);
}

html, body, [class*="css"] {
  font-family: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  color: var(--ezc-ink);
}

.stApp {
  background:
    radial-gradient(900px 380px at 100% -8%, rgba(252, 200, 23, 0.10), transparent 60%),
    radial-gradient(1000px 420px at -6% -10%, rgba(115, 165, 53, 0.14), transparent 58%),
    linear-gradient(180deg, #f6f8f3 0%, #eef3e8 46%, #f7f9f4 100%);
}

.block-container { padding-top: 2.2rem; max-width: 1280px; }

h1, h2, h3, h4, h5 {
  font-family: "Montserrat", "Source Sans 3", sans-serif;
  color: var(--ezc-forest);
  letter-spacing: -0.015em;
  line-height: 1.18;
}
h2 { font-weight: 700; }
h3, h4, h5 { font-weight: 600; }

a { color: #2f6b1f; }

a:focus-visible, button:focus-visible, [role="button"]:focus-visible,
input:focus-visible, select:focus-visible, textarea:focus-visible,
.stSlider:focus-within {
  outline: 3px solid var(--ezc-focus) !important;
  outline-offset: 2px !important;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important; transition: none !important;
    scroll-behavior: auto !important;
  }
}

/* ---------- Cabeçalho de página ---------- */
.ezc-header {
  position: relative; display: flex; align-items: center; gap: 1.2rem;
  padding: 1.5rem 1.8rem; margin: 0 0 1.1rem 0; border-radius: 18px;
  color: #f4f8ef; overflow: hidden;
  background:
    radial-gradient(520px 240px at 96% 0%, rgba(252, 200, 23, 0.26), transparent 62%),
    linear-gradient(120deg, #2a4430 0%, #3d5a3a 52%, #547f36 100%);
  box-shadow: 0 16px 34px -24px rgba(31, 60, 36, 0.85);
}
.ezc-header .txt { flex: 1 1 auto; min-width: 0; }
.ezc-header .eyebrow {
  font-family: "Montserrat", sans-serif; font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--ezc-sun);
  margin: 0 0 0.35rem 0;
}
.ezc-header h1 {
  color: #ffffff; font-size: clamp(1.5rem, 2.6vw, 2.15rem); font-weight: 700;
  margin: 0; padding: 0; line-height: 1.12;
}
.ezc-header p.lead {
  color: #dfead6; margin: 0.5rem 0 0 0; font-size: 1.04rem; line-height: 1.5;
  max-width: 46rem;
}
.ezc-header img.art { flex: 0 0 auto; width: 190px; height: auto; }

/* ---------- Hero da Home ---------- */
.napi-hero-xl {
  position: relative; display: grid; grid-template-columns: 1.05fr 1fr;
  align-items: stretch; border-radius: 24px; color: #f4f8ef; overflow: hidden;
  margin-bottom: 1.2rem; min-height: 380px;
  background:
    radial-gradient(640px 320px at 78% 8%, rgba(252, 200, 23, 0.20), transparent 62%),
    linear-gradient(125deg, #24402b 0%, #2f4a33 40%, #456b38 100%);
  box-shadow: 0 22px 46px -28px rgba(31, 60, 36, 0.9);
}
.napi-hero-xl .copy { padding: 2.5rem 1rem 2.3rem 2.5rem; z-index: 2; }
.napi-hero-xl .scene {
  position: relative; min-height: 260px;
  background-repeat: no-repeat; background-position: 70% bottom;
  background-size: cover;
}
.napi-hero-xl .eyebrow {
  font-family: "Montserrat", sans-serif; font-size: 0.76rem; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--ezc-sun);
  margin: 0 0 0.8rem 0;
}
.napi-hero-xl h1 {
  color: #ffffff; font-size: clamp(1.9rem, 3.3vw, 2.9rem); font-weight: 800;
  line-height: 1.08; margin: 0 0 1rem 0; padding: 0; letter-spacing: -0.025em;
}
.napi-hero-xl h1 em { font-style: normal; color: var(--ezc-sun); }
.napi-hero-xl p.lead {
  color: #dfead6; font-size: 1.12rem; line-height: 1.55; margin: 0;
  max-width: 34rem;
}
.napi-hero-xl .pill {
  display: inline-block; margin-top: 1.2rem; padding: 0.32rem 0.85rem;
  border-radius: 999px; font-size: 0.82rem; font-weight: 600; color: #eaf3e2;
  background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.24);
}

/* herói antigo (páginas que ainda o usam) */
.napi-hero {
  padding: 1.3rem 1.5rem; border-left: 6px solid var(--ezc-leaf);
  background: #ffffff; border-radius: 0 14px 14px 0; margin-bottom: 1.1rem;
}
.napi-hero p { margin: 0; color: var(--ezc-muted); line-height: 1.5; }

/* ---------- Cartões ---------- */
.napi-kpi {
  background: var(--ezc-card); border: 1px solid var(--ezc-line);
  border-radius: 16px; padding: 1.05rem 1.15rem 0.95rem 1.15rem; height: 100%;
  box-shadow: 0 10px 24px -20px rgba(31, 60, 36, 0.7);
  border-top: 5px solid var(--kpi, var(--ezc-leaf));
}
.napi-kpi .k-label {
  font-family: "Montserrat", sans-serif; font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--ezc-muted);
  margin: 0;
}
.napi-kpi .k-value {
  font-family: "Montserrat", sans-serif; font-size: 2rem; font-weight: 700;
  color: var(--ezc-forest); line-height: 1.15; margin: 0.3rem 0 0.1rem 0;
  letter-spacing: -0.02em;
}
.napi-kpi .k-sub { font-size: 0.96rem; color: var(--ezc-ink); margin: 0 0 0.45rem 0; }
.napi-kpi .k-src { font-size: 0.78rem; color: #6b7a70; margin: 0; line-height: 1.35; }

.napi-card {
  background: var(--ezc-card); border: 1px solid var(--ezc-line);
  border-radius: 16px; padding: 1.15rem 1.2rem; height: 100%;
  margin-bottom: 0.4rem;
  /* Os três cartões ficam lado a lado com textos de tamanhos diferentes.
     A altura mínima alinha os links que vêm logo abaixo de cada um. */
  min-height: 310px;
}
.napi-card h4 { margin: 0 0 0.35rem 0; font-size: 1.05rem; padding: 0; }
.napi-card p { margin: 0; color: var(--ezc-muted); font-size: 0.97rem; line-height: 1.5; }
.napi-card .icon { font-size: 1.5rem; display: block; margin-bottom: 0.35rem; }
.napi-card img.art {
  width: 100%; height: 128px; object-fit: cover; border-radius: 12px;
  margin-bottom: 0.7rem;
  background: linear-gradient(120deg, #2f4a33, #547f36);
}

.napi-section-title { margin: 2rem 0 0.2rem 0; }
.napi-section-sub { color: var(--ezc-muted); margin: 0 0 0.9rem 0; font-size: 1.02rem; }

.napi-steps { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.4rem 0 0.2rem 0; }
.napi-steps span {
  background: #ffffff; border: 1px solid var(--ezc-line); border-radius: 999px;
  padding: 0.34rem 0.9rem; font-size: 0.9rem; color: var(--ezc-forest);
  font-weight: 600;
}
.napi-steps span b {
  display: inline-block; min-width: 1.35rem; margin-right: 0.4rem;
  padding: 0 0.3rem; border-radius: 999px; text-align: center;
  background: var(--ezc-sun); color: #3a2f00;
}

/* métricas nativas como cartão */
[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.72); border: 1px solid var(--ezc-line);
  border-radius: 14px; padding: 0.7rem 0.9rem;
}
[data-testid="stMetricLabel"] p { color: var(--ezc-muted); font-weight: 600; }
[data-testid="stMetricValue"] {
  font-family: "Montserrat", sans-serif; color: var(--ezc-forest);
  font-weight: 700; font-size: 1.7rem;
}

/* botões e abas */
.stButton > button, .stDownloadButton > button {
  border-radius: 10px; font-weight: 600; border-color: var(--ezc-line);
}
.stButton > button[kind="primary"] {
  background: var(--ezc-moss); border-color: var(--ezc-moss); color: #ffffff;
}
.stButton > button[kind="primary"]:hover { background: var(--ezc-forest); }
[data-baseweb="tab-list"] { gap: 0.4rem; }
[data-baseweb="tab"] { font-weight: 600; }
[data-testid="stExpander"] details {
  border-radius: 12px; border-color: var(--ezc-line); background: rgba(255,255,255,0.6);
}
[data-testid="stPageLink"] a { border-radius: 10px; }

/* selos de status */
.napi-badge {
  display: inline-block; padding: 0.18rem 0.6rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 700; margin-right: 0.35rem;
  border: 1px solid transparent;
}
.badge-partial { background: #fff4c7; color: #5c4500; border-color: #f0d875; }
.badge-planned { background: #e9eee6; color: #3d4b41; border-color: #d3dccf; }
.badge-available { background: #dff0cf; color: #24481a; border-color: #bcdc9f; }

.napi-meta { font-size: 0.92rem; color: var(--ezc-muted); line-height: 1.45; }

/* ---------- Rodapé institucional ---------- */
.napi-footer {
  margin-top: 2.6rem; padding: 1.3rem 1.5rem; border-radius: 18px;
  background: #ffffff; border: 1px solid var(--ezc-line);
  display: flex; flex-wrap: wrap; align-items: center; gap: 1.4rem;
  color: var(--ezc-muted); font-size: 0.88rem; line-height: 1.5;
}
.napi-footer img.logo { height: 62px; width: auto; }
.napi-footer .who { flex: 1 1 22rem; }
.napi-footer .who strong { color: var(--ezc-forest); }
.napi-footer .inst {
  display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem;
}
.napi-footer .inst span {
  border: 1px solid var(--ezc-line); border-radius: 999px;
  padding: 0.18rem 0.75rem; color: var(--ezc-forest); font-weight: 600;
  background: var(--ezc-paper);
}

/* ---------- Barra lateral ---------- */
section[data-testid="stSidebar"] {
  background: #ffffff; border-right: 1px solid var(--ezc-line);
}
section[data-testid="stSidebar"] img.side-logo {
  width: 100%; max-width: 210px; height: auto; display: block;
  margin: 0.2rem 0 0.6rem 0;
}
section[data-testid="stSidebar"] .napi-side-brand {
  font-family: "Montserrat", sans-serif; font-size: 1.2rem; font-weight: 800;
  color: var(--ezc-forest); margin: 0; letter-spacing: -0.02em;
}
section[data-testid="stSidebar"] .napi-side-brand em {
  font-style: normal; color: var(--ezc-leaf);
}
section[data-testid="stSidebar"] .napi-side-tag {
  font-size: 0.86rem; color: var(--ezc-muted); margin: 0.1rem 0 0.4rem 0;
  line-height: 1.35;
}
section[data-testid="stSidebar"] .napi-side-group {
  font-family: "Montserrat", sans-serif; font-size: 0.68rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--ezc-moss);
  margin: 1rem 0 0.1rem 0;
}

@media (max-width: 900px) {
  .napi-hero-xl { grid-template-columns: 1fr; min-height: 0; }
  .napi-hero-xl .copy { padding: 1.7rem 1.3rem 1.2rem 1.3rem; }
  .napi-hero-xl .scene { min-height: 190px; }
  .napi-card { min-height: 0; }
  .ezc-header { padding: 1.2rem 1.2rem; }
  .ezc-header img.art { display: none; }
  .napi-kpi .k-value { font-size: 1.6rem; }
  [data-testid="stMetricValue"] { font-size: 1.35rem; }
}
</style>
"""
