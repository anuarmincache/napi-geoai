"""Bootstrap compartilhado das páginas Streamlit (somente UI)."""

from __future__ import annotations

import base64
import hashlib
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# O pacote geoai vive na raiz do repositório e não é instalado na Streamlit
# Community Cloud, onde entram apenas as dependências de app/requirements.txt.
# Garantir a raiz em sys.path antes do primeiro import de geoai faz a aplicação
# subir igual na Cloud, na execução local e nos testes, sem depender de qual é
# o diretório de trabalho.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st  # noqa: E402
from geoai.portal import (  # noqa: E402
    list_domain_cards,
    load_energy_panel_bundle,
    load_mmgd_panel_bundle,
    load_municipality_layer,
    load_parana_layer,
    load_population_panel_bundle,
)

from ui import art  # noqa: E402
from ui.theme import CUSTOM_CSS  # noqa: E402

LOGO_PATH = REPO_ROOT / "assets" / "napi-ezc-logo.png"
HERO_PATH = REPO_ROOT / "assets" / "hero-parana.webp"
INSTITUTIONS = ("Universidade Estadual de Maringá (UEM)", "Fundação Araucária")
_MAP_HTML_CACHE = Path(tempfile.gettempdir()) / "napi_geoai_streamlit_maps"

def br_num(value: object, digits: int = 0, *, missing: str = "n/d") -> str:
    """Número no padrão brasileiro (1.234,5). ``None`` vira ``missing``."""

    if value is None:
        return missing
    try:
        text = f"{float(value):,.{int(digits)}f}"
    except (TypeError, ValueError):
        return missing
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def date_br(iso: object, *, missing: str = "n/d") -> str:
    parts = str(iso or "")[:10].split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return missing


@lru_cache(maxsize=1)
def logo_data_uri() -> str | None:
    """Logotipo NAPI Energia Zero-Carbono (arquivo cedido pelo projeto)."""

    try:
        raw = LOGO_PATH.read_bytes()
    except OSError:
        return None
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


@lru_cache(maxsize=8)
def asset_data_uri(nome: str) -> str | None:
    """Imagem de ``assets/`` embutida na página, ou ``None`` se faltar.

    As ilustrações são arquivos cedidos pelo projeto. Entram embutidas porque
    a Community Cloud não serve estáticos por padrão, e por isso cada uma é
    mantida pequena: peso aqui vira tempo de carregamento para quem visita.
    """
    caminho = REPO_ROOT / "assets" / nome
    try:
        raw = caminho.read_bytes()
    except OSError:
        return None
    tipo = "webp" if caminho.suffix == ".webp" else caminho.suffix.lstrip(".")
    return f"data:image/{tipo};base64," + base64.b64encode(raw).decode("ascii")


@lru_cache(maxsize=1)
def hero_image_data_uri() -> str | None:
    """Ilustração do topo da página inicial, cedida pelo projeto.

    A imagem traz só a paisagem. O título e o texto ao lado continuam sendo
    texto de verdade na página, para serem lidos por leitor de tela, achados
    pela busca e reorganizados no celular, o que não acontece quando a frase
    está desenhada dentro do arquivo.
    """
    try:
        raw = HERO_PATH.read_bytes()
    except OSError:
        return None
    return "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")


def page_header(
    title: str,
    lead: str | None = None,
    *,
    art_kind: str = "map",
    eyebrow: str = "NAPI GeoAI",
    banner: str | None = None,
    banner_alt: str = "",
    banner_pos: str = "center right",
    chips: tuple[str, ...] = (),
) -> None:
    """Faixa de título padronizada, com ilustração própria.

    ``banner`` nomeia um arquivo de ``assets/`` com a ilustração da página. O
    título, o resumo e as etiquetas continuam sendo texto, pelos mesmos
    motivos do bloco do topo da página inicial: leitor de tela, busca e
    reorganização no celular. Faltando o arquivo, o desenho vetorial assume.

    ``chips`` são as etiquetas do que a página cobre. Elas afirmam algo, então
    cada uma precisa corresponder ao que a página realmente mostra. Mantenha a
    linha curta, até umas cinco palavras somadas por etiqueta: quando a lista
    quebra em duas linhas, o divisor da primeira etiqueta da linha de baixo
    fica solto, e CSS não tem como detectar início de linha para escondê-lo.

    ``banner_pos`` escolhe que parte da ilustração fica visível quando a
    largura aperta. O padrão mostra a direita; use ``center left`` quando o que
    importa na arte estiver do lado esquerdo dela.
    """

    lead_html = f'<p class="lead">{lead}</p>' if lead else ""
    chips_html = ""
    if chips:
        itens = "".join(f"<span>{c}</span>" for c in chips)
        chips_html = f'<p class="ezc-chips">{itens}</p>'
    fonte = (asset_data_uri(banner) if banner else None) or art.data_uri(
        art.spot(art_kind)
    )
    st.markdown(
        f'''
<div class="ezc-header" role="banner">
  <div class="txt">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{title}</h1>
    {lead_html}
    {chips_html}
  </div>
  <img class="art" alt="{banner_alt}" src="{fonte}"
       style="object-position: {banner_pos}"/>
</div>
''',
        unsafe_allow_html=True,
    )


