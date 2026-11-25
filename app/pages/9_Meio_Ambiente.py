"""Meio Ambiente — moldura territorial IBGE, sem indicador ambiental inventado."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal import (
    compare_municipalities,
    environment_source_inventory,
    explorer_attribution_lines,
    list_municipalities,
    municipality_label,
    municipality_map_html,
    search_municipalities,
)
from geoai.portal.landcover_panel import (
    landcover_attribution_lines,
    landcover_change,
    landcover_composition,
    landcover_map_html,
    landcover_ranked,
    landcover_share,
)
from geoai.portal.textos_legados import atualizar_lista

from _bootstrap import (
    br_num,
    cached_landcover_panel,
    cached_municipality_layer,
    configure_page,
    page_header,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("Meio Ambiente")
sidebar_brand()

page_header(
    "Cobertura e uso da terra",
    "Floresta, agricultura, pastagem e área urbana nos 399 municípios, de 1985 a 2025.",
    art_kind="forest",
    eyebrow="Território",
)
lc = cached_landcover_panel()
if lc.available:
    st.caption(
        "Cobertura e uso da terra dos 399 municípios do Paraná, de 1985 a "
        f"{lc.panel['last_year']}, segundo o MapBiomas Coleção 11. Não há taxa "
        "de desmatamento, unidade de conservação ou recurso hídrico nesta página."
    )
else:
    st.caption(
        "Consulta territorial do Paraná. Não há percentual de vegetação, "
        "desmatamento, unidade de conservação ou recurso hídrico nesta página."
    )

inventory = environment_source_inventory()
_sources = st.expander(
    "Fontes ambientais e situação de cada uma", expanded=not lc.available
)
for item in inventory:
    if item.validated and item.integrated:
        state = (
            "arquivo validado e integrado"
            if item.supports_environmental_indicator
            else "arquivo validado e integrado como moldura territorial"
        )
    elif item.catalogued and not item.local_file:
        state = "catalogada, sem arquivo local"
    elif not item.catalogued and not item.local_file:
        state = "não catalogada e sem arquivo local"
    else:
        state = "arquivo presente, ainda não validado"
    _sources.markdown(f"**{item.theme_pt}** — {item.organization}: {state}.")
    _sources.caption(item.note_pt)

if lc.available:
    st.warning(
        "Unidades de conservação e recursos hídricos estão indisponíveis. "
        "A cobertura da terra vem do MapBiomas: floresta mapeada não é área "
        "protegida, e a mudança entre anos não é taxa de desmatamento."
    )
else:
    st.warning(
        "MapBiomas, unidades de conservação e recursos hídricos estão "
        "indisponíveis. Nenhum indicador ambiental foi calculado."
    )
    st.caption(
        "A tabela municipal da Coleção 11 está identificada na página oficial "
        "de estatísticas (1985–2025, hectares). " + (lc.missing_reason_pt or "")
    )

lc_group = None
lc_year = None
group_labels: dict[str, str] = {}
if lc.available:
    group_labels = {g["key"]: g["label_pt"] for g in lc.panel["groups"]}
    g1, g2 = st.columns([1.6, 1])
    with g1:
        lc_group = st.selectbox(
            "Classe no mapa",
            options=list(group_labels),
            format_func=lambda k: group_labels[k],
            key="env_group",
        )
    with g2:
        lc_year = st.select_slider(
            "Ano",
            options=lc.panel["years"],
            value=lc.panel["last_year"],
            key="env_year",
            help=lc.panel["year_rule_pt"],
        )
    st.caption(
        f"No mapa: **{group_labels[lc_group]}** como percentual da área "
        f"mapeada de cada município em **{lc_year}**. Hectares são dado "
        "oficial, e o percentual é calculado sobre a área mapeada."
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

if "env_query" not in st.session_state:
    st.session_state.env_query = ""
if "env_code" not in st.session_state:
    st.session_state.env_code = None


def _clear_env_search() -> None:
    st.session_state.env_query = ""


def _on_city() -> None:
    label = st.session_state.get("env_city")
    if label in label_to_code:
        st.session_state.env_code = label_to_code[label]


NONE_SELECTION = "— Mapa geral do Paraná —"

query = str(st.session_state.env_query or "")
hits = search_municipalities(bundle, query, limit=None)
hit_labels = [municipality_label(rec) for rec in hits]
if query.strip():
    options = hit_labels
else:
    options = [NONE_SELECTION, *hit_labels]
if not options:
    options = [NONE_SELECTION]
current = code_to_label.get(str(st.session_state.env_code or ""))
if current and current not in options:
    options = [current, *options]
if "env_city" not in st.session_state or st.session_state.env_city not in options:
    st.session_state.env_city = current or options[0]
chosen = st.session_state.env_city
st.session_state.env_code = label_to_code.get(chosen)

left, right = st.columns([2.2, 1], gap="medium")
with right:
    st.markdown("#### Município")
    st.caption(
        f"Catálogo IBGE: **{EXPECTED_PR_MUNICIPALITY_COUNT}** municípios. "
        "A área exibida é o atributo oficial da malha, não um indicador ambiental."
    )
    st.text_input(
        "Nome ou código IBGE",
        key="env_query",
        placeholder="Ex.: Maringá ou 4115200",
    )
    st.button("Limpar busca", on_click=_clear_env_search)
    st.markdown(f"**{len(hits)} de {EXPECTED_PR_MUNICIPALITY_COUNT}** municípios")
    if query.strip() and not hits:
        st.warning("Nenhum município encontrado para esta busca.")
    if options:
        st.selectbox(
            "Município no mapa",
            options=options,
            key="env_city",
            on_change=_on_city,
        )

with left:
    with st.spinner("Renderizando malha municipal…"):
        try:
            if lc.available:
                html = landcover_map_html(
                    bundle,
                    lc,
                    lc_group,
                    int(lc_year),
                    selected_code=st.session_state.env_code,
                )
            else:
                html = municipality_map_html(
                    bundle,
                    selected_code=st.session_state.env_code,
                )
            render_html_map(html, height=560)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")

code = st.session_state.env_code
selected = next((rec for rec in records if rec.code == code), None)
st.subheader("Território selecionado")
if selected is None:
    st.info("Nenhum município selecionado. O mapa mostra o Paraná.")
else:
    st.markdown(f"**{selected.name}** · código IBGE `{selected.code}`")
    c1, c2, c3 = st.columns(3)
    c1.metric("Código IBGE", selected.code)
    c2.metric("Área oficial (km²)", f"{br_num(selected.area_km2, 1)}")
    if lc.available:
        share = landcover_share(lc, selected.code, lc_group, int(lc_year))
        c3.metric(
            f"{group_labels[lc_group]} em {lc_year}",
            f"{br_num(share, 1)}%" if share is not None else "sem dado",
            help=f"{group_labels[lc_group]}: % da área mapeada em {lc_year}.",
        )
    else:
        c3.metric("Indicador ambiental", "indisponível")
    st.caption(
        "AREA_KM2 é o campo oficial da Malha Municipal IBGE 2025. "
        "Não representa vegetação, desmatamento nem aptidão ambiental."
    )

if lc.available:
    scope_code = selected.code if selected is not None else None
    scope_name = selected.name if selected is not None else "Paraná"
    last_year = lc.panel["last_year"]
    first_year = lc.panel["years"][0]
    st.subheader(f"Cobertura e uso da terra em {lc_year}: {scope_name}")
    comp = landcover_composition(lc, scope_code, int(lc_year))
    comp_df = pd.DataFrame(
        [
            {
                "Classe": r["label_pt"],
                "Hectares": round(r["hectares"]),
                "% da área mapeada": round(r["percent"], 1)
                if r["percent"] is not None
                else None,
            }
            for r in comp
        ]
    )
    b1, b2 = st.columns([1.3, 1])
    with b1:
        st.bar_chart(comp_df, x="Classe", y="% da área mapeada", horizontal=True)
    with b2:
        st.dataframe(comp_df, hide_index=True, width="stretch")
    if selected is not None:
        row = lc.panel["municipalities"][selected.code]
        st.caption(
            f"Área mapeada em {last_year}: "
            f"{br_num(row['mapped_ha_last'] / 100, 1)} km². Área oficial IBGE: "
            f"{br_num(row['ibge_area_km2'], 1)} km². Diferença: "
            f"{br_num(100 * row['relative_delta_vs_ibge'], 2)}%. "
            "Os hectares não foram reescalados."
        )

    st.subheader(f"O que mudou de {first_year} a {last_year}: {scope_name}")
    change = landcover_change(lc, scope_code, first_year, last_year)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Classe": r["label_pt"],
                    f"Hectares em {first_year}": round(r["hectares_a"]),
                    f"Hectares em {last_year}": round(r["hectares_b"]),
                    "Diferença (ha)": round(r["delta_ha"]),
                    "Diferença (pontos percentuais)": round(r["delta_pp"], 1)
                    if r["delta_pp"] is not None
                    else None,
                }
                for r in change
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Diferença de estoque entre os dois anos, por classe. Não é taxa de "
        "desmatamento, não mostra onde a mudança ocorreu e não distingue "
        "conversão de regeneração."
    )

    st.subheader(f"Maiores percentuais: {group_labels[lc_group]}, {lc_year}")
    names_by_code = {rec.code: rec.name for rec in records}
    top = landcover_ranked(lc, lc_group, int(lc_year), names_by_code, limit=10)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Município": r["NM_MUN"],
                    "Código IBGE": r["CD_MUN"],
                    "% da área mapeada": round(r["percent"], 1),
                }
                for r in top
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption("Ordenação descritiva. Não é ranking ambiental nem de aptidão.")
    export = [
        {
            "CD_MUN": rec.code,
            "NM_MUN": rec.name,
            "ano": int(lc_year),
            **{
                f"{r['key']}_ha": round(r["hectares"], 2)
                for r in landcover_composition(lc, rec.code, int(lc_year))
            },
        }
        for rec in records
    ]
    st.download_button(
        f"Baixar cobertura dos 399 municípios em {lc_year} (CSV)",
        pd.DataFrame(export).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"napi_geoai_cobertura_{lc_year}.csv",
        mime="text/csv",
    )

st.subheader("Comparação territorial")
st.caption(
    "A comparação usa somente nome, código e área oficial. "
    "Não compara condição ambiental."
)
if "env_cmp_a" not in st.session_state:
    st.session_state.env_cmp_a = labels[0]
if "env_cmp_b" not in st.session_state:
    st.session_state.env_cmp_b = labels[min(1, len(labels) - 1)]
ca, cb = st.columns(2)
with ca:
    a_label = st.selectbox("Município A", labels, key="env_cmp_a")
with cb:
    b_label = st.selectbox("Município B", labels, key="env_cmp_b")
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
    st.write(f"Δ área oficial (A−B): **{br_num(delta, 1)} km²**")
    st.warning(compared["disclaimer_pt"])

st.subheader("Fonte, referência e método")
for line in explorer_attribution_lines(bundle):
    st.caption(line)
if lc.available:
    for line in landcover_attribution_lines(lc):
        st.caption(line)
    for line in atualizar_lista(lc.panel.get("notices_pt")):
        st.caption(line)
    st.caption("CNUC/ICMBio e ANA/IAT ainda não foram integrados.")
else:
    st.caption(
        "Resolução ambiental: não se aplica. A malha municipal não tem "
        "resolução de sensor. MapBiomas, CNUC/ICMBio e ANA/IAT ainda não "
        "foram integrados."
    )
    st.caption(
        "Próximo dado: estatística municipal oficial de uso do solo, com "
        "código IBGE conferido contra os 399, antes de qualquer percentual."
    )

render_footer()
