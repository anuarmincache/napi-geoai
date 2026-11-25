"""Painel energético — empreendimentos de geração SIGA/ANEEL (MVP 10)."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_aggregate import PHASE_OPERACAO
from geoai.portal import (
    compare_municipal_energy,
    energy_attribution_lines,
    energy_map_html,
    energy_public_notice,
    list_municipalities,
    municipalities_ranked,
    municipality_generation_mix,
    municipality_label,
    search_municipalities,
)
from geoai.portal.energy_panel import (
    energy_scope_totals,
    escopo_em_portugues,
    project_municipality_metrics,
)
from geoai.portal.formatos import data_br, rotulo_tecnologia
from geoai.portal.textos_legados import atualizar
from geoai.presentation import AudienceLevel

from _bootstrap import (
    br_num,
    cached_energy_panel,
    cached_municipality_layer,
    configure_page,
    page_header,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Energia — SIGA/ANEEL")
sidebar_brand()

page_header(
    "Usinas e geração centralizada",
    "Usinas em operação no Paraná por município e tecnologia, segundo a ANEEL.",
    art_kind="grid",
    eyebrow="Energia",
)
st.caption(
    "Potência **fiscalizada** das usinas de grande porte do Paraná, em MW. "
    "Potência é o tamanho da usina, **não** a energia que ela gerou (MWh). "
    "Município sem usina no mapa não é ausência comprovada, e nada aqui "
    "indica aptidão solar."
)

mun = cached_municipality_layer()
energy = cached_energy_panel()
if not mun.validated_for_map:
    st.error(mun.missing_reason_pt or "Malha municipal indisponível.")
    render_footer()
    st.stop()
if not energy.available:
    st.error(energy.missing_reason_pt or "Painel SIGA indisponível.")
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
tipos = sorted(
    {
        t
        for m in (energy.panel.get("municipalities") or [])
        for t in (m.get("por_tipo") or {})
    }
)
f1, f2 = st.columns([2, 1])
with f1:
    tipo = st.selectbox(
        "Tecnologia de geração",
        options=["(todas)", *tipos],
        format_func=lambda v: v if v == "(todas)" else rotulo_tecnologia(v),
        help=(
            "Os indicadores, a lista e o mapa passam a considerar só a "
            "tecnologia escolhida. A lista de municípios continua com os 399. "
            "A sigla entre parênteses é a que a ANEEL usa no cadastro."
        ),
    )
with f2:
    st.selectbox(
        "Fase",
        options=[PHASE_OPERACAO],
        help="Esta página mostra só usinas em operação.",
        disabled=True,
    )

tipo_filter = None if tipo == "(todas)" else tipo
scope = energy_scope_totals(energy, tipo=tipo_filter)
n_un = int(scope["n_empreendimentos_nao_associados"])

if level is AudienceLevel.BASIC:
    st.info(
        "O mapa mostra a potência das usinas em operação em cada município, "
        "segundo a ANEEL. Cinza claro significa que nenhuma usina com "
        "localização conhecida foi associada ao município. Isso não prova que "
        f"não exista usina ali: {n_un} usina(s) não puderam ser localizadas "
        "em um município."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "Potência fiscalizada, potência outorgada e energia gerada são "
        f"coisas diferentes. Fase considerada: {PHASE_OPERACAO}. Cada usina "
        "é associada ao município pelas coordenadas, com conferência por dois "
        "métodos independentes. O filtro de tecnologia vale para indicadores, "
        "lista e mapa."
    )
else:
    st.info(
        "Artefatos: `siga_pr_energy_panel.json`, proveniência/qualidade, "
        "`siga_pr_qgis_join_report.json` (assignments). "
        "MMGD: pipeline derivado separado — não misturar com SIGA."
    )

if tipo_filter:
    st.info(
        f"Escopo ativo: tecnologia **{tipo_filter}** "
        f"(`{scope['metric_scope']}`). "
        "Indicadores, lista, comparação e mapa referem-se só a este tipo."
    )
else:
    st.caption(
        "Escopo ativo: **todas as tecnologias** na fase Operação "
        f"(`{scope['metric_scope']}`)."
    )

notice = energy_public_notice(energy)
st.warning(notice["notice_pt"])
st.caption(
    "Fonte: ANEEL, cadastro SIGA, sobre a Malha Municipal IBGE 2025. "
    f"Conjunto de dados de {data_br(notice['dat_conjunto'])}, "
    f"baixado em {data_br(notice['retrieved_at'])} e preparado em "
    f"{data_br(notice['prepared_at'])}."
)
if tipo_filter:
    st.warning(atualizar(scope["nao_associados_limitation_pt"]) or "")

c1, c2, c3, c4 = st.columns(4)
# O recorte em uso não se repete nos quatro rótulos: ele já está na legenda
# logo abaixo, e repetido aqui estourava a largura do cartão e era cortado.
c1.metric("Usinas em operação", br_num(scope["n_empreendimentos_fase"]))
c2.metric(
    "Potência fiscalizada (MW)",
    br_num(scope["potencia_fiscalizada_mw_conhecida_fase"], 1),
)
c3.metric(
    "Municípios com usinas", br_num(scope["n_municipios_com_usinas"])
)
c4.metric(
    "Municípios no Paraná",
    f"{scope['municipality_count']}/{EXPECTED_PR_MUNICIPALITY_COUNT}",
)
st.caption(scope["kpi_caption_pt"])
st.caption(
    "Todos os registros deste recorte têm potência declarada."
    if not scope["n_potencia_fiscalizada_ausente_fase"]
    else (
        f"{scope['n_potencia_fiscalizada_ausente_fase']} registros deste "
        "recorte não declaram potência e ficam fora da soma."
    )
)
if scope.get("totals_caveat_pt"):
    st.warning(scope["totals_caveat_pt"])

ranked = municipalities_ranked(
    energy,
    only_with_plants=True,
    tipo=tipo_filter,
    limit=20,
)

all_recs = list_municipalities(mun)
label_to_code = {municipality_label(r): r.code for r in all_recs}
code_to_label = {c: lab for lab, c in label_to_code.items()}
labels_all = list(label_to_code.keys())

default_code = ranked[0]["CD_MUN"] if ranked else all_recs[0].code
if "energy_code" not in st.session_state:
    st.session_state.energy_code = default_code
if "energy_query" not in st.session_state:
    st.session_state.energy_query = ""

rank_labels = [
    f"{r['NM_MUN']} ({r['CD_MUN']}) — {br_num(r['display_mw'], 1)} MW"
    for r in ranked
]
rank_codes = [r["CD_MUN"] for r in ranked]


def _select_municipality(code: str) -> None:
    st.session_state.energy_code = code
    label = code_to_label.get(code)
    if label:
        st.session_state.energy_city = label


def _on_city_change() -> None:
    label = st.session_state.get("energy_city")
    if label in label_to_code:
        st.session_state.energy_code = label_to_code[label]


def _on_rank_change() -> None:
    label = st.session_state.get("energy_rank")
    if label in rank_labels:
        _select_municipality(rank_codes[rank_labels.index(label)])


def _clear_energy_search() -> None:
    st.session_state.energy_query = ""


def _format_mw(value: object) -> str:
    if value is None:
        return "não informada"
    return f"{br_num(value, 1)} MW"


query = str(st.session_state.energy_query or "")
hits = search_municipalities(mun, query, limit=None)
hit_labels = [municipality_label(rec) for rec in hits]
current_label = code_to_label.get(str(st.session_state.energy_code))
if current_label and current_label not in hit_labels:
    city_options = [current_label, *hit_labels]
else:
    city_options = hit_labels or labels_all
if "energy_city" not in st.session_state or (
    st.session_state.energy_city not in city_options and current_label
):
    st.session_state.energy_city = current_label or city_options[0]
if st.session_state.energy_city in label_to_code:
    st.session_state.energy_code = label_to_code[st.session_state.energy_city]

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Buscar município")
    st.caption(
        f"Os **{EXPECTED_PR_MUNICIPALITY_COUNT}** municípios do Paraná "
        "podem ser escolhidos. O ranking abaixo só destaca os 20 maiores."
    )
    st.text_input(
        "Nome ou código IBGE",
        key="energy_query",
        placeholder="Ex.: Maringá ou 4115200",
    )
    st.button("Limpar busca", on_click=_clear_energy_search)
    st.markdown(f"**{len(hits)} de {EXPECTED_PR_MUNICIPALITY_COUNT}** municípios")
    if query.strip() and not hits:
        st.warning("Nenhum município encontrado para esta busca.")
    st.selectbox(
        "Município no mapa",
        options=city_options,
        key="energy_city",
        on_change=_on_city_change,
    )

    st.markdown("#### Ranking (MW fiscalizada no escopo)")
    if not rank_labels:
        st.warning("Nenhum município com empreendimentos no filtro.")
    else:
        st.selectbox(
            "20 maiores (atalho)",
            options=rank_labels,
            key="energy_rank",
            on_change=_on_rank_change,
            help="Atalho. A busca acima alcança qualquer município.",
        )

with left:
    st.markdown(
        """
        <style>
        iframe[title="streamlit_html"] {
          background: #e8eef5 !important; border: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.spinner("Renderizando mapa energético…"):
        try:
            html = energy_map_html(
                mun,
                energy,
                selected_code=st.session_state.energy_code,
                tipo=tipo_filter,
            )
            render_html_map(html, height=620)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")

st.subheader("Município em foco")
code = st.session_state.energy_code
by_code = {
    str(item["CD_MUN"]): item
    for item in (energy.panel.get("municipalities") or [])
}
raw = by_code.get(str(code)) if code else None
row = project_municipality_metrics(raw, tipo=tipo_filter) if raw else None
mix = municipality_generation_mix(raw, tipo=tipo_filter) if raw else ()
if row:
    st.markdown(f"**{row['NM_MUN']}** · código IBGE `{row['CD_MUN']}`")
    m1, m2, m3 = st.columns(3)
    m1.metric("Usinas associadas", int(row["display_n"]))
    m2.metric("Potência fiscalizada (MW)", _format_mw(row["display_mw"]))
    m3.metric("Potência outorgada (MW)", _format_mw(row.get("display_outorgada_mw")))
    st.caption(
        "Fiscalizada e outorgada são potências distintas, em MW. "
        "Nenhuma das duas é energia gerada em MWh."
    )
    if row.get("display_ausente"):
        st.caption(
            f"{row['display_ausente']} registro(s) sem potência "
            "fiscalizada válida neste escopo."
        )
    if level == AudienceLevel.TECHNICAL:
        st.caption(f"Escopo métrica: `{row.get('metric_scope')}`")
    if int(row["display_n"]) == 0:
        st.caption(
            "Nenhuma usina associada a este município no escopo. "
            "Isso não prova ausência absoluta de usinas."
        )
    elif row.get("zero_semantics") and not tipo_filter:
        st.caption(row["zero_semantics"])

    st.markdown("##### Composição por tipo de geração")
    if not mix:
        st.caption("Nenhuma usina associada neste escopo.")
    else:
        chart = pd.DataFrame(mix)
        chart["tipo"] = chart["tipo"].map(rotulo_tecnologia)
        chart = chart.set_index("tipo")
        st.bar_chart(
            chart[["potencia_fiscalizada_mw"]].rename(
                columns={"potencia_fiscalizada_mw": "Potência fiscalizada (MW)"}
            )
        )
        st.caption(
            "A barra mostra só a potência fiscalizada (MW) das usinas "
            "associadas a este município."
        )
        for item in mix:
            st.write(
                f"- {item['tipo']}: {item['n']} usina(s) · "
                "fiscalizada "
                f"{_format_mw(item['potencia_fiscalizada_mw'])} · "
                "outorgada "
                f"{_format_mw(item['potencia_outorgada_mw'])}"
            )

with st.expander("Fonte e metodologia", expanded=True):
    for line in energy_attribution_lines(energy):
        st.markdown(f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True)

st.subheader("Comparação municipal (capacidade fiscalizada no escopo)")
if st.session_state.energy_code and st.session_state.energy_code in code_to_label:
    preferred = code_to_label[st.session_state.energy_code]
else:
    preferred = labels_all[0]
if "energy_cmp_a" not in st.session_state:
    st.session_state.energy_cmp_a = preferred
if st.session_state.energy_cmp_a not in labels_all:
    st.session_state.energy_cmp_a = preferred
if "energy_cmp_b" not in st.session_state:
    alt = next(
        (code_to_label[c] for c in rank_codes if code_to_label.get(c) != preferred),
        labels_all[min(1, len(labels_all) - 1)],
    )
    st.session_state.energy_cmp_b = alt

ca, cb = st.columns(2)
with ca:
    a_lab = st.selectbox("Município A", labels_all, key="energy_cmp_a")
with cb:
    b_lab = st.selectbox("Município B", labels_all, key="energy_cmp_b")

cmp = compare_municipal_energy(
    energy,
    label_to_code[a_lab],
    label_to_code[b_lab],
    tipo=tipo_filter,
)
if not cmp.get("ok"):
    st.warning(cmp.get("message"))
else:
    x, y = st.columns(2)
    with x:
        st.markdown(f"**{cmp['a']['NM_MUN']}** (`{cmp['a']['CD_MUN']}`)")
        st.write(
            f"Fiscalizada: **{_format_mw(cmp['a']['display_mw'])}** · "
            f"Outorgada: **{_format_mw(cmp['a'].get('display_outorgada_mw'))}** · "
            f"n={cmp['a']['display_n']} · {cmp['a']['status_dados']}"
        )
    with y:
        st.markdown(f"**{cmp['b']['NM_MUN']}** (`{cmp['b']['CD_MUN']}`)")
        st.write(
            f"Fiscalizada: **{_format_mw(cmp['b']['display_mw'])}** · "
            f"Outorgada: **{_format_mw(cmp['b'].get('display_outorgada_mw'))}** · "
            f"n={cmp['b']['display_n']} · {cmp['b']['status_dados']}"
        )
    st.write(
        "Diferença do primeiro para o segundo: "
        f"**{br_num(cmp['delta_fiscalizada_mw_a_minus_b'], 1)} MW** e "
        f"**{br_num(cmp['delta_n_a_minus_b'])} usinas**, em "
        f"{escopo_em_portugues(cmp['metric_scope'])}."
    )
    st.warning(cmp["disclaimer_pt"])
    st.download_button(
        "Baixar comparação (JSON)",
        data=json.dumps(cmp, ensure_ascii=False, indent=2),
        file_name=(
            f"energia_cmp_{cmp['a']['CD_MUN']}_{cmp['b']['CD_MUN']}.json"
        ),
        mime="application/json",
    )

st.download_button(
    "Baixar painel agregado (JSON)",
    data=json.dumps(energy.panel, ensure_ascii=False, indent=2),
    file_name="siga_pr_energy_panel.json",
    mime="application/json",
)

render_footer()
