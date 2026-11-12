"""Painel energético — empreendimentos de geração SIGA/ANEEL (MVP 10)."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.energy.siga_aggregate import PHASE_OPERACAO
from geoai.portal import (
    compare_municipal_energy,
    energy_attribution_lines,
    energy_map_html,
    list_municipalities,
    municipalities_ranked,
    municipality_label,
)
from geoai.portal.energy_panel import (
    energy_scope_totals,
    project_municipality_metrics,
)
from geoai.presentation import AudienceLevel

from _bootstrap import (
    cached_energy_panel,
    cached_municipality_layer,
    configure_page,
    render_footer,
    sidebar_brand,
)

configure_page("Energia — SIGA/ANEEL")
sidebar_brand()

st.title("Energia — empreendimentos de geração (SIGA/ANEEL)")
st.caption(
    "Capacidade **fiscalizada conhecida** (MW) de geração **centralizada** "
    "no Paraná. Ausência ≠ zero. Não é geração efetiva (MWh), não é MMGD e "
    "**não** é aptidão solar."
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
        "Tecnologia (SigTipoGeracao) — redefine KPIs, ranking e mapa",
        options=["(todas)", *tipos],
        help=(
            "Os cards superiores e o mapa usam MW/contagens **desta** "
            "tecnologia. Catálogo municipal permanece 399."
        ),
    )
with f2:
    st.selectbox(
        "Fase",
        options=[PHASE_OPERACAO],
        help="Demais fases existem na qualidade; UI default = Operação.",
        disabled=True,
    )

tipo_filter = None if tipo == "(todas)" else tipo
scope = energy_scope_totals(energy, tipo=tipo_filter)
n_un = int(scope["n_empreendimentos_nao_associados"])

if level is AudienceLevel.BASIC:
    st.info(
        "O mapa mostra capacidade fiscalizada **conhecida** (MW) por município "
        "nas usinas SIGA em operação, no filtro de tecnologia escolhido. "
        "Cinza claro = nenhuma usina **georreferenciada e associada** ao "
        "polígono nesse escopo — não é prova de ausência absoluta "
        f"({n_un} usina(s) do escopo sem associação municipal)."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "Potência fiscalizada ≠ outorgada ≠ energia gerada. "
        f"Fase padrão: {PHASE_OPERACAO}. Join espacial de referência: QGIS; "
        "GeoPandas reconcilia CodCEG→CD_MUN (fail-closed). "
        "O filtro de tecnologia redefine KPIs, ranking e mapa."
    )
else:
    st.info(
        "Artefatos: `siga_pr_energy_panel.json`, proveniência/qualidade, "
        "`siga_pr_qgis_join_report.json` (assignments). "
        "MMGD catalogado, fora deste MVP."
    )

if tipo_filter:
    st.info(
        f"Escopo ativo: tecnologia **{tipo_filter}** "
        f"(`{scope['metric_scope']}`). "
        "KPIs superiores, ranking, comparação e mapa referem-se só a este tipo."
    )
else:
    st.caption(
        "Escopo ativo: **todas as tecnologias** na fase Operação "
        f"(`{scope['metric_scope']}`)."
    )

st.warning(scope["nao_associados_limitation_pt"])

c1, c2, c3, c4 = st.columns(4)
_scope_label = (
    f"escopo {tipo_filter}" if tipo_filter else "todas as tecnologias"
)
c1.metric(
    f"Empreendimentos ({_scope_label})",
    f"{scope['n_empreendimentos_fase']}",
)
c2.metric(
    f"MW fiscalizada conhecida ({_scope_label})",
    f"{float(scope['potencia_fiscalizada_mw_conhecida_fase']):,.1f}",
)
c3.metric(
    f"Municípios com usinas ({_scope_label})",
    f"{scope['n_municipios_com_usinas']}",
)
c4.metric(
    "Municípios no catálogo (fixo)",
    f"{scope['municipality_count']}/{EXPECTED_PR_MUNICIPALITY_COUNT}",
)
st.caption(scope["kpi_caption_pt"])
st.caption(
    f"Rótulo da soma: `{scope['soma_rotulo']}` · cobertura: "
    f"**{scope['soma_cobertura']}** · "
    f"ausências de potência fiscalizada: "
    f"{scope['n_potencia_fiscalizada_ausente_fase']} · "
    f"não associados no escopo: {n_un}"
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

if "energy_code" not in st.session_state:
    st.session_state.energy_code = ranked[0]["CD_MUN"] if ranked else None

rank_labels = [
    f"{r['NM_MUN']} ({r['CD_MUN']}) — {float(r['display_mw']):.2f} MW"
    for r in ranked
]
rank_codes = [r["CD_MUN"] for r in ranked]

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Ranking (MW fiscalizada no escopo)")
    if not rank_labels:
        st.warning("Nenhum município com empreendimentos no filtro.")
    else:
        choice = st.selectbox(
            "Municípios com usinas (top 20)",
            options=rank_labels,
            help="Atalho para foco no mapa. Catálogo completo = 399.",
        )
        st.session_state.energy_code = rank_codes[rank_labels.index(choice)]

    st.markdown("#### Município em foco")
    code = st.session_state.energy_code
    by_code = {
        str(m["CD_MUN"]): m for m in (energy.panel.get("municipalities") or [])
    }
    raw = by_code.get(str(code)) if code else None
    row = project_municipality_metrics(raw, tipo=tipo_filter) if raw else None
    if row:
        st.metric("Nome", row["NM_MUN"])
        st.metric("Código IBGE", row["CD_MUN"])
        st.metric("Status (escopo)", row["status_dados"])
        st.metric("Nº empreendimentos (escopo)", int(row["display_n"]))
        st.metric(
            "MW fiscalizada conhecida (escopo)",
            f"{float(row['display_mw']):,.3f}",
        )
        if row.get("display_ausente"):
            st.caption(
                f"{row['display_ausente']} registro(s) sem potência "
                "fiscalizada válida neste escopo."
            )
        st.caption(f"Escopo métrica: `{row.get('metric_scope')}`")
        if row.get("zero_semantics") and not tipo_filter:
            st.caption(row["zero_semantics"])
        if row.get("por_tipo"):
            st.write("Por tipo (n / MW conhecida):")
            for t_name, t_val in (row.get("por_tipo") or {}).items():
                if isinstance(t_val, dict):
                    st.write(
                        f"- {t_name}: n={t_val.get('n', 0)} · "
                        f"MW={float(t_val.get('potencia_fiscalizada_mw') or 0):.3f}"
                    )
                else:
                    st.write(f"- {t_name}: n={t_val}")

    with st.expander("Fonte e metodologia", expanded=False):
        for line in energy_attribution_lines(energy):
            st.markdown(f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True)

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
            components.html(html, height=620, scrolling=False)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")

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
            f"MW conhecida: **{float(cmp['a']['display_mw']):.3f}** · "
            f"n={cmp['a']['display_n']} · {cmp['a']['status_dados']}"
        )
    with y:
        st.markdown(f"**{cmp['b']['NM_MUN']}** (`{cmp['b']['CD_MUN']}`)")
        st.write(
            f"MW conhecida: **{float(cmp['b']['display_mw']):.3f}** · "
            f"n={cmp['b']['display_n']} · {cmp['b']['status_dados']}"
        )
    st.write(
        f"Δ MW (A−B): **{cmp['delta_fiscalizada_mw_a_minus_b']:.3f}** · "
        f"Δ n: **{cmp['delta_n_a_minus_b']}** · escopo `{cmp['metric_scope']}`"
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
