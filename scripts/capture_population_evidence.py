"""Evidências HTML/PNG dos mapas temáticos populacionais (MVP 11)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.population.panel import load_population_panel_bundle  # noqa: E402
from geoai.portal.municipal_explorer import load_municipality_layer  # noqa: E402
from geoai.portal.municipal_profile import population_map_html  # noqa: E402

OUT = REPO / "docs" / "evidence" / "mvp11"
OUT.mkdir(parents=True, exist_ok=True)


def _matplotlib_fallback(name: str, metric: str, code: str | None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mun = load_municipality_layer(REPO)
    pop = load_population_panel_bundle(REPO)
    gdf = mun.gdf.to_crs(epsg=4326).copy()
    by = {str(r["CD_MUN"]): r for r in (pop.panel.get("municipalities") or [])}
    gdf["val"] = gdf["CD_MUN"].astype(str).map(
        lambda c: (by.get(c) or {}).get(metric)
    )
    fig, ax = plt.subplots(1, 1, figsize=(10, 7), dpi=120)
    gdf.plot(
        ax=ax,
        column="val",
        cmap="YlGnBu",
        legend=True,
        edgecolor="#0b2545",
        linewidth=0.2,
        missing_kwds={"color": "#dbe4ee"},
    )
    if code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(code)]
        if not hit.empty:
            hit.boundary.plot(ax=ax, color="#7c2d12", linewidth=1.4)
    ax.set_title(metric)
    ax.set_axis_off()
    fig.tight_layout()
    png = OUT / f"{name}.png"
    fig.savefig(png, bbox_inches="tight", facecolor="#e8eef5")
    plt.close(fig)
    return png


def main() -> int:
    mun = load_municipality_layer(REPO)
    pop = load_population_panel_bundle(REPO)
    if not mun.available or not pop.available:
        raise SystemExit("malha ou painel populacional indisponível")
    cases = [
        ("mapa_populacao_2026", "populacao_estimada_2026_hab", None),
        (
            "mapa_densidade_2026",
            "densidade_demografica_estimada_2026_hab_km2",
            None,
        ),
        (
            "mapa_kw_hab_maringa",
            "potencia_fiscalizada_conhecida_kw_por_habitante",
            "4115200",
        ),
    ]
    for name, metric, code in cases:
        html = population_map_html(
            mun, pop, metric=metric, selected_code=code
        )
        html_path = OUT / f"{name}.html"
        html_path.write_text(html, encoding="utf-8")
        png = OUT / f"{name}.png"
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
                page.wait_for_timeout(1200)
                page.screenshot(path=str(png), full_page=False)
                browser.close()
        except Exception:
            _matplotlib_fallback(name, metric, code)
        print(f"ok {name}")
        html_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
