"""Serviço de apresentação do NDVI estadual. Só lê artefatos estáticos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoai.portal.municipal_explorer import MunicipalityLayerBundle
from geoai.sentinel.targets import load_ndvi_plan, load_ndvi_targets, target_status

__all__ = ["STATUS_STYLE", "load_ndvi_overview", "ndvi_targets_map_html"]

STATUS_STYLE: dict[str, tuple[str, str]] = {
    "publicado": ("#15803d", "NDVI publicado"),
    "medido": ("#0e7490", "Cena medida, NDVI não publicado"),
    "planejado": ("#d97706", "Passagem candidata, sem medição"),
    "sem_passagem": ("#b91c1c", "Sem passagem na janela"),
    "aguardando": ("#64748b", "Aguardando processamento"),
}


def _pilot_catalog(repo_root: Path) -> dict[str, Any] | None:
    path = Path(repo_root) / "data" / "derived" / "sentinel_maringa_pilot.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_ndvi_overview(repo_root: Path) -> dict[str, Any]:
    """Alvos com estado público. ``available`` falso se a lista não existe."""

    registry = load_ndvi_targets(repo_root)
    if registry is None:
        return {
            "available": False,
            "missing_reason_pt": (
                "Lista de municípios-alvo ausente. Gere com "
                "scripts/prepare_ndvi_targets.py."
            ),
        }
    catalog = _pilot_catalog(repo_root)
    plan = load_ndvi_plan(repo_root)
    rows = []
    counts = dict.fromkeys(STATUS_STYLE, 0)
    for target in registry["targets"]:
        status = target_status(target["cd_mun"], catalog, plan)
        counts[status["code"]] += 1
        rows.append({**target, "status": status})
    return {
        "available": True,
        "registry": registry,
        "rows": rows,
        "counts": counts,
        "plan": plan,
        "pilot_catalog": catalog,
    }


def ndvi_targets_map_html(
    mun_bundle: MunicipalityLayerBundle, overview: dict[str, Any]
) -> str:
    try:
        import folium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("folium necessário: pip install 'napi-geoai[ui]'") from exc
    if not mun_bundle.available or not overview.get("available"):
        raise FileNotFoundError("malha ou lista de alvos indisponível")

    by_code = {row["cd_mun"]: row for row in overview["rows"]}
    gdf = mun_bundle.gdf.to_crs(epsg=4326).copy()
    codes = gdf["CD_MUN"].astype(str)
    gdf["ndvi_alvo"] = [code in by_code for code in codes]
    gdf["ndvi_status"] = [
        by_code[code]["status"]["code"] if code in by_code else "fora" for code in codes
    ]
    gdf["ndvi_texto"] = [
        by_code[code]["status"]["label_pt"]
        if code in by_code
        else "Fora da lista (até 20 mil habitantes)"
        for code in codes
    ]
    gdf["ndvi_pop"] = [
        f"{by_code[code]['population']:,}".replace(",", ".")
        if code in by_code
        else "—"
        for code in codes
    ]
    minx, miny, maxx, maxy = gdf.total_bounds
    fmap = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
        status = (feat.get("properties") or {}).get("ndvi_status")
        if status in STATUS_STYLE:
            return {
                "fillColor": STATUS_STYLE[status][0],
                "color": "#0f172a",
                "weight": 0.9,
                "fillOpacity": 0.62,
            }
        return {
            "fillColor": "#e2e8f0",
            "color": "#94a3b8",
            "weight": 0.4,
            "fillOpacity": 0.25,
        }

    folium.GeoJson(
        data=json.loads(gdf.to_json()),
        name="Municípios-alvo do NDVI",
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["NM_MUN", "CD_MUN", "ndvi_pop", "ndvi_texto"],
            aliases=["Município", "Código IBGE", "População estimada", "Situação"],
        ),
    ).add_to(fmap)
    fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
    return fmap.get_root().render()
