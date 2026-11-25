"""Agricultura — PAM e PPM (IBGE/SIDRA) quando o artefato existe.

Sem o artefato derivado, a página mostra apenas a moldura territorial e
marca os indicadores como indisponíveis. Nenhum valor é inventado.
"""

from __future__ import annotations

import pandas as pd
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
from geoai.portal.agro_panel import (
    PAM_LABELS_PT,
    PPM_LABELS_PT,
    STATUS_LABELS_PT,
    agro_attribution_lines,
    agro_cell,
    agro_format_cell,
    agro_indicator,
    agro_map_html,
    agro_ranked,
    agro_state_summary,
    list_agro_crops,
)
from geoai.portal.textos_legados import atualizar_lista

from _bootstrap import (
    br_num,
    cached_agro_panel,
    cached_municipality_layer,
    configure_page,
    page_header,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Agricultura")
sidebar_brand()

page_header(
    "Agricultura e pecuária",
    "Lavouras, rebanhos e leite nos 399 municípios, com dados do IBGE.",
    art_kind="agro",
    eyebrow="Território",
    banner="banner-agricultura.webp",
    banner_alt="Trator em lavoura de soja, silos e rebanho bovino",
    chips=(
        "Lavouras",
        "Rebanhos",
        "Leite",
        "Rendimento",
        "Por município",
    ),
)
agro = cached_agro_panel()
if agro.available:
    st.caption(
        "Lavouras e pecuária dos 399 municípios do Paraná, com dados oficiais "
        "do IBGE (PAM e PPM). Valores do último ano publicado, sem série "
        "temporal e sem estimativa."
    )
else:
    st.caption(
        "Consulta territorial do Paraná. Não há produção, área plantada, "
        "rendimento, pecuária ou série temporal agrícola nesta página."
    )

inventory = agriculture_source_inventory()
_sources = st.expander(
    "Fontes agrícolas e situação de cada uma", expanded=not agro.available
)
for item in inventory:
    if item.validated and item.integrated:
        state = "arquivo validado e integrado como moldura territorial"
    elif item.catalogued and not item.local_file:
        state = "catalogada, sem arquivo local"
    elif not item.catalogued and not item.local_file:
        state = "não catalogada e sem arquivo local"
    else:
        state = "arquivo presente, ainda não validado"
    _sources.markdown(f"**{item.theme_pt}** — {item.organization}: {state}.")
    _sources.caption(item.note_pt)

if agro.available:
    st.warning(
        "CONAB e IPARDES estão indisponíveis. PAM e PPM vêm do IBGE/SIDRA. "
        "Efetivo de rebanho não é resíduo disponível para biogás, e área "
        "plantada não indica viabilidade de negócio."
    )
else:
    st.warning(
        "PAM, PPM, CONAB e IPARDES estão indisponíveis. "
        "Nenhum indicador agrícola foi calculado."
    )
    if agro.missing_reason_pt:
        st.caption(agro.missing_reason_pt)

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

indicator = None
crop_id = None
herd_key = "suinos"
if agro.available:
    crops = list_agro_crops(agro)
    crop_names = {str(c["id"]): str(c["name"]) for c in crops}
    s1, s2, s3 = st.columns([1, 1.4, 1.4])
    with s1:
        theme = st.radio(
            "Tema do mapa", ["Lavouras", "Pecuária"], horizontal=True, key="agro_theme"
        )
    with s2:
        crop_id = st.selectbox(
            "Cultura",
            options=list(crop_names),
            format_func=lambda c: crop_names[c],
            key="agro_crop",
            help=agro.panel["pam"]["crop_selection_rule_pt"],
        )
        pam_key = st.selectbox(
            "Variável da lavoura",
            options=list(PAM_LABELS_PT),
            format_func=lambda k: PAM_LABELS_PT[k],
            key="agro_pam_var",
        )
    with s3:
        herd_key = st.selectbox(
            "Rebanho ou produto",
            options=list(PPM_LABELS_PT),
            index=list(PPM_LABELS_PT).index("suinos"),
            format_func=lambda k: PPM_LABELS_PT[k],
            key="agro_herd",
        )
    indicator = (
        agro_indicator(agro, "pam", pam_key, crop_id)
        if theme == "Lavouras"
        else agro_indicator(agro, "ppm", herd_key)
    )
    st.caption(
        f"No mapa: **{indicator.label_pt}** ({indicator.unit}), ano "
        f"**{indicator.year}**. {indicator.source_pt}. Cinza tracejado = sem "
        "valor publicado."
    )

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
            if indicator is not None:
                html = agro_map_html(
                    bundle,
                    agro,
                    indicator,
                    selected_code=st.session_state.agro_code,
                )
            else:
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
    c2.metric("Área oficial (km²)", f"{br_num(selected.area_km2, 1)}")
    st.caption(
        "A área é o valor oficial da Malha Municipal do IBGE de 2025. "
        "Não representa lavoura, rendimento nem rebanho."
    )
p1, p2, p3, p4 = st.columns(4)
if not agro.available:
    p1.metric("Produção agrícola", "indisponível")
    p2.metric("Área plantada", "indisponível")
    p3.metric("Rendimento", "indisponível")
    p4.metric("Pecuária", "indisponível")
else:
    scope = selected.name if selected is not None else "Paraná"
    ind_prod = agro_indicator(agro, "pam", "producao", crop_id)
    ind_area = agro_indicator(agro, "pam", "area_plantada", crop_id)
    ind_rend = agro_indicator(agro, "pam", "rendimento", crop_id)
    ind_herd = agro_indicator(agro, "ppm", herd_key)

    def _shown(ind) -> str:
        if selected is not None:
            return agro_format_cell(*agro_cell(agro, selected.code, ind), "").strip()
        if not ind.summable:
            return "ver por município"
        total = agro_state_summary(agro, ind)["soma_publicada"]
        return agro_format_cell(float(total), "valor", "").strip()

    crop_label = crop_names[crop_id]
    p1.metric("Produção agrícola", _shown(ind_prod), help=ind_prod.label_pt)
    p2.metric("Área plantada", _shown(ind_area), help=ind_area.label_pt)
    p3.metric("Rendimento", _shown(ind_rend), help=ind_rend.label_pt)
    p4.metric("Pecuária", _shown(ind_herd), help=ind_herd.label_pt)
    st.caption(
        f"Recorte: **{scope}**. Lavoura: **{crop_label}**, PAM "
        f"{ind_prod.year}. Pecuária: **{PPM_LABELS_PT[herd_key]}**, PPM "
        f"{ind_herd.year}. Unidades: produção em {ind_prod.unit}, área em "
        f"{ind_area.unit}, rendimento em {ind_rend.unit}, pecuária em "
        f"{ind_herd.unit}. "
        + (
            "No Paraná, a soma considera apenas valores municipais publicados."
            if selected is None
            else "Dado oficial, registrado direto na fonte."
        )
    )

    if selected is not None:
        t1, t2 = st.columns([1.6, 1])
        with t1:
            st.markdown("##### Lavouras no município")
            rows = []
            for crop in crops:
                line = {"Cultura": crop["name"]}
                for key, label in PAM_LABELS_PT.items():
                    ind = agro_indicator(agro, "pam", key, str(crop["id"]))
                    line[f"{label} ({ind.unit})"] = agro_format_cell(
                        *agro_cell(agro, selected.code, ind), ""
                    ).strip()
                rows.append(line)
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        with t2:
            st.markdown("##### Pecuária no município")
            rows = []
            for key, label in PPM_LABELS_PT.items():
                ind = agro_indicator(agro, "ppm", key)
                rows.append(
                    {
                        "Indicador": label,
                        "Valor": agro_format_cell(
                            *agro_cell(agro, selected.code, ind), ind.unit
                        ),
                        "Ano": ind.year,
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.subheader("Maiores valores municipais")
    names_by_code = {rec.code: rec.name for rec in records}
    top = agro_ranked(agro, indicator, names_by_code, limit=10)
    if not top:
        st.info("Nenhum município com valor publicado para este indicador.")
    else:
        top_df = pd.DataFrame(top).rename(
            columns={
                "NM_MUN": "Município",
                "CD_MUN": "Código IBGE",
                "valor": f"{indicator.label_pt} ({indicator.unit})",
            }
        )[["Município", "Código IBGE", f"{indicator.label_pt} ({indicator.unit})"]]
        st.dataframe(top_df, hide_index=True, width="stretch")
    summary = agro_state_summary(agro, indicator)
    counts = summary.get("contagem_por_status") or {}
    st.caption(
        "Ordenação descritiva do ano de referência, não é ranking de "
        "investimento. Situação dos 399 municípios neste indicador: "
        + "; ".join(
            f"{STATUS_LABELS_PT.get(k, k)}: {v}" for k, v in counts.items() if v
        )
        + "."
    )
    export = []
    for rec in records:
        value, status = agro_cell(agro, rec.code, indicator)
        export.append(
            {
                "CD_MUN": rec.code,
                "NM_MUN": rec.name,
                "indicador": indicator.label_pt,
                "unidade": indicator.unit,
                "ano": indicator.year,
                "valor": value,
                "situacao": STATUS_LABELS_PT.get(status, status),
                "fonte": indicator.source_pt,
            }
        )
    st.download_button(
        "Baixar este indicador dos 399 municípios (CSV)",
        pd.DataFrame(export).to_csv(index=False).encode("utf-8-sig"),
        file_name="napi_geoai_agro_indicador.csv",
        mime="text/csv",
    )

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
        st.write(f"Área oficial: **{br_num(compared['a']['area_km2'], 1)} km²**")
    with xb:
        st.markdown(f"**{compared['b']['name']}**")
        st.write(f"Área oficial: **{br_num(compared['b']['area_km2'], 1)} km²**")
    delta = compared["area_km2_delta_a_minus_b"]
    st.write(
        f"Diferença de área oficial: **{br_num(abs(delta), 1)} km²** "
        + ("a mais no primeiro" if delta >= 0 else "a mais no segundo")
    )
    st.warning(compared["disclaimer_pt"])

st.subheader("Fonte, referência e método")
for line in explorer_attribution_lines(bundle):
    st.caption(line)
if agro.available:
    for line in agro_attribution_lines(agro):
        st.caption(line)
    for line in atualizar_lista(agro.panel.get("notices_pt")):
        st.caption(line)
else:
    st.caption(
        "Próximo dado: tabela PAM municipal, com código IBGE conferido contra "
        "os 399. Cultura sem registro permanece sem registro. Série temporal "
        "só depois de dois anos validados no arquivo."
    )

render_footer()
