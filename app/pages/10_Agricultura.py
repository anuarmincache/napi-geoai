"""Agricultura — moldura territorial IBGE, sem produção inventada."""

from __future__ import annotations

import streamlit as st
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal import (
    agriculture_source_inventory,
    compare_municipalities,
    explorer_attribution_lines,
    list_municipalities,
    municipality_label,
    municipality_map_html,
    search_municipalities,
)

from _bootstrap import (
    cached_municipality_layer,
    configure_page,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Agricultura")
sidebar_brand()

st.title("Agricultura")
st.caption(
    "Consulta territorial do Paraná. Não há produção, área plantada, "
    "rendimento, pecuária ou série temporal agrícola nesta página."
)

inventory = agriculture_source_inventory()
st.subheader("Fontes agrícolas")
for item in inventory:
    if item.validated and item.integrated:
        state = "arquivo validado e integrado como moldura territorial"
    elif item.catalogued and not item.local_file:
        state = "catalogada, sem arquivo local"
    elif not item.catalogued and not item.local_file:
        state = "não catalogada e sem arquivo local"
    else:
        state = "arquivo presente, ainda não validado"
    st.markdown(f"**{item.theme_pt}** — {item.organization}: {state}.")
    st.caption(item.note_pt)

st.warning(
    "PAM, PPM, CONAB e IPARDES estão indisponíveis. "
    "Nenhum indicador agrícola foi calculado."
)

bundle = cached_municipality_layer()
if not bundle.validated_for_map:
    st.error(bundle.missing_reason_pt or "Malha municipal indisponível.")
    render_footer()
    st.stop()

records = list_municipalities(bundle)
label_to_code = {municipality_label(rec): rec.code for rec in records}
code_to_label = {code: label for label, code in label_to_code.items()}
labels = list(label_to_code.keys())

if "agro_query" not in st.session_state:
    st.session_state.agro_query = ""
if "agro_code" not in st.session_state:
    st.session_state.agro_code = None


def _clear_agro_search() -> None:
    st.session_state.agro_query = ""


def _on_city() -> None:
    label = st.session_state.get("agro_city")
    if label in label_to_code:
        st.session_state.agro_code = label_to_code[label]


NONE_SELECTION = "— Mapa geral do Paraná —"

query = str(st.session_state.agro_query or "")
hits = search_municipalities(bundle, query, limit=None)
hit_labels = [municipality_label(rec) for rec in hits]
if query.strip():
    options = hit_labels
else:
    options = [NONE_SELECTION, *hit_labels]
if not options:
    options = [NONE_SELECTION]
current = code_to_label.get(str(st.session_state.agro_code or ""))
if current and current not in options:
    options = [current, *options]
if "agro_city" not in st.session_state or st.session_state.agro_city not in options:
    st.session_state.agro_city = current or options[0]
chosen = st.session_state.agro_city
st.session_state.agro_code = label_to_code.get(chosen)

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Município")
    st.caption(
        f"Catálogo IBGE: **{EXPECTED_PR_MUNICIPALITY_COUNT}** municípios. "
        "A área exibida é o atributo oficial da malha, não área plantada."
    )
    st.text_input(
        "Nome ou código IBGE",
        key="agro_query",
        placeholder="Ex.: Maringá ou 4115200",
    )
    st.button("Limpar busca", on_click=_clear_agro_search)
    st.markdown(f"**{len(hits)} de {EXPECTED_PR_MUNICIPALITY_COUNT}** municípios")
    if query.strip() and not hits:
        st.warning("Nenhum município encontrado para esta busca.")
    if options:
        st.selectbox(
            "Município no mapa",
            options=options,
            key="agro_city",
            on_change=_on_city,
        )

with left:
    with st.spinner("Renderizando malha municipal…"):
        try:
            html = municipality_map_html(
                bundle,
                selected_code=st.session_state.agro_code,
            )
            render_html_map(html, height=560)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")

code = st.session_state.agro_code
selected = next((rec for rec in records if rec.code == code), None)
st.subheader("Território selecionado")
if selected is None:
    st.info("Nenhum município selecionado. O mapa mostra o Paraná.")
else:
    st.markdown(f"**{selected.name}** · código IBGE `{selected.code}`")
    c1, c2 = st.columns(2)
    c1.metric("Código IBGE", selected.code)
    c2.metric("Área oficial (km²)", f"{selected.area_km2:,.3f}")
    st.caption(
        "AREA_KM2 é o campo oficial da Malha Municipal IBGE 2025. "
        "Não representa lavoura, rendimento nem rebanho."
    )
p1, p2, p3, p4 = st.columns(4)
p1.metric("Produção agrícola", "indisponível")
p2.metric("Área plantada", "indisponível")
p3.metric("Rendimento", "indisponível")
p4.metric("Pecuária", "indisponível")

st.subheader("Comparação territorial")
st.caption(
    "A comparação usa somente nome, código e área oficial. "
    "Não compara produção nem produtividade."
)
if "agro_cmp_a" not in st.session_state:
    st.session_state.agro_cmp_a = labels[0]
if "agro_cmp_b" not in st.session_state:
    st.session_state.agro_cmp_b = labels[min(1, len(labels) - 1)]
ca, cb = st.columns(2)
with ca:
    a_label = st.selectbox("Município A", labels, key="agro_cmp_a")
with cb:
    b_label = st.selectbox("Município B", labels, key="agro_cmp_b")
compared = compare_municipalities(
    bundle,
    label_to_code[a_label],
    label_to_code[b_label],
)
if not compared.get("ok"):
    st.warning(compared.get("message"))
else:
    xa, xb = st.columns(2)
    with xa:
        st.markdown(f"**{compared['a']['name']}**")
        st.write(f"Área oficial: **{compared['a']['area_km2']:,.3f} km²**")
    with xb:
        st.markdown(f"**{compared['b']['name']}**")
        st.write(f"Área oficial: **{compared['b']['area_km2']:,.3f} km²**")
    delta = compared["area_km2_delta_a_minus_b"]
    st.write(f"Δ área oficial (A−B): **{delta:,.3f} km²**")
    st.warning(compared["disclaimer_pt"])

st.subheader("Fonte, referência e método")
for line in explorer_attribution_lines(bundle):
    st.caption(line)
st.caption(
    "Próximo dado: tabela PAM municipal, com código IBGE conferido contra "
    "os 399. Cultura sem registro permanece sem registro. Série temporal "
    "só depois de dois anos validados no arquivo."
)

render_footer()
