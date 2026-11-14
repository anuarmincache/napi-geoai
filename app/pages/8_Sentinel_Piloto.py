"""Piloto Sentinel-2 de Pinhais. Lê só o catálogo estático."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from geoai.sentinel.catalog import load_pilot_catalog, show_ndvi

from _bootstrap import configure_page, render_footer, sidebar_brand

configure_page("Sentinel-2 piloto")
sidebar_brand()

REPO = Path(__file__).resolve().parents[1]
catalog = load_pilot_catalog(REPO)

st.title("Piloto Sentinel-2 — Pinhais")
st.caption(
    "Índice espectral NDVI, quando houver raster publicado. "
    "Não é biomassa, produtividade, biogás nem viabilidade."
)

if not show_ndvi(catalog):
    st.warning(catalog.get("public_message_pt") or "NDVI do piloto indisponível.")
else:
    st.success("Raster NDVI publicado no catálogo.")

aoi = catalog.get("aoi") or {}
st.subheader("Região")
st.write(
    f"{aoi.get('name', 'Pinhais')} — CD_MUN {aoi.get('cd_mun', '4119152')}, "
    f"área oficial {aoi.get('area_km2_official', 'n/d')} km², "
    f"CRS {aoi.get('crs', 'n/d')}."
)
if aoi.get("why_pt"):
    st.write(aoi["why_pt"])

candidate = catalog.get("candidate") or {}
st.subheader("Cena consultada")
if not candidate:
    st.write("Nenhuma cena de cobertura completa foi registrada.")
else:
    st.write(f"Produto: `{candidate.get('product_id')}`")
    st.write(f"Aquisição: {candidate.get('datetime') or 'n/d'}")
    st.write(f"Fonte: {catalog.get('source') or 'n/d'}")
    cloud = candidate.get("eo_cloud_cover")
    st.write(
        "Nuvem do item STAC: "
        + ("n/d" if cloud is None else f"{cloud}%")
        + ". Isso não é a cobertura válida dentro do município."
    )
    fraction = candidate.get("valid_pixel_fraction")
    st.write(
        "Fração de pixels válidos na AOI: "
        + ("não medida" if fraction is None else str(fraction))
    )
    st.write(f"Cena aceita para NDVI: {candidate.get('accepted') is True}")

st.subheader("Limitações")
st.write(
    "Sem raster publicado não há mapa de NDVI. "
    "O download oficial das bandas exige credencial do Copernicus Data Space. "
    "A atualização é manual. O estado inteiro não foi processado."
)
render_footer()