def configure_page(title: str, *, icon: str = "🌱") -> None:
    st.set_page_config(
        page_title=f"NAPI GeoAI — {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


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
            ("pages/7_Ficha_Municipal.py", "Ficha do município", "📍"),
            ("pages/5_Explorador_Territorial.py", "Explorar o mapa", "🧭"),
        ),
    ),
    (
        "Energia",
        (
            ("pages/8_Energia_MMGD.py", "Solar e geração distribuída", "☀️"),
            ("pages/6_Energia_SIGA.py", "Usinas e geração centralizada", "⚡"),
            ("pages/11_Ferramentas.py", "Calculadoras", "🧮"),
        ),
    ),
    (
        "Território",
        (
            ("pages/10_Agricultura.py", "Agricultura e pecuária", "🌾"),
            ("pages/9_Meio_Ambiente.py", "Cobertura da terra", "🌳"),
        ),
    ),
    (
        "Transparência",
        (
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
    logo = logo_data_uri()
    if logo:
        sb.markdown(
            f'<img class="side-logo" alt="NAPI Energia Zero-Carbono" src="{logo}"/>',
            unsafe_allow_html=True,
        )
    sb.markdown(
        '<p class="napi-side-brand">NAPI Geo<em>AI</em></p>'
        '<p class="napi-side-tag">Inteligência territorial e energética '
        "do Paraná</p>",
        unsafe_allow_html=True,
    )
    for group, items in NAV_GROUPS:
        sb.markdown(
            f'<p class="napi-side-group">{group}</p>', unsafe_allow_html=True
        )
        with sb:
            for path, label, icon in items:
                page_link(path, label, icon)
    sb.divider()
    with sb.expander("Sobre os dados desta versão"):
        st.caption(
            "Dados oficiais em retratos datados (não é tempo real). Cada "
            "número traz a fonte e a data. Quando um dado não existe, a "
            "página diz que não existe."
        )


def render_footer() -> None:
    logo = logo_data_uri()
    logo_html = (
        f'<img class="logo" alt="NAPI Energia Zero-Carbono" src="{logo}"/>'
        if logo
        else ""
    )
    chips = "".join(f"<span>{name}</span>" for name in INSTITUTIONS)
    st.markdown(
        f"""
<div class="napi-footer" role="contentinfo">
  {logo_html}
  <div class="who">
    <strong>NAPI GeoAI</strong> é uma iniciativa do NAPI Energia Zero-Carbono.
    Dados oficiais (IBGE, ANEEL, MapBiomas) em retratos datados, com fonte
    e data em cada número. Os indicadores apoiam a
    investigação e não substituem estudos de viabilidade técnica, ambiental
    ou econômica.
    <div class="inst">{chips}</div>
  </div>
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


@st.cache_resource(show_spinner="Montando o espaço de comparação…")
def cached_similaridade():
    """Índice de municípios parecidos. Conta determinística, uma vez por processo.

    Devolve ``None`` quando falta algum painel, para a página omitir a seção
    em vez de mostrar uma vizinhança calculada sobre dado incompleto.
    """
    from geoai.portal.landcover_panel import load_landcover_bundle
    from geoai.portal.similaridade import (
        DadosInsuficientes,
        construir_indice,
        linhas_dos_paineis,
    )

    cobertura = load_landcover_bundle(REPO_ROOT)
    mmgd = load_mmgd_panel_bundle(REPO_ROOT)
    if not (cobertura.available and mmgd.available):
        return None
    try:
        return construir_indice(
            linhas_dos_paineis(
                populacao=load_population_panel_bundle(REPO_ROOT),
                cobertura=cobertura,
                mmgd=mmgd,
            )
        )
    except DadosInsuficientes:
        return None


@st.cache_resource(show_spinner="Carregando cobertura e uso da terra…")
def cached_landcover_panel():
    from geoai.portal.landcover_panel import load_landcover_bundle

    return load_landcover_bundle(REPO_ROOT)


@st.cache_resource(show_spinner="Carregando painel agropecuário…")
def cached_agro_panel():
    from geoai.portal.agro_panel import load_agro_panel_bundle

    return load_agro_panel_bundle(REPO_ROOT)


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
