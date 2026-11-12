"""Gera evidências HTML/PNG do painel energético (MVP 10).

Preferência: Playwright. Fallback: Matplotlib coroplético simplificado.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.energy.siga_aggregate import load_energy_panel_bundle  # noqa: E402
from geoai.portal.energy_panel import energy_map_html  # noqa: E402
from geoai.portal.municipal_explorer import load_municipality_layer  # noqa: E402

OUT = REPO / "docs" / "evidence" / "mvp10"
OUT.mkdir(parents=True, exist_ok=True)


def _write_html(name: str, code: str | None) -> Path:
    mun = load_municipality_layer(REPO)
    energy = load_energy_panel_bundle(REPO)
    html = energy_map_html(
        mun,
        energy,
        selected_code=code,
        metric="potencia_fiscalizada_mw",
    )
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

    mun = load_municipality_layer(REPO)
    energy = load_energy_panel_bundle(REPO)
    gdf = mun.gdf.to_crs(epsg=4326).copy()
    by_code = {
        str(r["CD_MUN"]): r
        for r in (energy.panel.get("municipalities") or [])
    }
    gdf["mw"] = gdf["CD_MUN"].astype(str).map(
        lambda c: float((by_code.get(c) or {}).get("potencia_fiscalizada_mw") or 0.0)
    )
    fig, ax = plt.subplots(1, 1, figsize=(10, 7), dpi=120)
    gdf.plot(
        ax=ax,
        column="mw",
        cmap="YlOrRd",
        legend=True,
        edgecolor="#0b2545",
        linewidth=0.2,
        missing_kwds={"color": "#dbe4ee"},
    )
    if code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(code)]
        if not hit.empty:
            hit.boundary.plot(ax=ax, color="#7c2d12", linewidth=1.4)
            minx, miny, maxx, maxy = hit.total_bounds
            pad = 0.15
            ax.set_xlim(minx - pad, maxx + pad)
            ax.set_ylim(miny - pad, maxy + pad)
            title = f"SIGA MW — {hit.iloc[0]['NM_MUN']} ({code})"
        else:
            title = f"SIGA MW — código {code}"
    else:
        title = "Paraná — capacidade fiscalizada SIGA (MW)"
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    png = OUT / f"{name}.png"
    fig.savefig(png, bbox_inches="tight", facecolor="#e8eef5")
    plt.close(fig)
    return png


def main() -> int:
    cases = [
        ("mapa_geral_mw", None),
        ("mapa_maringa", "4115200"),
        ("mapa_foz", "4108304"),
        ("mapa_comparacao_curitiba", "4106902"),
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
