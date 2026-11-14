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

candidate = catalog.get("candidate") or {}
st.subheader("Cena consultada")
if not candidate:
    st.write("Nenhuma cena de cobertura geométrica suficiente foi registrada.")
else:
    st.write(f"Produto: `{candidate.get('product_id')}`")
    st.write(f"Aquisição: {candidate.get('datetime') or 'n/d'}")
    st.write(f"Tile MGRS: {candidate.get('mgrs_tile') or 'n/d'}")
    st.write(f"Fonte: {catalog.get('source') or 'n/d'}")
    criteria = catalog.get("criteria") or {}
    st.write(f"Janela usada: {criteria.get('window_used', 'n/d')}")
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

tiles = catalog.get("tiles") or []
if tiles:
    st.subheader("Tiles que intersectam o município")
    st.dataframe(tiles, use_container_width=True, hide_index=True)
union = catalog.get("tile_union_coverage")
if union is not None:
    st.write(f"União dos footprints, um por tile: {union}")

probe_scene = catalog.get("access_probe_scene") or {}
if probe_scene and not candidate:
    st.subheader("Inspeção de acesso")
    st.write(
        "A cena abaixo não atinge a cobertura de uma tile só. "
        "Ela não foi aceita e não gerou NDVI."
    )
    st.write(f"Produto: `{probe_scene.get('product_id')}`")
    st.write(f"Aquisição: {probe_scene.get('datetime') or 'n/d'}")
    st.write(f"Tile: {probe_scene.get('mgrs_tile') or 'n/d'}")
    st.write(f"Cobertura geométrica: {probe_scene.get('aoi_coverage')}")

access = catalog.get("asset_access") or {}
probe = access.get("probe") or {}
if access:
    st.subheader("Acesso às bandas")
    st.write(f"Host HTTPS sondado: {access.get('https_host') or 'n/d'}")
    st.write(f"HTTP da requisição sem Authorization: {probe.get('http_status', 'n/d')}")
    schemes = ((access.get("collection") or {}).get("auth_schemes") or {}).keys()
    st.write("Esquemas declarados na coleção: " + (", ".join(schemes) or "n/d"))
    if access.get("openid_token_endpoint"):
        st.write(f"Token endpoint OIDC publicado: {access['openid_token_endpoint']}")

st.subheader("Limitações")
st.write(
    "Sem raster publicado não há mapa de NDVI. "
    "A fração válida no município só existe depois da leitura de B04, B08 e SCL. "
    "A atualização é manual. O estado inteiro não foi processado. "
    "O comando de preparo ainda não implementa o recorte georreferenciado."
)
render_footer()
