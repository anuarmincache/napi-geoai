"""Entrada Streamlit — Portal NAPI GeoAI."""

from __future__ import annotations

import streamlit as st
from geoai.portal import (
    list_municipalities,
    mmgd_map_html,
    mmgd_ranked,
    municipality_label,
)

from _bootstrap import (
    cached_agro_panel,
    cached_energy_panel,
    cached_landcover_panel,
    cached_mmgd_panel,
    cached_municipality_layer,
    cached_population_panel,
    configure_page,
    page_link,
    render_footer,
    render_html_map,
    sidebar_brand,
)
from ui import art

configure_page("Início")
sidebar_brand()


def _int_br(value: float | int) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def _dec_br(value: float, digits: int = 1) -> str:
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _date_br(iso: object) -> str:
    text = str(iso or "")[:10]
    parts = text.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return "data não registrada"


def _kpi(label: str, value: str, sub: str, source: str, color: str) -> str:
    return (
        f'<div class="napi-kpi" style="--kpi:{color}">'
        f'<p class="k-label">{label}</p>'
        f'<p class="k-value">{value}</p>'
        f'<p class="k-sub">{sub}</p>'
        f'<p class="k-src">{source}</p></div>'
    )


_UNAVAILABLE = "indisponível"

mun = cached_municipality_layer()
pop = cached_population_panel()
siga = cached_energy_panel()
mmgd = cached_mmgd_panel()
agro = cached_agro_panel()
landcover = cached_landcover_panel()

# ---------------------------------------------------------------- Hero
st.markdown(
    f"""
<div class="napi-hero-xl" role="banner">
  <div class="copy">
    <p class="eyebrow">NAPI Energia Zero-Carbono · Paraná</p>
    <h1>NAPI GeoAI: onde investigar <em>energia limpa</em> no Paraná</h1>
    <p class="lead">
      Território, população, energia, lavouras e cobertura da terra dos 399
      municípios, reunidos em um só lugar. Explore, compare e descubra quais
      regiões merecem um estudo mais profundo, com a fonte e o limite de cada
      número sempre à vista.
    </p>
    <span class="pill">Em desenvolvimento · dados oficiais em retratos
    datados, não tempo real</span>
  </div>
  <div class="scene" role="img"
       aria-label="Paisagem ilustrada com energia solar e eólica"
       style="background-image:url('{art.data_uri(art.hero_landscape())}')"></div>
</div>
""",
    unsafe_allow_html=True,
)

cta1, cta2, cta3, _sp = st.columns([1.2, 1.3, 1.3, 1.6])
with cta1:
    page_link("pages/7_Ficha_Municipal.py", "Abrir ficha municipal", "📍")
with cta2:
    page_link("pages/8_Energia_MMGD.py", "Ver geração distribuída", "☀️")
with cta3:
    page_link("pages/11_Ferramentas.py", "Usar as calculadoras", "🧮")

# ---------------------------------------------------------------- KPIs
kpis: list[str] = []

if mun.validated_for_map:
    n_mun = len(list_municipalities(mun))
    kpis.append(
        _kpi(
            "Território",
            _int_br(n_mun),
            "municípios com malha validada",
            "IBGE · Malha Municipal 2025",
            "#455b40",
        )
    )
else:
    kpis.append(
        _kpi("Território", _UNAVAILABLE, "malha municipal", "IBGE", "#94a3b8")
    )

if pop.available:
    panel = pop.panel
    kpis.append(
        _kpi(
            "População",
            f"{_dec_br(float(panel['population_sum_hab']) / 1e6, 2)} mi",
            "habitantes (estimativa, não Censo)",
            "IBGE · Estimativas · referência "
            f"{_date_br(panel.get('population_reference_date'))}",
            "#73a535",
        )
    )
else:
    kpis.append(
        _kpi("População", _UNAVAILABLE, "estimativa municipal", "IBGE", "#94a3b8")
    )

if mmgd.available:
    tot = mmgd.panel["totals"]
    kpis.append(
        _kpi(
            "Geração distribuída",
            f"{_dec_br(float(tot['potencia_instalada_mw_conhecida']) / 1e3, 2)} GW",
            f"{_int_br(tot['n_empreendimentos'])} instalações",
            "ANEEL · geração distribuída · retrato de "
            f"{mmgd.panel.get('periodo_referencia') or 'n/d'} · potência "
            "instalada",
            "#fcc817",
        )
    )
else:
    kpis.append(
        _kpi("Geração distribuída", _UNAVAILABLE, "MMGD", "ANEEL", "#94a3b8")
    )

