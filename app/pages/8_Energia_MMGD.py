"""Painel MMGD/ANEEL — micro e minigeração distribuída (MVP 14)."""

from __future__ import annotations

import json
import time

import streamlit as st
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal import (
    list_municipalities,
    municipality_label,
    search_municipalities,
)
from geoai.portal.mmgd_panel import (
    compare_municipal_mmgd,
    list_mmgd_filter_options,
    mmgd_attribution_lines,
    mmgd_map_html,
    mmgd_public_notice,
    mmgd_ranked,
    mmgd_scope_totals,
    project_mmgd_metrics,
)
from geoai.portal.textos_legados import atualizar, atualizar_lista
from geoai.presentation import AudienceLevel

from _bootstrap import (
    br_num,
    cached_mmgd_panel,
    cached_municipality_layer,
    configure_page,
    page_header,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Energia — MMGD/ANEEL")
sidebar_brand()

page_header(
    "Solar e geração distribuída",
    "Instalações de micro e minigeração por município, segundo a ANEEL.",
    art_kind="solar",
    eyebrow="Energia",
)
st.caption(
    "Potência **instalada** da geração distribuída do Paraná, em MW. A "
    "contagem principal é de **instalações**. As unidades que recebem "
    "crédito são consumidores beneficiados, não instalações, e aparecem "
    "como número secundário. Potência **não** é energia gerada (MWh), não "
    "se soma às usinas de grande porte e não indica aptidão solar."
)

t_load0 = time.perf_counter()
mun = cached_municipality_layer()
mmgd = cached_mmgd_panel()
t_load = time.perf_counter() - t_load0

if not mun.validated_for_map:
    st.error(mun.missing_reason_pt or "Malha municipal indisponível.")
    render_footer()
    st.stop()
if not mmgd.available:
    st.error(mmgd.missing_reason_pt or "Painel MMGD indisponível.")
    st.info(
        "Os dados de geração distribuída desta versão não estão disponíveis. "
        "Nenhum número é exibido no lugar deles."
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

opts = list_mmgd_filter_options(mmgd)
none = "(todas)"
f1, f2, f3 = st.columns(3)
with f1:
    tipo_sel = st.selectbox(
        "Tecnologia de geração",
        options=[none, *opts["tipo"]],
        help="Um filtro categórico por vez. Redefine contagens e mapa.",
    )
with f2:
    classe_sel = st.selectbox(
        "Classe de consumo",
        options=[none, *opts["classe"]],
    )
with f3:
    porte_sel = st.selectbox(
        "Porte",
        options=[none, *opts["porte"]],
    )

tipo_filter = None if tipo_sel == none else str(tipo_sel)
classe_filter = None if classe_sel == none else str(classe_sel)
porte_filter = None if porte_sel == none else str(porte_sel)

scope = mmgd_scope_totals(
    mmgd,
    tipo=tipo_filter,
    classe=classe_filter,
    porte=porte_filter,
)
notice = mmgd_public_notice(mmgd)

st.caption(
    "Fonte ANEEL MMGD · período "
    f"{notice['periodo_referencia']} · conjunto {notice['dat_conjunto']} · "
    f"recuperado {notice['retrieved_at']} · painel {notice['prepared_at']} · "
    "licença ODbL."
)
if level != AudienceLevel.BASIC:
    st.info(
        "Redistribuição/derivação sujeitas aos termos ODbL "
        "(atribuição e share-alike quando aplicável). "
        "Detalhes em Fonte e metodologia."
    )

if level == AudienceLevel.BASIC:
    st.warning(
        "MMGD é a geração distribuída: sistemas pequenos, quase todos solares, "
        "instalados em casas, comércios e propriedades rurais. Os números são "
        "de potência instalada (MW), não de energia gerada (MWh), e não se "
        "somam aos das usinas da página de geração centralizada."
    )
    st.caption(
        "O retrato é de um mês específico. A data de atualização do cadastro "
        "não é a data em que a instalação foi ligada, então esta página não "
        "mostra crescimento ao longo do tempo."
    )
else:
    st.warning(notice["notice_pt"])
    st.warning(
        str(atualizar(notice.get("temporal_note_pt")) or "")
    + " Anos em `by_cadastral_update_year` **não** são apresentados como "
    "crescimento de conexões."
)

if not scope.get("filter_ok", True):
    st.error(scope.get("kpi_caption_pt") or "Filtros incompatíveis.")
    st.info(scope.get("filter_note_pt") or "")
else:
    if scope.get("filter_note_pt"):
        st.info(scope["filter_note_pt"])

    c1, c2, c3, c4 = st.columns(4)
    scope_lab = scope["metric_scope"]
    c1.metric(
        f"Empreendimentos ({scope_lab})",
        (
            f"{scope['n_empreendimentos']:,}".replace(",", ".")
            if scope["n_empreendimentos"] is not None
            else "n/d"
        ),
    )
    mw = scope.get("potencia_instalada_mw_conhecida")
    c2.metric(
        f"MW instalada conhecida ({scope_lab})",
        br_num(mw, 1) if mw is not None else "n/d no filtro",
        help="Disponível no escopo total; ausente nos filtros categóricos.",
    )
    uc = scope.get("qtd_uc_recebe_credito_total")
    c3.metric(
        "Unidades que recebem crédito",
        f"{uc:,}".replace(",", ".") if uc is not None else "n/d no filtro",
        help=(
            "Consumidores que recebem crédito da energia gerada. Um mesmo "
            "sistema pode dividir crédito com várias unidades, então este "
            "número não conta instalações."
        ),
    )
    c4.metric(
        "Municípios com registros",
        (
            f"{scope['n_municipios_com_registros']}/"
            f"{EXPECTED_PR_MUNICIPALITY_COUNT}"
            if scope["n_municipios_com_registros"] is not None
            else "n/d"
        ),
    )
    st.caption(scope["kpi_caption_pt"])

ranked = mmgd_ranked(
    mmgd,
    tipo=tipo_filter,
    classe=classe_filter,
    porte=porte_filter,
    limit=20,
)

all_recs = list_municipalities(mun)
label_to_code = {municipality_label(r): r.code for r in all_recs}
code_to_label = {c: lab for lab, c in label_to_code.items()}
labels_all = list(label_to_code.keys())

default_code = ranked[0]["CD_MUN"] if ranked else all_recs[0].code
if "mmgd_code" not in st.session_state:
    st.session_state.mmgd_code = default_code
if "mmgd_query" not in st.session_state:
    st.session_state.mmgd_query = ""

if scope.get("mw_available_in_scope"):
    rank_labels = [
        f"{r['NM_MUN']} ({r['CD_MUN']}) — "
        f"{br_num(r.get('display_mw') or 0, 1)} MW"
        for r in ranked
    ]
else:
    rank_labels = [
        f"{r['NM_MUN']} ({r['CD_MUN']}) — {int(r.get('display_n') or 0)} emp."
        for r in ranked
    ]
rank_codes = [r["CD_MUN"] for r in ranked]


def _select_municipality(code: str) -> None:
    st.session_state.mmgd_code = code
    label = code_to_label.get(code)
    if label:
        st.session_state.mmgd_city = label


def _on_city_change() -> None:
    label = st.session_state.get("mmgd_city")
    if label in label_to_code:
        st.session_state.mmgd_code = label_to_code[label]


def _on_rank_change() -> None:
    label = st.session_state.get("mmgd_rank")
    if label in rank_labels:
        _select_municipality(rank_codes[rank_labels.index(label)])


def _clear_mmgd_search() -> None:
    st.session_state.mmgd_query = ""


query = str(st.session_state.mmgd_query or "")
hits = search_municipalities(mun, query, limit=None)
hit_labels = [municipality_label(rec) for rec in hits]
current_label = code_to_label.get(str(st.session_state.mmgd_code))
if current_label and current_label not in hit_labels:
    city_options = [current_label, *hit_labels]
else:
    city_options = hit_labels or labels_all
if "mmgd_city" not in st.session_state or (
    st.session_state.mmgd_city not in city_options and current_label
):
    st.session_state.mmgd_city = current_label or city_options[0]
if st.session_state.mmgd_city in label_to_code:
    st.session_state.mmgd_code = label_to_code[st.session_state.mmgd_city]

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Buscar município")
    st.caption(
        f"Os **{EXPECTED_PR_MUNICIPALITY_COUNT}** municípios do Paraná. "
        "O ranking é descritivo (potência/quantidade), não de investimento."
    )
    st.text_input(
        "Nome ou código IBGE",
        key="mmgd_query",
        placeholder="Ex.: Maringá ou 4115200",
    )
    st.button("Limpar busca", on_click=_clear_mmgd_search)
    st.markdown(f"**{len(hits)} de {EXPECTED_PR_MUNICIPALITY_COUNT}** municípios")
    if query.strip() and not hits:
        st.warning("Nenhum município encontrado para esta busca.")
    st.selectbox(
        "Município no mapa",
        options=city_options,
        key="mmgd_city",
        on_change=_on_city_change,
    )
    st.markdown("#### Ranking descritivo (atalho)")
    if not rank_labels:
        st.warning("Nenhum município com empreendimentos no filtro.")
    else:
        st.selectbox(
            "20 maiores no escopo",
            options=rank_labels,
            key="mmgd_rank",
            on_change=_on_rank_change,
        )

with left:
    t_map0 = time.perf_counter()
    with st.spinner("Renderizando mapa MMGD…"):
        try:
            html = mmgd_map_html(
                mun,
                mmgd,
                selected_code=st.session_state.mmgd_code,
                tipo=tipo_filter,
                classe=classe_filter,
                porte=porte_filter,
            )
            render_html_map(html, height=620)
            if level == AudienceLevel.TECHNICAL:
                st.caption(
                    f"Artefatos carregados em {t_load * 1000:.0f} ms · mapa "
                    f"gerado em {(time.perf_counter() - t_map0) * 1000:.0f} ms"
                )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa MMGD: {exc}")

st.subheader("Município em foco")
code = st.session_state.mmgd_code
mun_rows = mmgd.panel.get("municipalities") or []
by_code = {str(item["CD_MUN"]): item for item in mun_rows}
raw = by_code.get(str(code))
if raw is None:
    st.warning("Município sem linha no painel MMGD.")
else:
    proj = project_mmgd_metrics(
        raw,
        tipo=tipo_filter,
        classe=classe_filter,
        porte=porte_filter,
    )
    st.markdown(
        f"**{proj.get('NM_MUN') or code_to_label.get(code, code)}** · "
        f"código IBGE `{code}`"
    )
    m1, m2, m3 = st.columns(3)
    n_disp = proj.get("display_n")
    m1.metric(
        "Empreendimentos (escopo)",
        n_disp if n_disp is not None else "n/d",
    )
    m2.metric(
        "MW instalada conhecida",
        (
            br_num(proj["display_mw"], 2)
            if proj.get("display_mw") is not None
            else "n/d no filtro"
        ),
    )
    m3.metric(
        "Unidades que recebem crédito",
        (
            f"{int(raw.get('qtd_uc_recebe_credito') or 0):,}".replace(",", ".")
            if not (tipo_filter or classe_filter or porte_filter)
            else "n/d no filtro"
        ),
    )
    if level == AudienceLevel.TECHNICAL:
        st.json(
            {
                "by_tipo": raw.get("by_tipo"),
                "by_classe": raw.get("by_classe"),
                "by_porte": raw.get("by_porte"),
                "by_cadastral_update_year": raw.get(
                    "by_cadastral_update_year"
                ),
                "note": (
                    "by_cadastral_update_year = atualização cadastral, "
                    "não conexão"
                ),
            }
        )

with st.expander("Fonte e metodologia", expanded=False):
    for line in mmgd_attribution_lines(mmgd):
        st.markdown(f"- {line}")
    for note in atualizar_lista(mmgd.panel.get("notices_pt")):
        st.caption(str(note))

st.subheader("Comparação municipal (MMGD)")
cmp_a, cmp_b = st.columns(2)
if "mmgd_cmp_a" not in st.session_state:
    st.session_state.mmgd_cmp_a = code_to_label.get(code, labels_all[0])
if "mmgd_cmp_b" not in st.session_state:
    alt = next(
        (lab for lab in labels_all if lab != st.session_state.mmgd_cmp_a),
        labels_all[0],
    )
    st.session_state.mmgd_cmp_b = alt
with cmp_a:
    st.selectbox("Município A", options=labels_all, key="mmgd_cmp_a")
with cmp_b:
    st.selectbox("Município B", options=labels_all, key="mmgd_cmp_b")

cmp = compare_municipal_mmgd(
    mmgd,
    label_to_code[st.session_state.mmgd_cmp_a],
    label_to_code[st.session_state.mmgd_cmp_b],
    tipo=tipo_filter,
    classe=classe_filter,
    porte=porte_filter,
)
if not cmp.get("ok"):
    st.warning(cmp.get("message") or "Comparação indisponível.")
else:
    a, b = cmp["a"], cmp["b"]
    nome_a = a.get("NM_MUN") or "Município A"
    nome_b = b.get("NM_MUN") or "Município B"

    def _diferenca(valor: object, casas: int) -> str:
        if valor is None:
            return "n/d"
        numero = float(valor)
        sinal = "+" if numero >= 0 else "−"
        return f"{sinal}{br_num(abs(numero), casas)}"

    st.dataframe(
        [
            {
                "Indicador": "Instalações",
                nome_a: br_num(a.get("display_n")),
                nome_b: br_num(b.get("display_n")),
                "Diferença": _diferenca(cmp.get("delta_n_a_minus_b"), 0),
            },
            {
                "Indicador": "Potência instalada (MW)",
                nome_a: br_num(a.get("display_mw"), 1),
                nome_b: br_num(b.get("display_mw"), 1),
                "Diferença": _diferenca(cmp.get("delta_mw_a_minus_b"), 1),
            },
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"A diferença é {nome_a} menos {nome_b}, no recorte escolhido acima."
    )
    st.caption(cmp["disclaimer_pt"])
    st.download_button(
        "Baixar comparação (JSON)",
        data=json.dumps(cmp, ensure_ascii=False, indent=2),
        file_name=(
            f"mmgd_cmp_{a.get('CD_MUN')}_{b.get('CD_MUN')}.json"
        ),
        mime="application/json",
    )

export_panel = {
    "source_id": mmgd.panel.get("source_id"),
    "periodo_referencia": mmgd.panel.get("periodo_referencia"),
    "totals": mmgd.panel.get("totals"),
    "notices_pt": atualizar_lista(mmgd.panel.get("notices_pt")),
    "municipality_count": mmgd.panel.get("municipality_count"),
}
# Garantir ausência de PII no export agregado
export_text = json.dumps(export_panel, ensure_ascii=False, indent=2)
st.download_button(
    "Baixar totais do painel (JSON, sem PII)",
    data=export_text,
    file_name="mmgd_pr_totals_export.json",
    mime="application/json",
)

render_footer()
