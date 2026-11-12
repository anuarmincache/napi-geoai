"""Ficha municipal — população IBGE 2026, densidade e kW/hab SIGA (MVP 11)."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal import (
    list_municipalities,
    municipality_label,
    search_municipalities,
)
from geoai.portal.municipal_profile import (
    compare_municipal_profiles,
    population_attribution_lines,
    population_map_html,
    profile_for_code,
)
from geoai.presentation import AudienceLevel

from _bootstrap import (
    cached_municipality_layer,
    cached_population_panel,
    configure_page,
    render_footer,
    sidebar_brand,
)

configure_page("Ficha municipal")
sidebar_brand()

st.title("Ficha municipal — população e indicadores")
st.caption(
    "Estimativa IBGE **01/07/2026** + área malha **2025** + capacidade "
    "SIGA conhecida (centralizada). Não é Censo, MWh, MMGD nem aptidão solar."
)

mun = cached_municipality_layer()
pop = cached_population_panel()
if not mun.validated_for_map:
    st.error(mun.missing_reason_pt or "Malha municipal indisponível.")
    render_footer()
    st.stop()
if not pop.available:
    st.error(pop.missing_reason_pt or "Painel populacional indisponível.")
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
        "Escolha um município entre os 399. Veja habitantes estimados, "
        "densidade (hab/km²) e, quando houver usinas SIGA associadas, "
        "capacidade por habitante (kW/hab)."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "Densidade mistura população 2026 e área 2025. kW/hab usa MW "
        "fiscalizada conhecida ÷ população — geração centralizada em "
        "Operação; há usinas SIGA sem associação municipal."
    )
else:
    st.info(
        "Artefatos: `ibge_pr_population_2026_panel.json` + proveniência/"
        "qualidade. Join estrito CD_MUN×malha; QGIS validou a malha no MVP 09."
    )

st.warning(pop.panel.get("nao_associados_limitation_pt") or "")

all_recs = list_municipalities(mun)
label_to_code = {municipality_label(r): r.code for r in all_recs}
code_to_label = {c: lab for lab, c in label_to_code.items()}
labels_all = list(label_to_code.keys())

if "ficha_query" not in st.session_state:
    st.session_state.ficha_query = ""
if "ficha_code" not in st.session_state:
    st.session_state.ficha_code = all_recs[0].code if all_recs else None

q = st.text_input(
    "Buscar município (nome ou código IBGE)",
    key="ficha_query",
    placeholder="Ex.: Londrina / 4113700",
)
hits = search_municipalities(mun, q, limit=None)
st.caption(f"{len(hits)} de {EXPECTED_PR_MUNICIPALITY_COUNT} municípios")
if q.strip() and not hits:
    st.warning("Nenhum município encontrado")
else:
    opts = [municipality_label(r) for r in hits] or labels_all
    preferred = code_to_label.get(st.session_state.ficha_code, opts[0])
    if preferred not in opts:
        preferred = opts[0]
    choice = st.selectbox("Município", options=opts, index=opts.index(preferred))
    st.session_state.ficha_code = label_to_code[choice]

code = st.session_state.ficha_code
profile = profile_for_code(pop, code) if code else None

metric_choice = st.selectbox(
    "Mapa temático",
    options=[
        "populacao_estimada_2026_hab",
        "densidade_demografica_estimada_2026_hab_km2",
        "potencia_fiscalizada_conhecida_kw_por_habitante",
    ],
    format_func={
        "populacao_estimada_2026_hab": "População estimada 2026 (hab)",
        "densidade_demografica_estimada_2026_hab_km2": "Densidade estimada (hab/km²)",
        "potencia_fiscalizada_conhecida_kw_por_habitante": (
            "kW/hab SIGA conhecida"
        ),
    }.__getitem__,
)

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Ficha")
    if profile:
        st.metric("Nome", profile["NM_MUN"])
        st.metric("Código IBGE", profile["CD_MUN"])
        st.metric(
            "População estimada 2026 (hab)",
            f"{int(profile['populacao_estimada_2026_hab']):,}".replace(",", "."),
        )
        st.caption(f"Referência: {profile['populacao_referencia_data']} (não é Censo)")
        dens = profile.get("densidade_demografica_estimada_2026_hab_km2")
        st.metric(
            "Densidade estimada (hab/km²)",
            f"{dens:.2f}" if dens is not None else "n/d",
        )
        st.caption(profile.get("densidade_note_pt") or "")
        st.metric(
            "Área malha 2025 (km²)",
            f"{float(profile['area_km2_ibge_2025']):,.3f}",
        )
        st.metric(
            "MW fiscalizada conhecida (SIGA)",
            (
                f"{float(profile['potencia_fiscalizada_conhecida_mw']):,.3f}"
                if profile.get("potencia_fiscalizada_conhecida_mw") is not None
                else "n/d"
            ),
        )
        kw = profile.get("potencia_fiscalizada_conhecida_kw_por_habitante")
        st.metric(
            "kW/hab (SIGA conhecida)",
            f"{kw:,.4f}" if kw is not None else "n/d",
        )
        st.caption(profile.get("kw_por_habitante_note_pt") or "")
        st.metric(
            "Usinas SIGA associadas",
            int(profile.get("n_empreendimentos_siga_operacao") or 0),
        )
        st.caption(profile.get("energy_scope_pt") or "")
        st.caption(profile.get("unassociated_plants_limitation_pt") or "")
    with st.expander("Fonte e metodologia", expanded=False):
        for line in population_attribution_lines(pop):
            st.markdown(f'<p class="napi-meta">{line}</p>', unsafe_allow_html=True)

with left:
    with st.spinner("Renderizando mapa temático…"):
        try:
            html = population_map_html(
                mun,
                pop,
                metric=metric_choice,
                selected_code=code,
            )
            components.html(html, height=620, scrolling=False)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")

st.subheader("Comparação A/B (população e indicadores)")
if "ficha_cmp_a" not in st.session_state:
    st.session_state.ficha_cmp_a = code_to_label.get(code, labels_all[0])
if "ficha_cmp_b" not in st.session_state:
    alt = next(
        (lab for lab in labels_all if lab != st.session_state.ficha_cmp_a),
        labels_all[0],
    )
    st.session_state.ficha_cmp_b = alt

ca, cb = st.columns(2)
with ca:
    a_lab = st.selectbox("Município A", labels_all, key="ficha_cmp_a")
with cb:
    b_lab = st.selectbox("Município B", labels_all, key="ficha_cmp_b")

cmp = compare_municipal_profiles(
    pop, label_to_code[a_lab], label_to_code[b_lab]
)
if not cmp.get("ok"):
    st.warning(cmp.get("message"))
else:
    x, y = st.columns(2)
    for col, side in ((x, "a"), (y, "b")):
        row = cmp[side]
        with col:
            st.markdown(f"**{row['NM_MUN']}** (`{row['CD_MUN']}`)")
            dens = row.get("densidade_demografica_estimada_2026_hab_km2")
            kw = row.get("potencia_fiscalizada_conhecida_kw_por_habitante")
            pop_n = int(row["populacao_estimada_2026_hab"])
            st.write(
                f"Pop. 2026: **{pop_n:,}** hab · "
                f"densidade: **{dens}** hab/km² · kW/hab: **{kw}**"
            )
    st.write("Δ (A−B):", cmp["deltas"])
    st.caption("Unidades: " + json.dumps(cmp["units"], ensure_ascii=False))
    st.warning(cmp["disclaimer_pt"])
    st.download_button(
        "Baixar comparação (JSON)",
        data=json.dumps(cmp, ensure_ascii=False, indent=2),
        file_name=(
            f"ficha_cmp_{cmp['a']['CD_MUN']}_{cmp['b']['CD_MUN']}.json"
        ),
        mime="application/json",
    )

st.download_button(
    "Baixar painel populacional (JSON)",
    data=json.dumps(pop.panel, ensure_ascii=False, indent=2),
    file_name="ibge_pr_population_2026_panel.json",
    mime="application/json",
)

render_footer()