if siga.available:
    tot = siga.panel["totals"]
    kpis.append(
        _kpi(
            "Geração centralizada",
            f"{_dec_br(float(tot['potencia_fiscalizada_mw_conhecida_fase']) / 1e3, 1)}"
            " GW",
            f"{_int_br(tot['n_empreendimentos_fase'])} usinas em operação",
            "ANEEL · SIGA · coleta "
            f"{_date_br(siga.provenance.get('retrieved_at'))} · potência "
            "fiscalizada",
            "#2f4a33",
        )
    )
else:
    kpis.append(
        _kpi("Geração centralizada", _UNAVAILABLE, "SIGA", "ANEEL", "#94a3b8")
    )

for col, html in zip(st.columns(4), kpis, strict=True):
    col.markdown(html, unsafe_allow_html=True)

st.caption(
    "Potência instalada (GW) não é energia gerada (GWh). Geração distribuída "
    "(MMGD) e centralizada (SIGA) são cadastros diferentes e não se somam "
    "sem critério."
)

# ---------------------------------------------------------------- Mapa
st.markdown(
    '<h2 class="napi-section-title">O Paraná em um mapa</h2>'
    '<p class="napi-section-sub">Potência instalada de geração '
    "distribuída por município. Passe o cursor para ver os valores.</p>",
    unsafe_allow_html=True,
)

map_col, side_col = st.columns([2.1, 1], gap="large")
with map_col:
    if mun.validated_for_map and mmgd.available:
        try:
            render_html_map(mmgd_map_html(mun, mmgd), height=500)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao renderizar o mapa: {exc}")
    else:
        st.warning(
            "Mapa indisponível: "
            + (
                mun.missing_reason_pt
                or mmgd.missing_reason_pt
                or "os dados necessários não estão disponíveis."
            )
        )

with side_col:
    st.markdown("#### Comece por um município")
    if mun.validated_for_map:
        records = list_municipalities(mun)
        label_to_code = {municipality_label(rec): rec.code for rec in records}
        choice = st.selectbox(
            "Digite o nome ou o código IBGE",
            options=list(label_to_code.keys()),
            index=None,
            placeholder="Ex.: Maringá",
            key="home_city",
        )
        if st.button(
            "Abrir ficha municipal",
            type="primary",
            disabled=choice is None,
            width="stretch",
        ):
            st.session_state["ficha_code"] = label_to_code[choice]
            st.session_state["ficha_query"] = ""
            st.switch_page("pages/7_Ficha_Municipal.py")
    else:
        st.caption("Busca indisponível sem a malha municipal.")

    if mmgd.available:
        st.markdown("#### Maior potência instalada de geração distribuída")
        for pos, row in enumerate(mmgd_ranked(mmgd, limit=5), start=1):
            name = row.get("NM_MUN") or row.get("nome_fonte") or row.get("CD_MUN")
            st.markdown(
                f"{pos}. **{name}** · "
                f"{_dec_br(float(row.get('display_mw') or 0.0), 1)} MW"
            )
        st.caption(
            "Ordenação descritiva deste retrato. Muitas instalações não "
            "provam saturação, demanda futura nem rentabilidade."
        )

# ------------------------------------------------------------- Públicos
st.markdown(
    '<h2 class="napi-section-title">O que você quer investigar?</h2>'
    '<p class="napi-section-sub">Três caminhos de entrada para a mesma base '
    "de dados.</p>",
    unsafe_allow_html=True,
)
aud = st.columns(3)
with aud[0]:
    st.markdown(
        '<div class="napi-card">'
        f'<img class="art" alt="" src="{art.data_uri(art.spot('solar'))}"/>'
        ''
        "<h4>Empreendedores e empresas</h4>"
        "<p>Veja onde a geração solar distribuída já está presente, em quais "
        "classes de consumo, e selecione municípios para pesquisa comercial."
        "</p></div>",
        unsafe_allow_html=True,
    )
    page_link("pages/8_Energia_MMGD.py", "Explorar MMGD por município", "☀️")
    page_link(
        "pages/11_Ferramentas.py", "Simular consumo e sistema solar", "🧮"
    )
with aud[1]:
    st.markdown(
        '<div class="napi-card">'
        f'<img class="art" alt="" src="{art.data_uri(art.spot('docs'))}"/>'
        ''
        "<h4>Pesquisadores e universidades</h4>"
        "<p>Consulte proveniência, hashes, cobertura e limitações de cada "
        "fonte. Compare municípios com indicadores reprodutíveis.</p></div>",
        unsafe_allow_html=True,
    )
    page_link("pages/3_Fontes_e_qualidade.py", "Fontes e qualidade", "🔎")
    page_link("pages/6_Energia_SIGA.py", "Usinas por tecnologia (SIGA)", "⚡")
