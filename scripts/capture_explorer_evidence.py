"""Gera evidências HTML/PNG do explorador (MVP 09.1).

Preferência: Playwright (se instalado). Caso contrário, grava HTML Folium
inspecionável e um mosaico Matplotlib dos limites (sem basemap).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.portal.municipal_explorer import (  # noqa: E402
    load_municipality_layer,
    municipality_map_html,
)

OUT = REPO / "docs" / "evidence" / "mvp09_1"
OUT.mkdir(parents=True, exist_ok=True)


def _write_html(name: str, code: str | None) -> Path:
    bundle = load_municipality_layer(REPO)
    html = municipality_map_html(bundle, selected_code=code, fill_opacity=0.28)
    path = OUT / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _try_playwright(html_path: Path, png_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(png_path), full_page=False)
        browser.close()
    return png_path.is_file()


def _matplotlib_fallback(name: str, code: str | None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bundle = load_municipality_layer(REPO)
    gdf = bundle.gdf.to_crs(epsg=4326)
    fig, ax = plt.subplots(1, 1, figsize=(10, 7), dpi=120)
    gdf.boundary.plot(ax=ax, linewidth=0.25, color="#0b2545")
    gdf.plot(ax=ax, color="#1f4e79", alpha=0.28, edgecolor="#0b2545", linewidth=0.2)
    if code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(code)]
        if not hit.empty:
            hit.plot(
                ax=ax,
                color="#c45c26",
                alpha=0.75,
                edgecolor="#7c2d12",
                linewidth=1.2,
            )
            minx, miny, maxx, maxy = hit.total_bounds
            pad = 0.15
            ax.set_xlim(minx - pad, maxx + pad)
            ax.set_ylim(miny - pad, maxy + pad)
            title = f"Seleção {hit.iloc[0]['NM_MUN']} ({code})"
        else:
            title = f"Código {code}"
    else:
        title = "Paraná — 399 municípios (visão geral)"
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    png = OUT / f"{name}.png"
    fig.savefig(png, bbox_inches="tight", facecolor="#e8eef5")
    plt.close(fig)
    return png


def main() -> int:
    cases = [
        ("mapa_geral_399", None),
        ("mapa_maringa", "4115200"),
        ("mapa_codigo_4115200", "4115200"),
        ("mapa_comparacao_ref_londrina", "4113700"),
    ]
    for name, code in cases:
        html_path = _write_html(name, code)
        png_path = OUT / f"{name}.png"
        if not _try_playwright(html_path, png_path):
            _matplotlib_fallback(name, code)
        print(f"ok {name} html={html_path.name} png={png_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
