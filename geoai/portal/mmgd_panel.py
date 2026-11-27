"""Serviços do painel MMGD/ANEEL (sem Streamlit).

Contagem primária = empreendimentos. UCs crédito são secundárias.
Filtros categóricos usam os histogramas municipais do artefato derivado;
MW por tecnologia/classe/porte **não** está no painel municipal — no
recorte filtrado a métrica de mapa/ranking é a contagem, não potência
inventada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal.formatos import (
    data_br,
    motivos_de_recusa_pt,
    numero_br,
)
from geoai.portal.municipal_explorer import MunicipalityLayerBundle
from geoai.portal.paths import (
    mmgd_panel_path,
    mmgd_provenance_path,
    mmgd_quality_path,
    repo_root_from_here,
)
from geoai.portal.textos_legados import atualizar

__all__ = [
    "MmgdPanelBundle",
    "compare_municipal_mmgd",
    "list_mmgd_filter_options",
    "load_mmgd_panel_bundle",
    "mmgd_attribution_lines",
    "mmgd_map_html",
    "mmgd_municipalities_list",
    "mmgd_public_notice",
    "mmgd_scope_totals",
    "mmgd_ranked",
    "project_mmgd_metrics",
]

_REQUIRED_PANEL_KEYS = (
    "source_id",
    "municipalities",
    "totals",
    "periodo_referencia",
    "unit_primary",
)
_PII_MARKERS = (
    "NomTitularEmpreendimento",
    "NumCPFCNPJ",
    "CodCEP",
    "NumCoordESub",
    "NumCoordNSub",
)


@dataclass(frozen=True, slots=True)
class MmgdPanelBundle:
    available: bool
    panel: dict[str, Any]
    provenance: dict[str, Any]
    quality: dict[str, Any]
    missing_reason_pt: str | None = None


def _repo_root(repo_root: Path | None = None) -> Path:
    return repo_root or repo_root_from_here()


def _as_mun_list(panel: dict[str, Any]) -> list[dict[str, Any]]:
    raw = panel.get("municipalities")
    if isinstance(raw, dict):
        rows: list[dict[str, Any]] = []
        for code, row in raw.items():
            item = dict(row)
            item.setdefault("cd_mun", str(code))
            item["CD_MUN"] = str(item.get("cd_mun") or code)
            item["NM_MUN"] = str(item.get("nome_fonte") or item.get("NM_MUN") or code)
            rows.append(item)
        rows.sort(key=lambda r: str(r["CD_MUN"]))
        return rows
    if isinstance(raw, list):
        rows = []
        for row in raw:
            item = dict(row)
            code = str(item.get("cd_mun") or item.get("CD_MUN") or "").strip()
            item["CD_MUN"] = code
            item["cd_mun"] = code
            item["NM_MUN"] = str(item.get("nome_fonte") or item.get("NM_MUN") or code)
            rows.append(item)
        return rows
    return []


def _recorte_em_portugues(scope: object) -> str:
    """Nomeia o recorte ativo em linguagem comum, sem o código interno."""
    bruto = str(scope or "").strip().lower()
    if bruto in ("", "todas", "todos", "todas_classes"):
        return "todos os registros"
    return bruto.replace("_", " ")


def mmgd_municipalities_list(bundle: MmgdPanelBundle) -> list[dict[str, Any]]:
    return _as_mun_list(bundle.panel)


def _bucket_count(row: dict[str, Any], field: str, key: str) -> int:
    bucket = row.get(field) or {}
    if not isinstance(bucket, dict):
        return 0
    return int(bucket.get(key) or 0)


def _active_filters(
    *,
    tipo: str | None,
    classe: str | None,
    porte: str | None,
) -> dict[str, str]:
    active: dict[str, str] = {}
    if tipo:
        active["tipo"] = tipo
    if classe:
        active["classe"] = classe
    if porte:
        active["porte"] = porte
    return active


def project_mmgd_metrics(
    row: dict[str, Any],
    *,
    tipo: str | None = None,
    classe: str | None = None,
    porte: str | None = None,
) -> dict[str, Any]:
    """Projeta n/MW/UC no escopo. Multi-filtro categórico → fail-closed."""

    out = dict(row)
    out["CD_MUN"] = str(row.get("CD_MUN") or row.get("cd_mun") or "")
    out["NM_MUN"] = str(row.get("NM_MUN") or row.get("nome_fonte") or "")
    active = _active_filters(tipo=tipo, classe=classe, porte=porte)
    if len(active) > 1:
        out["metric_scope"] = "filtro_incompativel"
        out["filter_ok"] = False
        out["display_n"] = None
        out["display_mw"] = None
        out["display_uc"] = None
        out["display_metric"] = None
        out["map_metric"] = "n_empreendimentos"
        out["mw_available_in_scope"] = False
        out["status_dados"] = "filtro_incompativel"
        out["filter_note_pt"] = (
            "O painel agregado não tem tabela cruzada tipo×classe×porte. "
            "Selecione no máximo um filtro categórico por vez."
        )
        return out

    out["filter_ok"] = True
    out["filter_note_pt"] = None
    if not active:
        n = int(row.get("n_empreendimentos") or 0)
        mw = row.get("potencia_instalada_mw_conhecida")
        uc = row.get("qtd_uc_recebe_credito")
        out["metric_scope"] = "todas"
        out["display_n"] = n
        out["display_mw"] = float(mw) if mw is not None else None
        out["display_uc"] = int(uc) if uc is not None else None
        out["display_metric"] = out["display_mw"]
        out["map_metric"] = "potencia_instalada_mw_conhecida"
        out["mw_available_in_scope"] = True
        out["status_dados"] = "com_registros" if n > 0 else "zero_no_cadastro_pr"
        return out

    dim, key = next(iter(active.items()))
    field = {
        "tipo": "by_tipo",
        "classe": "by_classe",
        "porte": "by_porte",
    }[dim]
    n = _bucket_count(row, field, key)
    out["metric_scope"] = f"{dim}:{key}"
    out["display_n"] = n
    out["display_mw"] = None  # não inventar MW no subconjunto
    out["display_uc"] = None
    out["display_metric"] = float(n)
    out["map_metric"] = "n_empreendimentos"
    out["mw_available_in_scope"] = False
    out["status_dados"] = "com_registros" if n > 0 else "zero_no_cadastro_pr"
    out["filter_note_pt"] = (
        f"Escopo «{dim}:{key}»: contagem de empreendimentos no histograma "
        "municipal. Potência (MW) e UCs crédito não estão desagregadas neste "
        "artefato — ausente ≠ zero."
    )
    return out


def list_mmgd_filter_options(
    bundle: MmgdPanelBundle,
) -> dict[str, tuple[str, ...]]:
    totals = bundle.panel.get("totals") or {}
    tipos = tuple(sorted(str(k) for k in (totals.get("by_tipo") or {})))
    classes = tuple(sorted(str(k) for k in (totals.get("by_classe") or {})))
    portes: set[str] = set()
    for row in _as_mun_list(bundle.panel):
        portes.update(str(k) for k in (row.get("by_porte") or {}))
    return {
        "tipo": tipos,
        "classe": classes,
        "porte": tuple(sorted(portes)),
    }


def load_mmgd_panel_bundle(repo_root: Path | None = None) -> MmgdPanelBundle:
    root = _repo_root(repo_root)
    panel_p = mmgd_panel_path(root)
    prov_p = mmgd_provenance_path(root)
    qual_p = mmgd_quality_path(root)
    if not panel_p.is_file() or not prov_p.is_file() or not qual_p.is_file():
        return MmgdPanelBundle(
            available=False,
            panel={},
            provenance={},
            quality={},
            missing_reason_pt=(
                "Artefatos MMGD ausentes. Gere com "
                "scripts/prepare_mmgd_parana.py (sem download no Streamlit)."
            ),
        )
    try:
        panel_text = panel_p.read_text(encoding="utf-8")
        panel = json.loads(panel_text)
        provenance = json.loads(prov_p.read_text(encoding="utf-8"))
        quality = json.loads(qual_p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return MmgdPanelBundle(
            available=False,
            panel={},
            provenance={},
            quality={},
            missing_reason_pt=f"Artefato MMGD ilegível/corrompido: {exc}",
        )

    for marker in _PII_MARKERS:
        if marker in panel_text:
            return MmgdPanelBundle(
                available=False,
                panel={},
                provenance=provenance,
                quality=quality,
                missing_reason_pt=(
                    f"Campo potencialmente pessoal «{marker}» presente no "
                    "painel público — carregamento bloqueado."
                ),
            )

    missing = [k for k in _REQUIRED_PANEL_KEYS if k not in panel]
    if missing:
        return MmgdPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            missing_reason_pt=(
                "Painel MMGD incompatível — chaves ausentes: " + ", ".join(missing)
            ),
        )

    rows = _as_mun_list(panel)
    if len(rows) != EXPECTED_PR_MUNICIPALITY_COUNT:
        return MmgdPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            missing_reason_pt=(
                f"Painel com {len(rows)} municípios; esperado "
                f"{EXPECTED_PR_MUNICIPALITY_COUNT}."
            ),
        )
    if not quality.get("reconcile_ok"):
        return MmgdPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            missing_reason_pt="quality.reconcile_ok ≠ true — painel rejeitado.",
        )
    totals = panel.get("totals") or {}
    if int(totals.get("n_empreendimentos") or -1) != int(quality.get("n_valid") or -2):
        return MmgdPanelBundle(
            available=False,
            panel=panel,
            provenance=provenance,
            quality=quality,
            missing_reason_pt=(
                "Totais do painel ≠ n_valid da qualidade — inconsistência."
            ),
        )

    # Normaliza municipalities para lista estável no bundle em memória
    panel = dict(panel)
    panel["municipalities"] = rows
    panel["municipality_count"] = len(rows)
    return MmgdPanelBundle(
        available=True,
        panel=panel,
        provenance=provenance,
        quality=quality,
        missing_reason_pt=None,
    )


def mmgd_scope_totals(
    bundle: MmgdPanelBundle,
    *,
    tipo: str | None = None,
    classe: str | None = None,
    porte: str | None = None,
) -> dict[str, Any]:
    projected = [
        project_mmgd_metrics(r, tipo=tipo, classe=classe, porte=porte)
        for r in mmgd_municipalities_list(bundle)
    ]
    active = _active_filters(tipo=tipo, classe=classe, porte=porte)
    if len(active) > 1:
        return {
            "metric_scope": "filtro_incompativel",
            "filter_ok": False,
            "municipality_count": EXPECTED_PR_MUNICIPALITY_COUNT,
            "n_empreendimentos": None,
            "potencia_instalada_mw_conhecida": None,
            "qtd_uc_recebe_credito_total": None,
            "n_municipios_com_registros": None,
            "mw_available_in_scope": False,
            "kpi_caption_pt": (
                "Filtros incompatíveis: selecione no máximo uma dimensão."
            ),
            "filter_note_pt": projected[0].get("filter_note_pt") if projected else None,
        }

    if not active:
        totals = bundle.panel.get("totals") or {}
        n = int(totals.get("n_empreendimentos") or 0)
        mw = totals.get("potencia_instalada_mw_conhecida")
        uc = totals.get("qtd_uc_recebe_credito_total")
        n_mun = int(totals.get("municipios_com_registros") or 0)
        scope = "todas"
        mw_ok = True
    else:
        n = sum(int(r.get("display_n") or 0) for r in projected)
        mw = None
        uc = None
        n_mun = sum(1 for r in projected if int(r.get("display_n") or 0) > 0)
        scope = projected[0].get("metric_scope") if projected else "filtrado"
        mw_ok = False

    return {
        "metric_scope": scope,
        "filter_ok": True,
        "municipality_count": EXPECTED_PR_MUNICIPALITY_COUNT,
        "municipality_count_expected": EXPECTED_PR_MUNICIPALITY_COUNT,
        "n_empreendimentos": n,
        "potencia_instalada_mw_conhecida": (float(mw) if mw is not None else None),
        "qtd_uc_recebe_credito_total": int(uc) if uc is not None else None,
        "n_municipios_com_registros": n_mun,
        "mw_available_in_scope": mw_ok,
        "kpi_caption_pt": (
            f"Números acima: {_recorte_em_portugues(scope)}, somados sobre "
            f"os {EXPECTED_PR_MUNICIPALITY_COUNT} municípios do Paraná"
            + (
                "."
                if mw_ok
                else ". Neste filtro a ANEEL não separa potência nem unidades "
                "beneficiadas, então só a contagem de instalações aparece."
            )
        ),
        "filter_note_pt": None
        if mw_ok
        else (projected[0].get("filter_note_pt") if projected else None),
    }


def mmgd_ranked(
    bundle: MmgdPanelBundle,
    *,
    tipo: str | None = None,
    classe: str | None = None,
    porte: str | None = None,
    only_with_plants: bool = True,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = [
        project_mmgd_metrics(r, tipo=tipo, classe=classe, porte=porte)
        for r in mmgd_municipalities_list(bundle)
    ]
    rows = [r for r in rows if r.get("filter_ok") is not False]
    if only_with_plants:
        rows = [r for r in rows if int(r.get("display_n") or 0) > 0]
    if any(r.get("mw_available_in_scope") for r in rows):
        rows.sort(
            key=lambda r: float(r.get("display_mw") or 0.0),
            reverse=True,
        )
    else:
        rows.sort(key=lambda r: int(r.get("display_n") or 0), reverse=True)
    return rows[: max(0, limit)]


def compare_municipal_mmgd(
    bundle: MmgdPanelBundle,
    code_a: str,
    code_b: str,
    *,
    tipo: str | None = None,
    classe: str | None = None,
    porte: str | None = None,
) -> dict[str, Any]:
    by_code = {str(r["CD_MUN"]): r for r in mmgd_municipalities_list(bundle)}
    raw_a = by_code.get(str(code_a).strip())
    raw_b = by_code.get(str(code_b).strip())
    if raw_a is None or raw_b is None:
        return {
            "ok": False,
            "message": "Código municipal ausente no painel MMGD.",
        }
    a = project_mmgd_metrics(raw_a, tipo=tipo, classe=classe, porte=porte)
    b = project_mmgd_metrics(raw_b, tipo=tipo, classe=classe, porte=porte)
    if not a.get("filter_ok") or not b.get("filter_ok"):
        return {
            "ok": False,
            "message": a.get("filter_note_pt")
            or "Filtros incompatíveis para comparação.",
        }
    scope = a.get("metric_scope") or "todas"
    na = int(a.get("display_n") or 0)
    nb = int(b.get("display_n") or 0)
    out: dict[str, Any] = {
        "ok": True,
        "a": a,
        "b": b,
        "metric_scope": scope,
        "delta_n_a_minus_b": na - nb,
        "disclaimer_pt": (
            "A comparação usa a contagem de instalações de geração "
            "distribuída. Não inclui as usinas de grande porte, não é energia "
            "gerada e não indica aptidão solar. As unidades que recebem "
            "crédito são número secundário e só aparecem no total."
        ),
    }
    if a.get("mw_available_in_scope") and b.get("mw_available_in_scope"):
        mwa = float(a.get("display_mw") or 0.0)
        mwb = float(b.get("display_mw") or 0.0)
        out["delta_mw_a_minus_b"] = round(mwa - mwb, 6)
    else:
        out["delta_mw_a_minus_b"] = None
        out["disclaimer_pt"] += (
            " No filtro categórico, MW não está disponível no artefato."
        )
    return out


def mmgd_attribution_lines(bundle: MmgdPanelBundle) -> tuple[str, ...]:
    prov = bundle.provenance
    qual = bundle.quality
    panel = bundle.panel
    lines = [
        "Fonte: ANEEL — MMGD (Mini e Microgeração Distribuída)",
        f"Licença: {prov.get('license_note') or 'ODbL (Dados Abertos ANEEL)'}",
        f"URL do recurso: {prov.get('url') or 'n/d'}",
        f"Arquivo baixado em {data_br(prov.get('retrieved_at'))}",
        "Preparação do painel: "
        f"{data_br(prov.get('prepared_at') or qual.get('prepared_at'))}",
        "Conjunto de dados gerado pela ANEEL em "
        f"{data_br(panel.get('dat_conjunto') or prov.get('dat_conjunto'))}",
        "Período de referência do retrato: "
        + str(
            panel.get("periodo_referencia")
            or prov.get("periodo_referencia")
            or "não registrado"
        ),
        f"Impressão digital do arquivo: {prov.get('content_sha256') or 'n/d'}",
        "A contagem principal é de instalações. As unidades que recebem "
        "crédito são consumidores beneficiados e aparecem como número "
        "secundário.",
        "A potência vem em quilowatts no cadastro e é somada em megawatts "
        "nesta página. Potência não é energia gerada em MWh.",
        "Geração distribuída e usinas de grande porte são cadastros diferentes "
        "da ANEEL e não se somam.",
        str(
            atualizar(panel.get("temporal_note_pt") or qual.get("temporal_note_pt"))
            or ""
        ),
        f"Registros do Paraná descartados na checagem: {qual.get('n_rejected')}",
        f"Municípios no painel: {panel.get('municipality_count')} de "
        f"{EXPECTED_PR_MUNICIPALITY_COUNT}"
        + (
            ", conferidos contra a malha oficial."
            if qual.get("reconcile_ok")
            else ", com divergência na conferência contra a malha oficial."
        ),
    ]
    excluded = qual.get("personal_fields_excluded") or []
    if excluded:
        lines.append(
            "Campos pessoais excluídos dos artefatos públicos: "
            + ", ".join(str(x) for x in excluded)
        )
    return tuple(line for line in lines if line)


def mmgd_public_notice(bundle: MmgdPanelBundle) -> dict[str, Any]:
    qual = bundle.quality
    prov = bundle.provenance
    panel = bundle.panel
    n_rej = int(qual.get("n_rejected") or 0)
    reasons = qual.get("reject_reasons") or {}
    return {
        "periodo_referencia": panel.get("periodo_referencia")
        or prov.get("periodo_referencia"),
        "dat_conjunto": panel.get("dat_conjunto") or prov.get("dat_conjunto"),
        "retrieved_at": str(prov.get("retrieved_at") or "")[:10] or "n/d",
        "prepared_at": str(prov.get("prepared_at") or qual.get("prepared_at") or "")[
            :10
        ]
        or "n/d",
        "n_rejected": n_rej,
        "reject_reasons": reasons,
        "temporal_note_pt": panel.get("temporal_note_pt")
        or qual.get("temporal_note_pt"),
        "notice_pt": (
            f"{numero_br(n_rej)} registros do Paraná foram recusados na "
            f"preparação do arquivo: {motivos_de_recusa_pt(reasons)}. A "
            "contagem principal considera apenas os registros válidos. "
            "Potência instalada, medida em MW, não é energia gerada, que se "
            "mede em MWh. Este cadastro de geração distribuída não se soma ao "
            "cadastro de usinas."
        ),
    }


def mmgd_choropleth_geojson(
    mun_bundle: MunicipalityLayerBundle,
    mmgd: MmgdPanelBundle,
    *,
    tipo: str | None = None,
    classe: str | None = None,
    porte: str | None = None,
) -> dict[str, Any]:
    if not mun_bundle.available or not mmgd.available:
        raise FileNotFoundError("malha ou painel MMGD indisponível")
    by_code = {
        str(r["CD_MUN"]): project_mmgd_metrics(r, tipo=tipo, classe=classe, porte=porte)
        for r in mmgd_municipalities_list(mmgd)
    }
    gdf = mun_bundle.gdf.copy()
    status: list[str] = []
    n_vals: list[int] = []
    mw_vals: list[float | None] = []
    scopes: list[str] = []
    map_metric = "potencia_instalada_mw_conhecida"
    for _, row in gdf.iterrows():
        code = str(row["CD_MUN"])
        hit = by_code.get(code) or {}
        status.append(str(hit.get("status_dados") or "zero_no_cadastro_pr"))
        n_vals.append(int(hit.get("display_n") or 0))
        mw_vals.append(
            float(hit["display_mw"]) if hit.get("display_mw") is not None else None
        )
        scopes.append(str(hit.get("metric_scope") or "todas"))
        map_metric = str(hit.get("map_metric") or map_metric)
    gdf["status_dados"] = status
    gdf["n_empreendimentos"] = n_vals
    gdf["potencia_instalada_mw_conhecida"] = [
        v if v is not None else 0.0 for v in mw_vals
    ]
    gdf["metric_scope"] = scopes
    gdf["map_metric"] = map_metric
    # valor usado na cor
    if map_metric == "n_empreendimentos":
        gdf["choropleth_value"] = n_vals
    else:
        gdf["choropleth_value"] = [float(v) if v is not None else 0.0 for v in mw_vals]
    return json.loads(gdf.to_crs(epsg=4326).to_json())


def mmgd_map_html(
    mun_bundle: MunicipalityLayerBundle,
    mmgd: MmgdPanelBundle,
    *,
    selected_code: str | None = None,
    fill_opacity: float = 0.55,
    tipo: str | None = None,
    classe: str | None = None,
    porte: str | None = None,
) -> str:
    try:
        import folium
        from branca.colormap import LinearColormap
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("folium necessário: pip install 'napi-geoai[ui]'") from exc

    data = mmgd_choropleth_geojson(
        mun_bundle, mmgd, tipo=tipo, classe=classe, porte=porte
    )
    features = data.get("features") or []
    if features:
        map_metric = str(
            (features[0].get("properties") or {}).get("map_metric")
            or "potencia_instalada_mw_conhecida"
        )
    else:
        map_metric = "potencia_instalada_mw_conhecida"
    values = [
        float((f.get("properties") or {}).get("choropleth_value") or 0)
        for f in features
        if (f.get("properties") or {}).get("status_dados") == "com_registros"
    ]
    vmax = max(values) if values else 1.0
    caption = (
        "Empreendimentos MMGD (contagem no escopo)"
        if map_metric == "n_empreendimentos"
        else "Potência instalada conhecida MMGD (MW)"
    )
    cmap = LinearColormap(
        colors=["#fff7ec", "#fd8d3c", "#7f2704"],
        vmin=0.0,
        vmax=vmax if vmax > 0 else 1.0,
        caption=caption,
    )

    import geopandas as gpd

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    minx, miny, maxx, maxy = gdf.total_bounds
    fmap = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    def style_fn(feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        code = str(props.get("CD_MUN") or "")
        status = props.get("status_dados")
        selected = selected_code and code == str(selected_code)
        if status != "com_registros":
            base = {
                "fillColor": "#e2e8f0",
                "color": "#94a3b8",
                "weight": 0.6,
                "fillOpacity": 0.25,
            }
        else:
            val = float(props.get("choropleth_value") or 0.0)
            base = {
                "fillColor": cmap(val),
                "color": "#7c2d12",
                "weight": 0.7,
                "fillOpacity": fill_opacity,
            }
        if selected:
            base["color"] = "#0ea5e9"
            base["weight"] = 2.5
            base["fillOpacity"] = min(fill_opacity + 0.2, 0.9)
        return base

    folium.GeoJson(
        data=data,
        name="MMGD Paraná",
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "NM_MUN",
                "CD_MUN",
                "n_empreendimentos",
                "potencia_instalada_mw_conhecida",
                "status_dados",
                "metric_scope",
            ],
            aliases=[
                "Município",
                "Código",
                "Nº empreendimentos (escopo)",
                "MW instalada conhecida (total mun.)",
                "Status",
                "Escopo",
            ],
        ),
    ).add_to(fmap)
    cmap.add_to(fmap)
    if selected_code:
        hit = gdf[gdf["CD_MUN"].astype(str) == str(selected_code)]
        if not hit.empty:
            b = hit.total_bounds
            fmap.fit_bounds([[b[1], b[0]], [b[3], b[2]]], padding=(28, 28))
        else:
            fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
    else:
        fmap.fit_bounds([[miny, minx], [maxy, maxx]], padding=(12, 12))
    try:
        from branca.element import Element

        fmap.get_root().html.add_child(
            Element(
                "<style>html,body{margin:0;background:#e8eef5;}"
                ".leaflet-container{background:#e8eef5!important;}</style>"
            )
        )
    except Exception:  # pragma: no cover
        pass
    return fmap.get_root().render()
