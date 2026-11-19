"""Ficha municipal — população IBGE 2026, densidade e kW/hab SIGA (MVP 11)."""

from __future__ import annotations

import json

import streamlit as st
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal import (
    list_municipalities,
    municipality_label,
    search_municipalities,
)
from geoai.portal.agro_panel import (
    PPM_LABELS_PT,
    agro_cell,
    agro_format_cell,
    agro_indicator,
    list_agro_crops,
)
from geoai.portal.municipal_profile import (
    compare_municipal_profiles,
    population_attribution_lines,
    population_map_html,
    profile_for_code,
)
from geoai.presentation import AudienceLevel

from _bootstrap import (
    br_num,
    cached_agro_panel,
    cached_mmgd_panel,
    cached_municipality_layer,
    cached_population_panel,
    configure_page,
    date_br,
    page_header,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Ficha municipal")
sidebar_brand()

page_header(
    "Ficha do município",
    "Território, população, energia e agropecuária de um município em um só lugar.",
    art_kind="map",
    eyebrow="Comece aqui",
)
st.caption(
    "Território, população, energia e agropecuária de um município em um só "
    "lugar. Estimativa IBGE **01/07/2026** (não é Censo), malha **2025**, "
    "ANEEL SIGA e MMGD, IBGE PAM e PPM. Potência não é energia gerada (MWh)."
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
        "Escolha um município entre os 399. A ficha reúne população, "
        "usinas, geração distribuída, lavouras e pecuária, cada dado com a "
        "sua fonte e o seu ano."
    )
elif level is AudienceLevel.INTERMEDIATE:
    st.info(
        "A densidade combina população de 2026 com área de 2025. Os "
        "indicadores por habitante dividem a potência pela população "
        "estimada. Há usinas da ANEEL que não puderam ser associadas a um "
        "município."
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

SIGA_STATUS_PT = {
    "com_empreendimento": "com usinas associadas",
    "sem_empreendimento": "sem usina associada",
}

if profile:
    st.markdown(f"### {profile['NM_MUN']}")
    st.caption(f"Código IBGE {profile['CD_MUN']} · Paraná")

    card_t, card_e = st.columns(2, gap="medium")
    with card_t.container(border=True):
        st.markdown("##### 🗺️ Território e população")
        t1, t2, t3 = st.columns(3)
        t1.metric(
            "População estimada",
            br_num(profile["populacao_estimada_2026_hab"]),
        )
        t2.metric(
            "Densidade (hab/km²)",
            br_num(profile.get("densidade_demografica_estimada_2026_hab_km2"), 1),
        )
        t3.metric("Área (km²)", br_num(profile["area_km2_ibge_2025"], 1))
        st.caption(
            "IBGE, estimativa de "
            f"{date_br(profile['populacao_referencia_data'])} (não é Censo) e "
            "Malha Municipal 2025. " + (profile.get("densidade_note_pt") or "")
        )

    with card_e.container(border=True):
        st.markdown("##### ⚡ Geração centralizada (ANEEL SIGA)")
        status = str(profile.get("status_energia_siga"))
        e1, e2, e3 = st.columns(3)
        n_pl = profile.get("n_empreendimentos_siga_operacao")
        e1.metric("Usinas", br_num(n_pl))
        e2.metric(
            "MW fiscalizada",
            br_num(profile.get("potencia_fiscalizada_conhecida_mw"), 1),
        )
        e3.metric(
            "kW por habitante",
            br_num(profile.get("potencia_fiscalizada_conhecida_kw_por_habitante"), 2),
        )
        st.metric("Status energia SIGA", SIGA_STATUS_PT.get(status, status))
        if profile.get("zero_vinculado"):
            st.info(
                "Zero vinculado (usinas georreferenciadas associadas) — "
                "não interpretar como ausência absoluta de empreendimentos."
            )
        st.caption(profile.get("energy_scope_pt") or "")
        if level != AudienceLevel.BASIC:
            st.caption(profile.get("kw_por_habitante_note_pt") or "")
            st.caption(profile.get("unassociated_plants_limitation_pt") or "")

    card_m, card_a = st.columns(2, gap="medium")
    with card_m.container(border=True):
        st.markdown("##### ☀️ Geração distribuída (ANEEL MMGD)")
        mmgd = cached_mmgd_panel()
        mmgd_row = None
        if mmgd.available:
            mmgd_row = next(
                (
                    r
                    for r in (mmgd.panel.get("municipalities") or [])
                    if str(r.get("CD_MUN")) == str(profile["CD_MUN"])
                ),
                None,
            )
        if not mmgd.available:
            st.caption(mmgd.missing_reason_pt or "Painel MMGD indisponível.")
        elif mmgd_row is None:
            st.caption("Município ausente no painel MMGD.")
        else:
            n_mmgd = int(mmgd_row.get("n_empreendimentos") or 0)
            mw_mmgd = mmgd_row.get("potencia_instalada_mw_conhecida")
            pop_hab = float(profile["populacao_estimada_2026_hab"] or 0)
            m1, m2, m3 = st.columns(3)
            m1.metric("Instalações", br_num(n_mmgd))
            m2.metric("MW instalada", br_num(mw_mmgd, 1))
            m3.metric(
                "kW por habitante",
                br_num(float(mw_mmgd) * 1000 / pop_hab, 2)
                if mw_mmgd is not None and pop_hab > 0
                else "n/d",
                help=(
                    "Indicador derivado (classe B): potência instalada "
                    "conhecida MMGD em kW ÷ população estimada IBGE 2026."
                ),
            )
            classes = sorted(
                (mmgd_row.get("by_classe") or {}).items(),
                key=lambda kv: -int(kv[1]),
            )[:3]
            if classes:
                st.caption(
                    "Principais classes de consumo: "
                    + ", ".join(f"{k} ({br_num(v)})" for k, v in classes)
                    + "."
                )
            st.caption(
                f"Snapshot ANEEL {mmgd.panel.get('periodo_referencia') or 'n/d'}. "
                "MMGD ≠ SIGA. Contagem = empreendimentos; "
                "UCs crédito não substituem essa contagem. Muitas instalações "
                "não provam saturação de mercado."
            )

    with card_a.container(border=True):
        st.markdown("##### 🌾 Agropecuária (IBGE PAM e PPM)")
        agro = cached_agro_panel()
        if not agro.available:
            st.caption(agro.missing_reason_pt or "Painel agropecuário indisponível.")
        else:
            a_cols = [*st.columns(2), *st.columns(2)]
            for col, key in zip(a_cols, PPM_LABELS_PT, strict=True):
                ind = agro_indicator(agro, "ppm", key)
                value, status_cell = agro_cell(agro, profile["CD_MUN"], ind)
                col.metric(
                    f"{PPM_LABELS_PT[key]} ({ind.unit.lower()})",
                    agro_format_cell(value, status_cell, "").strip(),
                )
            crops_here = []
            for crop in list_agro_crops(agro):
                ind = agro_indicator(agro, "pam", "area_plantada", str(crop["id"]))
                value, _status = agro_cell(agro, profile["CD_MUN"], ind)
                if value:
                    crops_here.append((float(value), str(crop["name"]), ind.unit))
            crops_here.sort(reverse=True)
            if crops_here:
                st.caption(
                    "Maiores áreas plantadas: "
                    + ", ".join(
                        f"{name} ({br_num(v)} {unit.lower()})"
                        for v, name, unit in crops_here[:3]
                    )
                    + "."
                )
            st.caption(
                f"PAM {agro.panel['pam']['year']} e PPM "
                f"{agro.panel['ppm']['year_rebanho']}. Efetivo de rebanho não é "
                "resíduo disponível para biogás."
            )
left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Mapa temático")
    st.caption(
        "O mapa ao lado compara os 399 municípios no indicador escolhido "
        "acima. O município selecionado fica destacado."
    )
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
            render_html_map(html, height=620)
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
