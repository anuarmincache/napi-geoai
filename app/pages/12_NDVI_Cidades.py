"""NDVI por satélite nas cidades acima de 20 mil habitantes.

Lê só artefatos estáticos. Não baixa cena, não roda GDAL e não calcula NDVI.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from geoai.portal.ndvi_panel import (
    STATUS_STYLE,
    load_ndvi_overview,
    ndvi_targets_map_html,
)

from _bootstrap import (
    REPO_ROOT,
    br_num,
    cached_municipality_layer,
    configure_page,
    date_br,
    page_link,
    render_footer,
    render_html_map,
    sidebar_brand,
)

configure_page("NDVI por satélite", icon="🛰️")
sidebar_brand()

st.title("NDVI por satélite")
st.caption(
    "Índice de vegetação (NDVI) a partir de imagens Sentinel-2 L2A do "
    "programa Copernicus, para os municípios do Paraná acima de 20 mil "
    "habitantes. NDVI é um índice espectral: não é biomassa, produtividade, "
    "potencial de biogás nem viabilidade."
)


@st.cache_data(show_spinner=False)
def _overview() -> dict:
    return load_ndvi_overview(REPO_ROOT)


overview = _overview()
if not overview["available"]:
    st.error(overview["missing_reason_pt"])
    render_footer()
    st.stop()

registry = overview["registry"]
counts = overview["counts"]
rows = overview["rows"]
plan = overview["plan"]
done = counts["publicado"]

if done == 0:
    st.warning(
        f"**Nenhum mapa de NDVI está publicado ainda.** Dos {registry['count']} "
        f"municípios da lista, {counts['medido']} tem cena real medida e "
        f"{counts['aguardando'] + counts['planejado'] + counts['sem_passagem']} "
        "aguardam processamento. Esta página mostra o andamento, sem preencher "
        "o que falta."
    )

k1, k2, k3, k4 = st.columns(4)
k1.metric("Municípios na lista", br_num(registry["count"]))
k2.metric("Área somada (km²)", br_num(registry["total_area_km2"]))
k3.metric("Com cena medida", br_num(counts["medido"] + counts["publicado"]))
k4.metric("Com NDVI publicado", br_num(done))
st.caption(
    f"{registry['rule_pt']} Referência da população: "
    f"{date_br(registry.get('population_reference_date'))}. "
    f"{registry['aoi_note_pt']}"
)

left, right = st.columns([2.2, 1], gap="medium")
with left:
    mun = cached_municipality_layer()
    if mun.validated_for_map:
        try:
            render_html_map(ndvi_targets_map_html(mun, overview), height=540)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha no mapa: {exc}")
    else:
        st.warning(mun.missing_reason_pt or "Malha municipal indisponível.")
with right:
    st.markdown("#### Situação")
    for code, (color, label) in STATUS_STYLE.items():
        st.markdown(
            f'<span style="display:inline-block;width:0.8rem;height:0.8rem;'
            f'background:{color};border-radius:3px;margin-right:0.45rem;"></span>'
            f"{label}: **{counts[code]}**",
            unsafe_allow_html=True,
        )
    st.caption("Cinza claro no mapa: municípios fora da lista.")
    zones = registry["by_sentinel_utm_epsg"]
    st.markdown("#### Grade Sentinel-2")
    st.caption(
        "Zonas UTM das cenas: "
        + ", ".join(f"EPSG:{k} ({v} municípios)" for k, v in sorted(zones.items()))
        + ". O piloto de Maringá só exercitou a zona 22 Sul."
    )

st.subheader("Municípios da lista")
table = pd.DataFrame(
    [
        {
            "Município": r["name"],
            "Código IBGE": r["cd_mun"],
            "População estimada": r["population"],
            "Área (km²)": round(r["area_km2"], 1),
            "Zona UTM": f"EPSG:{r['sentinel_utm_epsg']}",
            "Situação": r["status"]["label_pt"],
            "Passagem": r["status"]["acquisition_id"] or "",
            "Pixels válidos (%)": (
                round(100 * float(r["status"]["valid_fraction"]), 1)
                if r["status"]["valid_fraction"] is not None
                else None
            ),
        }
        for r in rows
    ]
)
st.dataframe(table, hide_index=True, width="stretch", height=380)
st.download_button(
    "Baixar a lista (CSV)",
    table.to_csv(index=False).encode("utf-8-sig"),
    file_name="napi_geoai_ndvi_municipios.csv",
    mime="text/csv",
)

measured = [r for r in rows if r["status"]["code"] in ("medido", "publicado")]
if measured:
    st.subheader("O que já foi medido")
    for r in measured:
        fraction = r["status"]["valid_fraction"]
        st.markdown(
            f"**{r['name']}**: passagem `{r['status']['acquisition_id']}`, "
            f"**{br_num(100 * float(fraction), 1)}%** de pixels válidos no "
            "município após a máscara de nuvens e sombras (mínimo exigido: 70%)."
        )
    st.caption(
        "Medição feita com as bandas oficiais B04, B08 e SCL. O raster de "
        "NDVI ainda não foi publicado no portal."
    )
    page_link("pages/8_Sentinel_Piloto.py", "Ver o registro técnico do piloto", "🔬")

st.subheader("Plano do ciclo")
if plan is None:
    st.info(
        "O plano do ciclo ainda não foi gerado. Ele consulta o catálogo oficial "
        "do Copernicus e informa, sem baixar imagem, quantas cenas o ciclo exige "
        "e quanto elas somam. Comando: `python scripts/plan_ndvi_targets.py`."
    )
else:
    summary = plan["summary"]
    p1, p2, p3, p4 = st.columns(4)
    p1.metric(
        "Com passagem na janela",
        f"{summary['targets_with_pass']}/{summary['targets']}",
    )
    p2.metric("Cenas distintas", br_num(summary["distinct_products"]))
    p3.metric("Tiles distintas", br_num(len(summary["distinct_mgrs_tiles"])))
    p4.metric(
        "Volume oficial (GB)", br_num(summary["official_bytes_known"] / 1e9, 1)
    )
    st.caption(
        f"Janela de {plan['window_days']} dias até {date_br(plan['as_of_utc'])}. "
        f"{summary['bytes_note_pt']} " + " ".join(plan["limits_pt"])
    )
    if summary["targets_without_pass"]:
        st.warning(
            "Sem passagem que cubra o município na janela: "
            + ", ".join(summary["targets_without_pass"])
            + "."
        )

with st.expander("Como o NDVI é calculado e o que ele não diz"):
    st.latex(r"NDVI = \frac{B08 - B04}{B08 + B04}")
    st.markdown(
        "- B08 é o infravermelho próximo e B04 é o vermelho, em reflectância "
        "de superfície (Sentinel-2 L2A, 10 m).\n"
        "- Pixels com nuvem, sombra ou sem dado são retirados pela camada SCL "
        "e ficam sem valor. Não viram zero.\n"
        "- Cada município usa uma única passagem do satélite. Datas não são "
        "misturadas, então em períodos nublados pode não haver imagem válida.\n"
        "- A área analisada é o município inteiro, incluindo a zona rural.\n"
        "- NDVI indica vigor de vegetação. Não mede produção, biomassa "
        "disponível nem aptidão para qualquer empreendimento."
    )

render_footer()
