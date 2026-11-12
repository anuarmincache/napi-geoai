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
    "Capacidade **fiscalizada** (MW) de geração **centralizada** no Paraná. "
    "Não é geração efetiva (MWh), não é MMGD e **não** é aptidão solar."
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
if level is AudienceLevel.BASIC:
    st.info(
        "O mapa mostra quanto de capacidade fiscalizada (MW) cada município "
        "tem em usinas SIGA em operação. Cinza claro = nenhum empreendimento "
        "associado (zero real na fonte filtrada), não falta de mapa."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "Potência fiscalizada ≠ outorgada ≠ energia gerada. "
        f"Fase padrão: {PHASE_OPERACAO}. Coordenadas SIGA → join espacial "
        "na malha IBGE; municípios declarados são só checagem auxiliar."
    )
else:
    st.info(
        "Artefatos: `siga_pr_energy_panel.json`, proveniência/qualidade e "
        "`siga_pr_qgis_join_report.json`. MMGD catalogado, fora deste MVP."
    )

totals = energy.panel.get("totals") or {}
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Empreendimentos (operação)",
    f"{totals.get('n_empreendimentos_fase', 0)}",
)
c2.metric(
    "MW fiscalizada (total fase)",
    f"{float(totals.get('potencia_fiscalizada_mw_total_fase') or 0):,.1f}",
)
_n_agregado = sum(
    1
    for m in energy.panel.get("municipalities") or []
    if m.get("status_dados") == "agregado"
)
c3.metric("Municípios com usinas", f"{_n_agregado}")
c4.metric(
    "Municípios no catálogo",
    f"{energy.panel.get('municipality_count')}/{EXPECTED_PR_MUNICIPALITY_COUNT}",
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
        "Filtrar ranking por tecnologia (SigTipoGeracao)",
        options=["(todas)", *tipos],
        help="Não altera a fase (permanece Operação neste MVP).",
    )
with f2:
    st.selectbox(
        "Fase",
        options=[PHASE_OPERACAO],
        help="Demais fases existem na qualidade; UI default = Operação.",
        disabled=True,
    )

tipo_filter = None if tipo == "(todas)" else tipo
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

# Ranking shortcuts
rank_labels = [
    f"{r['NM_MUN']} ({r['CD_MUN']}) — {r['potencia_fiscalizada_mw']:.2f} MW"
    for r in ranked
]
rank_codes = [r["CD_MUN"] for r in ranked]

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Ranking (MW fiscalizada)")
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
    row = by_code.get(str(code)) if code else None
    if row:
        st.metric("Nome", row["NM_MUN"])
        st.metric("Código IBGE", row["CD_MUN"])
        st.metric("Status dos dados", row["status_dados"])
        st.metric("Nº empreendimentos", int(row["n_empreendimentos"]))
        st.metric(
            "MW fiscalizada",
            f"{float(row['potencia_fiscalizada_mw']):,.3f}",
        )
        st.metric(
            "MW outorgada",
            f"{float(row['potencia_outorgada_mw']):,.3f}",
        )
        if row.get("zero_semantics"):
            st.caption(row["zero_semantics"])
        if row.get("por_tipo"):
            st.write("Por tipo:", row["por_tipo"])

    with st.expander("Fonte e metodologia", expanded=False):
        for line in energy_attribution_lines(energy):
            st.markdown(f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True)
        un = energy.panel.get("nao_associados") or []
        st.caption(
            f"Não associados na fase: {len(un)} empreendimentos "
            "(coords ausentes/inválidas ou fora da malha)."
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
            )
            components.html(html, height=620, scrolling=False)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")

st.subheader("Comparação municipal (capacidade fiscalizada)")
if st.session_state.energy_code and st.session_state.energy_code in code_to_label:
    preferred = code_to_label[st.session_state.energy_code]
else:
    preferred = labels_all[0]
if "energy_cmp_a" not in st.session_state:
    st.session_state.energy_cmp_a = preferred
if st.session_state.energy_cmp_a not in labels_all:
    st.session_state.energy_cmp_a = preferred
if "energy_cmp_b" not in st.session_state:
    # segundo do ranking ou Londrina
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
    energy, label_to_code[a_lab], label_to_code[b_lab]
)
if not cmp.get("ok"):
    st.warning(cmp.get("message"))
else:
    x, y = st.columns(2)
    with x:
        st.markdown(f"**{cmp['a']['NM_MUN']}** (`{cmp['a']['CD_MUN']}`)")
        st.write(
            f"MW fiscalizada: **{cmp['a']['potencia_fiscalizada_mw']:.3f}** · "
            f"n={cmp['a']['n_empreendimentos']} · {cmp['a']['status_dados']}"
        )
    with y:
        st.markdown(f"**{cmp['b']['NM_MUN']}** (`{cmp['b']['CD_MUN']}`)")
        st.write(
            f"MW fiscalizada: **{cmp['b']['potencia_fiscalizada_mw']:.3f}** · "
            f"n={cmp['b']['n_empreendimentos']} · {cmp['b']['status_dados']}"
        )
    st.write(
        f"Δ MW (A−B): **{cmp['delta_fiscalizada_mw_a_minus_b']:.3f}** · "
        f"Δ n: **{cmp['delta_n_a_minus_b']}**"
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
