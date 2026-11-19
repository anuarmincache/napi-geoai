"""Serviço de apresentação do painel agropecuário (IBGE PAM e PPM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoai.agriculture import PAM_VARIABLES, PPM_INDICATORS, STATUS_NO_RECORD
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.connectors.sidra import (
    STATUS_NOT_APPLICABLE,
    STATUS_SUPPRESSED,
    STATUS_UNAVAILABLE,
    STATUS_VALUE,
    STATUS_ZERO,
)
from geoai.portal.municipal_explorer import MunicipalityLayerBundle
from geoai.portal.paths import (
    agro_panel_path,
    agro_provenance_path,
    agro_quality_path,
    repo_root_from_here,
)

__all__ = [
    "AgroIndicator",
    "AgroPanelBundle",
    "STATUS_LABELS_PT",
    "agro_attribution_lines",
    "agro_cell",
    "agro_format_cell",
    "agro_indicator",
    "agro_map_html",
    "agro_ranked",
    "agro_state_summary",
    "list_agro_crops",
    "load_agro_panel_bundle",
]

STATUS_LABELS_PT = {
    STATUS_VALUE: "valor publicado",
    STATUS_ZERO: "zero (IBGE: zero absoluto)",
    STATUS_NOT_APPLICABLE: "não se aplica",
    STATUS_UNAVAILABLE: "não disponível no IBGE",
    STATUS_SUPPRESSED: "sigilo estatístico (X)",
    STATUS_NO_RECORD: "sem registro na tabela",
}
PAM_LABELS_PT = {
    "area_plantada": "Área plantada",
    "area_colhida": "Área colhida",
    "producao": "Quantidade produzida",
    "rendimento": "Rendimento médio",
}
PPM_LABELS_PT = {
    "bovinos": "Bovinos",
    "suinos": "Suínos",
    "galinaceos": "Galináceos",
    "leite": "Leite",
}
_REQUIRED = ("schema_version", "pam", "ppm", "municipalities", "totals")


@dataclass(frozen=True, slots=True)
class AgroPanelBundle:
    available: bool
    panel: dict[str, Any]
    provenance: dict[str, Any]
    quality: dict[str, Any]
    missing_reason_pt: str | None = None


@dataclass(frozen=True, slots=True)
class AgroIndicator:
    """Indicador exibível: pecuária (PPM) ou cultura × variável (PAM)."""

    group: str  # "ppm" | "pam"
    key: str
    crop_id: str | None
    label_pt: str
    unit: str
    year: str
    source_pt: str
    summable: bool


def _fail(reason: str, **kw: dict[str, Any]) -> AgroPanelBundle:
    return AgroPanelBundle(
        available=False,
        panel=kw.get("panel", {}),
        provenance=kw.get("provenance", {}),
        quality=kw.get("quality", {}),
        missing_reason_pt=reason,
    )


def load_agro_panel_bundle(repo_root: Path | None = None) -> AgroPanelBundle:
    root = Path(repo_root) if repo_root is not None else repo_root_from_here()
    paths = (agro_panel_path(root), agro_provenance_path(root), agro_quality_path(root))
    if not all(p.is_file() for p in paths):
        return _fail(
            "Artefatos agropecuários ausentes. Gere com "
            "scripts/prepare_agro_parana.py (sem download no Streamlit)."
        )
    try:
        panel, provenance, quality = (
            json.loads(p.read_text(encoding="utf-8")) for p in paths
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _fail(f"Artefato agropecuário ilegível/corrompido: {exc}")
    kw = {"panel": panel, "provenance": provenance, "quality": quality}
    missing = [k for k in _REQUIRED if k not in panel]
    if missing:
        return _fail("Painel agropecuário sem chaves: " + ", ".join(missing), **kw)
    if panel.get("schema_version") != 1:
        return _fail("Versão de esquema do painel agropecuário desconhecida.", **kw)
    n = len(panel.get("municipalities") or {})
    if n != EXPECTED_PR_MUNICIPALITY_COUNT:
        return _fail(
            f"Painel com {n} municípios; esperado {EXPECTED_PR_MUNICIPALITY_COUNT}.",
            **kw,
        )
    if not quality.get("reconcile_ok"):
        return _fail("quality.reconcile_ok ≠ true — painel rejeitado.", **kw)
    if set(panel["pam"].get("variables") or {}) != set(PAM_VARIABLES):
        return _fail("Variáveis PAM diferentes do contrato.", **kw)
    if set(panel["ppm"].get("indicators") or {}) != set(PPM_INDICATORS):
        return _fail("Indicadores PPM diferentes do contrato.", **kw)
    return AgroPanelBundle(True, panel, provenance, quality, None)


def list_agro_crops(bundle: AgroPanelBundle) -> list[dict[str, Any]]:
    return list(bundle.panel["pam"]["crops"]) if bundle.available else []


def agro_indicator(
    bundle: AgroPanelBundle, group: str, key: str, crop_id: str | None = None
) -> AgroIndicator:
    if group == "ppm":
        ind = bundle.panel["ppm"]["indicators"][key]
        year = bundle.panel["ppm"][
            "year_rebanho" if ind["grupo"] == "rebanho" else "year_produto"
        ]
        return AgroIndicator(
            group="ppm",
            key=key,
            crop_id=None,
            label_pt=f"{PPM_LABELS_PT[key]} ({ind['variable_name']})",
            unit=str(ind["unit"]),
            year=str(year),
            source_pt=(
                "IBGE, Pesquisa da Pecuária Municipal, "
                f"categoria «{ind['category_name']}»"
            ),
            summable=True,
        )
    var = bundle.panel["pam"]["variables"][key]
    crop = next(c for c in list_agro_crops(bundle) if str(c["id"]) == str(crop_id))
    return AgroIndicator(
        group="pam",
        key=key,
        crop_id=str(crop_id),
        label_pt=f"{PAM_LABELS_PT[key]} — {crop['name']}",
        unit=str(var["unit"]),
        year=str(bundle.panel["pam"]["year"]),
        source_pt=f"IBGE, Produção Agrícola Municipal, variável «{var['name']}»",
        summable=key != "rendimento",
    )


def agro_cell(
    bundle: AgroPanelBundle, code: str, ind: AgroIndicator
) -> tuple[float | None, str]:
    row = (bundle.panel["municipalities"].get(str(code)) or {}).get(ind.group) or {}
    cell = (
        row.get(ind.key)
        if ind.group == "ppm"
        else (row.get(str(ind.crop_id)) or {}).get(ind.key)
    )
    if not cell:
        return None, STATUS_NO_RECORD
    value, status = cell
    return (float(value) if value is not None else None), str(status)


def _number_br(value: float) -> str:
    digits = 0 if float(value).is_integer() else 1
    text = f"{value:,.{digits}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def agro_format_cell(value: float | None, status: str, unit: str) -> str:
    if value is None:
        return STATUS_LABELS_PT.get(status, status)
    return f"{_number_br(value)} {unit}"


def agro_state_summary(bundle: AgroPanelBundle, ind: AgroIndicator) -> dict[str, Any]:
    totals = bundle.panel["totals"][ind.group]
    node = totals[ind.key] if ind.group == "ppm" else totals[str(ind.crop_id)][ind.key]
    return dict(node)


def agro_ranked(
    bundle: AgroPanelBundle,
    ind: AgroIndicator,
    names: dict[str, str],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = []
    for code in bundle.panel["municipalities"]:
        value, status = agro_cell(bundle, code, ind)
        if value is not None and status == STATUS_VALUE:
            rows.append(
                {"CD_MUN": code, "NM_MUN": names.get(code, code), "valor": value}
            )
    rows.sort(key=lambda r: (-r["valor"], r["CD_MUN"]))
    return rows[: max(0, limit)]


def agro_attribution_lines(bundle: AgroPanelBundle) -> tuple[str, ...]:
    if not bundle.available:
        return ()
    panel, prov = bundle.panel, bundle.provenance
    resolved = prov.get("resolved_identifiers") or {}
    lines = [
        f"PAM: IBGE/SIDRA tabela {(resolved.get('pam') or {}).get('table')}, "
        f"ano {panel['pam']['year']}.",
        f"PPM rebanhos: tabela "
        f"{((resolved.get('ppm') or {}).get('rebanho') or {}).get('table')}, "
        f"ano {panel['ppm']['year_rebanho']}. PPM produtos: tabela "
        f"{((resolved.get('ppm') or {}).get('produto') or {}).get('table')}, "
        f"ano {panel['ppm']['year_produto']}.",
        f"Coleta e preparação: {str(prov.get('prepared_at') or '')[:10] or 'n/d'}. "
        f"{prov.get('license_note') or ''}",
        str(panel["pam"].get("crop_selection_rule_pt") or ""),
    ]
    return tuple(line for line in lines if line.strip())


def agro_map_html(
    mun_bundle: MunicipalityLayerBundle,
    bundle: AgroPanelBundle,
    ind: AgroIndicator,
    *,
    selected_code: str | None = None,
    fill_opacity: float = 0.62,
) -> str:
    try:
        import folium
        from branca.colormap import LinearColormap
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("folium necessário: pip install 'napi-geoai[ui]'") from exc
    if not mun_bundle.available or not bundle.available:
        raise FileNotFoundError("malha ou painel agropecuário indisponível")

    gdf = mun_bundle.gdf.to_crs(epsg=4326).copy()
    values: list[float] = []
    shown: list[str] = []
    statuses: list[str] = []
    has_value: list[bool] = []
    for code in gdf["CD_MUN"].astype(str):
        value, status = agro_cell(bundle, code, ind)
        values.append(float(value) if value is not None else 0.0)
        shown.append(agro_format_cell(value, status, ind.unit))
        statuses.append(STATUS_LABELS_PT.get(status, status))
        has_value.append(value is not None)
    gdf["agro_value"] = values
    gdf["agro_text"] = shown
    gdf["agro_status"] = statuses
    gdf["agro_has_value"] = has_value
    known = [v for v, ok in zip(values, has_value, strict=True) if ok]
    vmax = max(known) if known else 1.0
    palette = (
        ["#f7fcf5", "#74c476", "#00441b"]
        if ind.group == "pam"
        else ["#fff5eb", "#fd8d3c", "#7f2704"]
    )
    cmap = LinearColormap(
        colors=palette,
        vmin=0.0,
        vmax=vmax if vmax > 0 else 1.0,
        caption=f"{ind.label_pt} ({ind.unit}), {ind.year}",
    )
    minx, miny, maxx, maxy = gdf.total_bounds
    fmap = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        if props.get("agro_has_value"):
            base = {
                "fillColor": cmap(float(props.get("agro_value") or 0.0)),
                "color": "#334155",
                "weight": 0.6,
                "fillOpacity": fill_opacity,
            }
        else:  # sem dado: cinza hachurado visualmente distinto de zero
            base = {
                "fillColor": "#cbd5e1",
                "color": "#64748b",
                "weight": 0.6,
                "fillOpacity": 0.35,
                "dashArray": "3",
            }
        if selected_code and str(props.get("CD_MUN")) == str(selected_code):
            base.update({"color": "#0ea5e9", "weight": 2.6})
        return base

    folium.GeoJson(
        data=json.loads(gdf.to_json()),
        name=ind.label_pt,
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["NM_MUN", "CD_MUN", "agro_text", "agro_status"],
            aliases=["Município", "Código IBGE", ind.label_pt, "Situação do dado"],
        ),
    ).add_to(fmap)
    cmap.add_to(fmap)
    bounds = [[miny, minx], [maxy, maxx]]
    if selected_code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(selected_code)]
        if not hit.empty:
            b = hit.total_bounds
            bounds = [[b[1], b[0]], [b[3], b[2]]]
    fmap.fit_bounds(bounds, padding=(20, 20))
    return fmap.get_root().render()
