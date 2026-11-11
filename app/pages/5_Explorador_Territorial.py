"""Explorador territorial interativo — 399 municípios do Paraná."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components
from geoai.portal import (
    compare_municipalities,
    explorer_attribution_lines,
    get_municipality,
    list_municipalities,
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

configure_page("Explorador territorial")
sidebar_brand()

st.title("Explorador territorial do Paraná")
st.caption(
    "Malha municipal oficial IBGE (`municipio_2025`) — 399 municípios. "
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
        "Escolha um município na lista ou use um atalho de cidade-polo. "
        "O mapa destaca a seleção. A comparação usa só nome, código e área "
        "oficial IBGE."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "Geometrias de apresentação são simplificadas (tolerância documentada). "
        "Área vem do campo oficial `AREA_KM2` da malha — não recalculada em graus."
    )
else:
    st.info(
        "Proveniência/SHA/CRS/contagem em `data/derived/parana_municipios_2025.*`. "
        "Alta fidelidade: ZIP IBGE regenerável. Serviços em `geoai.portal` "
        "(independentes do Streamlit)."
    )

all_recs = list_municipalities(bundle)
label_to_code = {f"{r.name} ({r.code})": r.code for r in all_recs}
labels_all = list(label_to_code.keys())
polos = polo_city_records(bundle)
polo_labels = {f"{r.name} ({r.code})": r.code for r in polos}

if "explorer_code" not in st.session_state:
    st.session_state.explorer_code = all_recs[0].code if all_recs else ""

c_search, c_polo = st.columns([2, 1])
with c_search:
    query = st.text_input(
        "Buscar município (nome ou código IBGE)",
        value="",
        help="Acentos são ignorados na busca. A lista abaixo é filtrada.",
    )
    hits = search_municipalities(bundle, query, limit=80)
    filtered_labels = [f"{r.name} ({r.code})" for r in hits] or labels_all
    current_label = next(
        (
            lab
            for lab, code in label_to_code.items()
            if code == st.session_state.explorer_code
        ),
        filtered_labels[0],
    )
    if current_label not in filtered_labels:
        current_label = filtered_labels[0]
    selected_label = st.selectbox(
        "Município selecionado",
        options=filtered_labels,
        index=filtered_labels.index(current_label),
        help="Seleção na lista é obrigatória e suficiente para zoom/destaque.",
    )
    st.session_state.explorer_code = label_to_code[selected_label]

with c_polo:
    st.markdown("#### Cidades-polo (atalhos)")
    st.caption("Cobertura regional — **não** é ranking.")
    polo_choice = st.selectbox(
        "Atalho rápido",
        options=["(nenhum)", *polo_labels.keys()],
    )
    if polo_choice != "(nenhum)":
        st.session_state.explorer_code = polo_labels[polo_choice]
        st.success(f"Atalho aplicado: {polo_choice}")

selected_code = st.session_state.explorer_code

map_col, meta_col = st.columns([2, 1])
with meta_col:
    fill_opacity = st.slider("Opacidade", 0.05, 0.7, 0.25, 0.05)
    line_weight = st.slider("Contorno", 0.5, 3.0, 1.0, 0.5)
    map_height = st.select_slider(
        "Altura (px)",
        options=[420, 520, 620, 720],
        value=620,
    )
    st.markdown("#### Metadados")
    for line in explorer_attribution_lines(bundle):
        st.markdown(f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True)
    rec = get_municipality(bundle, selected_code)
    if rec:
        st.metric("Município", rec.name)
        st.metric("Código IBGE", rec.code)
        st.metric("Área oficial (km²)", f"{rec.area_km2:.3f}")

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
left, right = st.columns(2)
with left:
    a_lab = st.selectbox("Município A", labels_all, index=0, key="cmp_a")
with right:
    default_b = min(1, len(labels_all) - 1)
    b_lab = st.selectbox("Município B", labels_all, index=default_b, key="cmp_b")

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
