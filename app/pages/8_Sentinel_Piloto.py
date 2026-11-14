"""Piloto Sentinel-2 de Maringá. Lê só o catálogo estático."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from geoai.sentinel.catalog import load_pilot_catalog, show_ndvi

from _bootstrap import configure_page, render_footer, sidebar_brand

configure_page("Sentinel-2 piloto")
sidebar_brand()

REPO = Path(__file__).resolve().parents[1]
catalog = load_pilot_catalog(REPO)
aoi = catalog.get("aoi") or {}
name = aoi.get("name") or "AOI não carregada"

st.title(f"Piloto Sentinel-2 — {name}")
st.caption(
    "Índice espectral NDVI, quando houver raster publicado. "
    "Não é biomassa, produtividade, biogás nem viabilidade."
)

if not show_ndvi(catalog):
    st.warning(catalog.get("public_message_pt") or "NDVI do piloto indisponível.")
else:
    st.success("Raster NDVI publicado no catálogo.")

st.subheader("Região")
st.write(
    f"{name} — CD_MUN {aoi.get('cd_mun', 'n/d')}, "
    f"área oficial {aoi.get('area_km2_official', 'n/d')} km², "
    f"CRS {aoi.get('crs', 'n/d')}."
)
if aoi.get("why_pt"):
    st.write(aoi["why_pt"])
if aoi.get("bbox"):
    st.write(f"BBox oficial: {aoi['bbox']}")

selected = catalog.get("selected_acquisition") or {}
criteria = catalog.get("criteria") or {}
st.subheader("Passagem selecionada")
st.write(f"Fonte: {catalog.get('source') or 'n/d'}")
st.write(f"Janela usada: {criteria.get('window_used', 'n/d')}")
if not selected:
    st.write("Nenhuma passagem única cobre o município no limiar geométrico.")
else:
    st.write(f"Aquisição: `{selected.get('acquisition_id')}`")
    st.write(f"Instante de aquisição: {selected.get('sensing_time_utc') or 'n/d'}")
    st.write(f"Órbita relativa: R{selected.get('relative_orbit') or 'n/d'}")
    st.write(f"Tiles do mosaico: {', '.join(selected.get('selected_tiles') or [])}")
    st.write(f"Cobertura conjunta: {selected.get('union_coverage')}")
    st.write(f"Lacuna: {selected.get('gap')}")
    st.write(f"Sobreposição: {selected.get('overlap_coverage')}")
    st.write("Composição: uma única aquisição. Datas diferentes não foram misturadas.")
    fraction = catalog.get("valid_pixel_fraction")
    if fraction is None:
        st.write(
            "Qualidade municipal: não avaliada. "
            "A cobertura geométrica não aprova o NDVI."
        )
    else:
        st.write(f"Fração válida na AOI: {fraction}")
        st.write(f"Qualidade aprovada: {catalog.get('quality_approved') is True}")
        st.write(f"NDVI publicado: {catalog.get('ndvi_published') is True}")
    st.write(f"Regra de sobreposição: {catalog.get('overlap_rule', 'n/d')}")
    fallback = catalog.get("fallback_acquisition_id")
    if fallback:
        st.write(
            f"Passagem reserva, ainda não lida: {fallback}. "
            "Ela só entra se a fração válida da candidata ficar abaixo de 0,70."
        )
    rows = selected.get("tiles") or []
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    st.write(
        "A nuvem do item STAC não é a fração de pixels válidos no município."
    )

access = catalog.get("asset_access") or {}
authorized = access.get("authorized") or {}
anonymous = access.get("anonymous_probe") or {}
if access:
    st.subheader("Acesso às bandas")
    st.write(f"Host OData: {access.get('https_host') or 'n/d'}")
    st.write(
        "Requisição autorizada enviada: "
        f"{authorized.get('authorized_attempted') is True}"
    )
    st.write(
        "HTTP sem Authorization: "
        f"{anonymous.get('http_status', 'não consultado')}"
    )
    if access.get("openid_token_endpoint"):
        st.write(f"Token endpoint OIDC publicado: {access['openid_token_endpoint']}")

st.subheader("Limitações")
if catalog.get("processing_status") == "measured":
    st.write(
        "A fração vale só para a passagem medida. Datas diferentes não entram "
        "no mesmo raster. O estado inteiro não foi processado. "
        "NDVI é índice espectral, não biomassa nem produtividade."
    )
else:
    st.write(
        "Sem raster publicado não há mapa de NDVI. "
        "A fração válida no município só existe depois da leitura de B04, B08 e SCL. "
        "A atualização é manual. O estado inteiro não foi processado. "
        "O processamento raster desta passagem não foi executado."
    )
render_footer()