with aud[2]:
    st.markdown(
        '<div class="napi-card">'
        f'<img class="art" alt="" src="{art.data_uri(art.spot('map'))}"/>'
        ''
        "<h4>Gestores públicos e cooperativas</h4>"
        "<p>Abra o perfil do seu município, compare com vizinhos e "
        "identifique lacunas de dados antes de planejar projetos.</p></div>",
        unsafe_allow_html=True,
    )
    page_link("pages/7_Ficha_Municipal.py", "Ficha municipal integrada", "📍")
    page_link("pages/5_Explorador_Territorial.py", "Explorador territorial", "🧭")

# -------------------------------------------------------------- Método
st.markdown(
    '<h2 class="napi-section-title">Do dado à hipótese, sem atalhos</h2>'
    '<p class="napi-section-sub">A plataforma ajuda a priorizar investigações. '
    "Ela não declara viabilidade econômica.</p>"
    '<div class="napi-steps">'
    "<span><b>1</b>Conhecer o território</span>"
    "<span><b>2</b>Explorar indicadores</span>"
    "<span><b>3</b>Comparar regiões</span>"
    "<span><b>4</b>Identificar sinais</span>"
    "<span><b>5</b>Investigar restrições</span>"
    "<span><b>6</b>Formular hipóteses</span>"
    "<span><b>7</b>Apoiar estudos de viabilidade</span>"
    "</div>",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------- Status
st.markdown(
    '<h2 class="napi-section-title">O que já está no ar</h2>'
    '<p class="napi-section-sub">Disponível, em estruturação e planejado, '
    "sem misturar as três coisas.</p>",
    unsafe_allow_html=True,
)
s1, s2, s3 = st.columns(3)
with s1:
    st.markdown("##### ✅ Disponível com dados oficiais")
    st.markdown(
        "- Malha e explorador dos 399 municípios (IBGE)\n"
        "- População estimada e densidade (IBGE)\n"
        "- Geração centralizada por tecnologia (ANEEL SIGA)\n"
        + (
            "- Geração distribuída por município (ANEEL MMGD)\n"
            if mmgd.available
            else ""
        )
        + (
            "- Lavouras e pecuária por município (IBGE PAM e PPM)\n"
            if agro.available
            else ""
        )
        + (
            "- Cobertura e uso da terra, 1985 a 2025 (MapBiomas)\n"
            if landcover.available
            else ""
        )
        + "- Ficha municipal integrada\n"
        "- Calculadoras de consumo e fotovoltaico preliminar"
    )
with s2:
    st.markdown("##### 🚧 Estrutura pronta, aguardando dados")
    st.markdown(
        (
            ""
            if agro.available
            else "- Agricultura: pecuária e produção municipal (IBGE PPM/PAM)\n"
        )
        + (
            "- Meio ambiente: unidades de conservação e recursos hídricos\n"
            if landcover.available
            else "- Meio ambiente: cobertura e uso da terra (MapBiomas)\n"
        )
    )
    st.caption("Nessas páginas, indicador sem fonte aparece como indisponível.")
with s3:
    st.markdown("##### 🗓️ Planejado")
    st.markdown(
        "- Recurso solar e aptidão territorial (INPE/LABREN)\n"
        "- Biogás e biometano em níveis de evidência\n"
        "- Observatório dinâmico Paraná Agora\n"
        "- Radar exploratório de oportunidades\n"
        "- Comparação automática entre municípios semelhantes"
    )

with st.expander("Como classificamos cada número"):
    st.markdown(
        "- **A, dado oficial:** registrado diretamente na fonte "
        "(ex.: potência cadastrada na ANEEL).\n"
        "- **B, indicador derivado:** cálculo determinístico sobre dados "
        "oficiais, com fórmula e unidade (ex.: kW por habitante).\n"
        "- **C, modelo ou simulação:** estimativa com hipóteses declaradas "
        "(ex.: calculadora fotovoltaica).\n\n"
        "Zero verdadeiro, dado indisponível e município sem associação "
        "espacial são mostrados de forma diferente. Falta de dado nunca é "
        "preenchida."
    )

st.info(
    "Todas as áreas ficam no menu lateral (☰ em telas estreitas): "
    "**Ficha do município**, **Explorar o mapa**, **Solar e geração "
    "distribuída** (Energia, MMGD), **Usinas e geração centralizada** "
    "(Energia, SIGA), **Calculadoras**, **Agricultura e pecuária**, "
    "**Cobertura da terra** (Meio Ambiente), **Fontes e qualidade** e "
    "**Sobre o projeto**."
)
render_footer()
