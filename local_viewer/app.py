"""Visualizador local de NDVI. Não é a entrada do Streamlit Cloud."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402
from geoai.viewer.config import load_config  # noqa: E402
from geoai.viewer.map_html import build_map_html  # noqa: E402
from geoai.viewer.policy import (  # noqa: E402
    local_downloads_enabled,
    public_downloads_enabled,
)
from geoai.viewer.session import (  # noqa: E402
    REASON_PT,
    ListedDate,
    ProductView,
    load_index,
    scientific_panel,
)

QUALITY_PT = {
    "approved": "Aprovado",
    "approved_with_reservations": "Aprovado com ressalvas",
}
MIME = {
    "png": "image/png",
    "png_legend": "image/png",
    "geotiff": "image/tiff",
    "json": "application/json",
    "csv": "text/csv",
}
OFFERED = ("png", "png_legend", "geotiff", "json")

_CSS = """
<style>
.block-container { padding-top: 1.1rem; }
.napi-hero {
  background: #ffffff;
  border: 1px solid #d5deea;
  border-left: 5px solid #1f4e79;
  border-radius: 8px;
  padding: 0.45rem 0.85rem;
  margin-bottom: 0.55rem;
}
.napi-kicker {
  margin: 0;
  color: #1f4e79;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.napi-hero h1 { margin: 0; color: #0b2545; font-size: 1.25rem; }
.napi-hero p { margin: 0; color: #334155; font-size: 0.9rem; }
</style>
"""


def _pt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _percent(value: float) -> str:
    return f"{value * 100:.2f}".replace(".", ",") + "%"


def _date_text(item: ListedDate) -> str:
    year, month, day = item.image_date.split("-")
    label = f"{day}/{month}/{year}"
    if item.loaded:
        return label
    return f"{label} — sem produto carregado"


def _render_map(product: ProductView) -> None:
    if product.map_spec is None:
        for code in product.block_reasons:
            st.error(REASON_PT.get(code, code))
        return
    spec = product.map_spec
    page = build_map_html(
        spec.png,
        {
            "width": spec.width,
            "height": spec.height,
            "geotransform": spec.geotransform,
            "epsg": spec.epsg,
            "stops": spec.stops,
            "gray": spec.gray,
            "note": spec.note,
            "title": spec.title,
            "place": spec.place,
            "date_label": spec.date_label,
            "acquisition": spec.acquisition,
            "resolution": spec.resolution,
        },
    )
    st.iframe(page, height=900)
    st.caption("Norte na primeira linha. O zoom só amplia a visualização.")


def _render_science(product: ProductView) -> None:
    panel = scientific_panel(product)
    quality = QUALITY_PT.get(panel["quality_status"], panel["quality_status"])
    st.subheader("Indicadores")
    if panel["numbers_confirmed"]:
        st.caption("Números confirmados no catálogo público e no manifesto local.")
    else:
        st.caption(
            "Números lidos do catálogo público. O produto local não foi confirmado."
        )
    place, date, satellite, resolution = st.columns(4)
    place.metric("Município", f"{product.name} — {product.uf}")
    date.metric("Data", product.date_label)
    satellite.metric("Satélite", panel["satellite"])
    resolution.metric("Resolução", f"{panel['spatial_resolution_m']:g} m")
    valid, usable, status = st.columns(3)
    valid.metric("Pixels válidos", _pt_int(panel["n_valid"]))
    usable.metric("Dados utilizáveis", _percent(panel["valid_pixel_fraction"]))
    status.metric("Qualidade", quality)
    st.caption(
        f"Fração de pixels válidos: {panel['valid_pixel_fraction']}. "
        f"Pixels do município: {_pt_int(panel['n_aoi'])}. "
        "O percentual é de dados utilizáveis, não de vegetação."
    )
    st.warning(
        f"{_pt_int(panel['anomalous'])} pixels válidos ficam fora de [-1, 1]. "
        "Eles aparecem em cinza e não indicam vegetação."
    )
    with st.expander("Como interpretar o NDVI?"):
        st.markdown(
            "O NDVI compara a luz vermelha, absorvida pela vegetação, com o "
            "infravermelho próximo, que a vegetação reflete com mais intensidade. "
            f"A fonte deste mapa é {panel['source']}, satélite {panel['satellite']}."
        )
        st.markdown(
            "Amarelo indica pouca vegetação, solo exposto ou superfície não "
            "vegetada. Verde indica maior resposta espectral da vegetação. "
            "São leituras indicativas, não uma classificação definitiva do solo."
        )
        st.markdown(
            "Nuvens, sombra e falhas de observação ficam transparentes. "
            "Esses pontos não entram no percentual de dados utilizáveis."
        )
        st.markdown(
            "NDVI alto não comprova, sozinho, saúde da planta, produtividade "
            "agrícola nem o tipo de vegetação."
        )
    for code in product.warnings:
        st.warning(REASON_PT.get(code, "A proveniência local não foi validada."))


def _offer_download(product: ProductView, key: str) -> bool:
    path = product.download_paths.get(key)
    item = product.local_files[key]
    if path is None or not item.validated or not item.exists or not item.filename:
        return False
    st.download_button(
        f"Baixar {item.label}",
        data=path.read_bytes(),
        file_name=item.filename,
        mime=MIME[key],
        key=f"local-{product.ibge}-{key}",
    )
    return True


def _render_downloads(product: ProductView, *, allowed: bool, address: str) -> None:
    del address
    st.subheader("Baixar dados")
    if public_downloads_enabled() or not allowed:
        st.info("Os arquivos deste mapa não estão disponíveis para download.")
        return
    for key in OFFERED:
        if not _offer_download(product, key):
            label = product.local_files[key].label
            st.write(f"{label} não está disponível.")
    csv = product.local_files["csv"]
    if csv.exists and csv.validated:
        _offer_download(product, "csv")


def main() -> None:
    st.set_page_config(
        page_title="NAPI GeoAI — Observatório de Vegetação",
        layout="wide",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        """
<div class="napi-hero">
  <p class="napi-kicker">Ambiente local de testes</p>
  <h1>NAPI GeoAI — Observatório de Vegetação</h1>
  <p>Análise territorial por imagens de satélite.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    try:
        config = load_config()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.error(REASON_PT.get(str(exc), "A configuração local é inválida."))
        return

    science = None if config is None else config.science_dir
    preview = None if config is None else config.preview_dir
    index = load_index(ROOT, science, preview)
    if index.errors:
        st.error("Catálogo bloqueado: " + ", ".join(index.errors))
    if not index.products:
        st.warning("Nenhum município verificado no catálogo.")
        return

    labels = [f"{item.name} — {item.uf} ({item.ibge})" for item in index.products]
    selected = st.sidebar.selectbox("Município", labels)
    product = index.products[labels.index(selected)]
    chosen = st.sidebar.selectbox(
        "Data de aquisição", product.dates, format_func=_date_text
    )
    st.sidebar.selectbox("Tipo de produto", [product.product_type])
    status = product.entry["quality"]["status"]
    quality = QUALITY_PT.get(status, status)
    st.sidebar.markdown(f"**Qualidade**\n\n{quality}")
    address = str(st.get_option("server.address") or "")
    requested = bool(config and config.local_test_downloads)
    allowed = local_downloads_enabled(requested, address)

    if not chosen.loaded:
        st.info("Esta data consta no catálogo, mas não há produto carregado para ela.")
        return
    _render_map(product)
    _render_science(product)
    _render_downloads(product, allowed=allowed, address=address)


if __name__ == "__main__":
    main()
