"""Explorador territorial interativo — 399 municípios do Paraná (MVP 09.1)."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal import (
    compare_municipalities,
    explorer_attribution_lines,
    get_municipality,
    list_municipalities,
    municipality_label,
    municipality_map_html,
    polo_city_records,
    search_municipalities,
)
from geoai.presentation import AudienceLevel

from _bootstrap import (
    cached_municipality_layer,
    configure_page,
    render_footer,
    sidebar_brand,
)

NONE_SELECTION = "— Mapa geral do Paraná (sem destaque) —"

configure_page("Explorador territorial")
sidebar_brand()

st.title("Explorador territorial do Paraná")
st.caption(
    "Malha municipal oficial IBGE (`municipio_2025`) — **todos os "
    f"{EXPECTED_PR_MUNICIPALITY_COUNT} municípios** disponíveis. "
    "Limite administrativo **não** é aptidão solar nem viabilidade comercial."
)

bundle = cached_municipality_layer()
if not bundle.validated_for_map:
    st.error(
        bundle.missing_reason_pt
        or "Camada municipal não validada (fail-closed)."
    )
    render_footer()
    st.stop()

level = st.radio(
    "Nível didático",
    options=[
        AudienceLevel.BASIC,
        AudienceLevel.INTERMEDIATE,
        AudienceLevel.TECHNICAL,
    ],
    format_func={
        AudienceLevel.BASIC: "Básico",
        AudienceLevel.INTERMEDIATE: "Intermediário",
        AudienceLevel.TECHNICAL: "Técnico",
    }.__getitem__,
    horizontal=True,
)
if level is AudienceLevel.BASIC:
    st.info(
        f"Busque por nome ou código IBGE entre os "
        f"{EXPECTED_PR_MUNICIPALITY_COUNT} municípios. "
        "Os 20 atalhos de cidades-polo só aceleram a escolha — "
        "não são um ranking. A comparação usa nome, código e área oficial."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "Geometrias de apresentação são simplificadas (tolerância documentada). "
        "Área vem do campo oficial `AREA_KM2` da malha — não recalculada em graus."
    )
else:
    st.info(
        "Proveniência/SHA/CRS/contagem em `data/derived/parana_municipios_2025.*`. "
        "Alta fidelidade: ZIP IBGE regenerável. Evidência QGIS Desktop "
        "(`*_qgis_report.json`) é local — não embutida no Streamlit Cloud."
    )

all_recs = list_municipalities(bundle)
label_to_code = {municipality_label(r): r.code for r in all_recs}
labels_all = list(label_to_code.keys())
code_to_label = {code: lab for lab, code in label_to_code.items()}
polos = polo_city_records(bundle)
polo_labels = {municipality_label(r): r.code for r in polos}

if "explorer_code" not in st.session_state:
    # Primeira visita: mapa geral, sem município pré-selecionado.
    st.session_state.explorer_code = None
if "explorer_query" not in st.session_state:
    st.session_state.explorer_query = ""
if "polo_choice" not in st.session_state:
    st.session_state.polo_choice = "(nenhum)"
if "explorer_select_label" not in st.session_state:
    st.session_state.explorer_select_label = NONE_SELECTION


def _on_polo_change() -> None:
    choice = st.session_state.get("polo_choice")
    if choice and choice != "(nenhum)":
        code = polo_labels[choice]
        st.session_state.explorer_code = code
        st.session_state.explorer_query = ""
        st.session_state.explorer_select_label = code_to_label[code]
        st.session_state.polo_choice = "(nenhum)"
        if code in code_to_label:
            st.session_state.cmp_a = code_to_label[code]


def _clear_search() -> None:
    st.session_state.explorer_query = ""


def _on_select_change() -> None:
    lab = st.session_state.get("explorer_select_label")
    if lab == NONE_SELECTION:
        st.session_state.explorer_code = None
    elif lab in label_to_code:
        st.session_state.explorer_code = label_to_code[lab]
        st.session_state.cmp_a = lab


st.markdown("### Buscar município")
st.caption(
    f"Catálogo completo: **{EXPECTED_PR_MUNICIPALITY_COUNT}** municípios do Paraná. "
    "Os 20 atalhos ao lado apenas aceleram a navegação."
)

c_search, c_polo = st.columns([2, 1], gap="medium")
with c_search:
    st.text_input(
        "Busca por nome ou código IBGE",
        key="explorer_query",
        placeholder="Digite cidade ou código IBGE, ex.: Maringá / 4115200",
        help=(
            "Acentos são ignorados. Com o campo limpo, o seletor lista "
            f"todos os {EXPECTED_PR_MUNICIPALITY_COUNT} municípios."
        ),
    )
    clear_col, _ = st.columns([1, 3])
    with clear_col:
        st.button(
            "Limpar busca",
            on_click=_clear_search,
            use_container_width=True,
            help="Remove o filtro e volta a listar os 399 municípios.",
        )

    query = str(st.session_state.explorer_query or "")
    hits = search_municipalities(bundle, query, limit=None)
    hit_count = len(hits)
    st.markdown(
        f"**{hit_count} de {EXPECTED_PR_MUNICIPALITY_COUNT}** municípios"
    )

    query_active = bool(query.strip())
    if query_active and hit_count == 0:
        st.warning("Nenhum município encontrado")
        st.caption(
            "A seleção e o mapa atuais foram mantidos. "
            "Ajuste a busca ou use Limpar busca."
        )
    else:
        options = [NONE_SELECTION, *[municipality_label(r) for r in hits]]
        # Um único resultado na busca → seleciona automaticamente (sync mapa).
        if query_active and hit_count == 1:
            only = municipality_label(hits[0])
            st.session_state.explorer_select_label = only
            st.session_state.explorer_code = hits[0].code
            st.session_state.cmp_a = only
        code = st.session_state.explorer_code
        sticky = code_to_label.get(code) if code else None
        if sticky and sticky not in options:
            # Mantém a seleção atual visível mesmo fora do filtro parcial.
            options = [NONE_SELECTION, sticky, *options[1:]]
        if st.session_state.explorer_select_label not in options:
            st.session_state.explorer_select_label = (
                sticky if sticky in options else NONE_SELECTION
            )

        st.selectbox(
            "Município selecionado",
            options=options,
            key="explorer_select_label",
            on_change=_on_select_change,
            help=(
                "Lista filtrada pela busca. Campo limpo = todos os "
                f"{EXPECTED_PR_MUNICIPALITY_COUNT}. "
                "Escolha o mapa geral para ver o Paraná sem destaque."
            ),
        )
        lab = st.session_state.explorer_select_label
        if lab == NONE_SELECTION:
            st.session_state.explorer_code = None
        elif lab in label_to_code:
            st.session_state.explorer_code = label_to_code[lab]

with c_polo:
    st.markdown("#### Cidades-polo (atalhos)")
    st.caption(
        f"20 atalhos regionais — **não** é ranking. "
        f"O catálogo tem {EXPECTED_PR_MUNICIPALITY_COUNT} municípios."
    )
    st.selectbox(
        "Atalho rápido",
        options=["(nenhum)", *polo_labels.keys()],
        key="polo_choice",
        on_change=_on_polo_change,
        help="Ao escolher um polo, a busca é limpa e o mapa destaca a cidade.",
    )

selected_code = st.session_state.explorer_code

st.markdown(
    """
    <style>
    iframe[title="streamlit_html"] {
      background: #e8eef5 !important;
      border: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

map_col, meta_col = st.columns([2.2, 1], gap="medium")
with meta_col:
    with st.expander("Personalizar mapa", expanded=False):
        fill_opacity = st.slider(
            "Opacidade do preenchimento", 0.05, 0.7, 0.28, 0.05
        )
        line_weight = st.slider("Espessura do contorno", 0.5, 3.0, 1.0, 0.5)
        map_height = st.select_slider(
            "Altura do mapa (px)",
            options=[420, 520, 600, 680, 760],
            value=600,
            help="Ajuste para notebooks ou telas estreitas.",
        )

    st.markdown("#### Município em foco")
    rec = get_municipality(bundle, selected_code) if selected_code else None
    if rec:
        st.metric("Nome", rec.name)
        st.metric("Código IBGE", rec.code)
        st.metric("Área oficial (km²)", f"{rec.area_km2:.3f}")
    else:
        st.info(
            f"Mapa geral: {EXPECTED_PR_MUNICIPALITY_COUNT} municípios. "
            "Selecione um município na busca ou use um atalho."
        )

    with st.expander("Fonte e metodologia", expanded=False):
        for line in explorer_attribution_lines(bundle):
            st.markdown(
                f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True
            )
        st.caption("Basemap: © OpenStreetMap contributors.")

with map_col:
    with st.spinner("Renderizando mapa municipal…"):
        try:
            html = municipality_map_html(
                bundle,
                selected_code=selected_code,
                fill_opacity=float(fill_opacity),
                line_weight=float(line_weight),
            )
            components.html(html, height=int(map_height), scrolling=False)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao renderizar mapa: {exc}")

st.subheader("Comparação territorial (dois municípios)")
st.caption(
    "Somente atributos verificáveis da malha. Sem população, PIB, irradiação "
    "ou oportunidade inventados."
)

if selected_code and selected_code in code_to_label:
    preferred_a = code_to_label[selected_code]
else:
    preferred_a = labels_all[0]
if "cmp_a" not in st.session_state:
    st.session_state.cmp_a = preferred_a
if st.session_state.cmp_a not in labels_all:
    st.session_state.cmp_a = preferred_a

if "cmp_b" not in st.session_state:
    # Prefer Londrina quando A é Maringá; senão o segundo da lista.
    londrina = next((lab for lab in labels_all if "4113700" in lab), None)
    if preferred_a != londrina and londrina:
        st.session_state.cmp_b = londrina
    else:
        st.session_state.cmp_b = next(
            (lab for lab in labels_all if lab != preferred_a),
            labels_all[0],
        )
if st.session_state.cmp_b not in labels_all:
    st.session_state.cmp_b = labels_all[min(1, len(labels_all) - 1)]

left, right = st.columns(2)
with left:
    a_lab = st.selectbox(
        "Município A",
        labels_all,
        key="cmp_a",
        help="Usa a seleção do mapa como padrão, quando houver.",
    )
with right:
    b_lab = st.selectbox(
        "Município B",
        labels_all,
        key="cmp_b",
    )

cmp = compare_municipalities(
    bundle,
    label_to_code[a_lab],
    label_to_code[b_lab],
)
if not cmp.get("ok"):
    st.warning(cmp.get("message", "Comparação indisponível."))
else:
    ca, cb = st.columns(2)
    with ca:
        st.markdown(f"**{cmp['a']['name']}** (`{cmp['a']['code']}`)")
        st.write(f"Área IBGE: **{cmp['a']['area_km2']:.3f} km²**")
    with cb:
        st.markdown(f"**{cmp['b']['name']}** (`{cmp['b']['code']}`)")
        st.write(f"Área IBGE: **{cmp['b']['area_km2']:.3f} km²**")
    if cmp.get("area_km2_delta_a_minus_b") is not None:
        st.write(
            f"Diferença de área (A − B): "
            f"**{cmp['area_km2_delta_a_minus_b']:.3f} km²**"
        )
    st.caption(str(cmp["area_source"]))
    st.warning(str(cmp["disclaimer_pt"]))

    report = {
        "produto": "comparacao_territorial_parana",
        "fonte": "IBGE Malha Municipal Digital",
        "edicao": bundle.provenance.get("edition"),
        "comparacao": cmp,
        "aviso": "Não é aptidão solar nem ranking comercial.",
    }
    st.download_button(
        "Baixar comparação (JSON)",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name=f"comparacao_{cmp['a']['code']}_{cmp['b']['code']}.json",
        mime="application/json",
    )

render_footer()
