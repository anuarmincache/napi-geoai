"""Gera os dados estáticos do protótipo web a partir dos artefatos validados.

Uso (na raiz do repositório):
  python scripts/build_web_data.py

Não baixa nada. Lê só `data/derived/` pelos serviços de `geoai.portal`, que já
aplicam as regras de validação, e grava em `web/public/dados/`. Se um painel
não estiver disponível, o campo correspondente sai como `null` e a interface
mostra a ausência, nunca um número inventado.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.portal import (  # noqa: E402
    load_energy_panel_bundle,
    load_mmgd_panel_bundle,
    load_population_panel_bundle,
)
from geoai.portal.agro_panel import (  # noqa: E402
    PPM_LABELS_PT,
    agro_cell,
    agro_indicator,
    agro_state_summary,
    list_agro_crops,
    load_agro_panel_bundle,
)
from geoai.portal.landcover_panel import (  # noqa: E402
    landcover_composition,
    landcover_share,
    load_landcover_bundle,
)
from geoai.portal.paths import municipalities_geojson_path  # noqa: E402
from geoai.sentinel.targets import load_ndvi_plan, load_ndvi_targets  # noqa: E402

OUT = REPO / "web" / "public" / "dados"
PRECISION = 5  # ~1 m; reduz o GeoJSON sem mudar a leitura do mapa


def round_coords(node: Any) -> Any:
    if isinstance(node, (int, float)):
        return round(float(node), PRECISION)
    if isinstance(node, list):
        return [round_coords(item) for item in node]
    return node


def write(name: str, payload: Any) -> None:
    path = OUT / name
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    print(f"gravado web/public/dados/{name} ({path.stat().st_size / 1024:.0f} KB)")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pop = load_population_panel_bundle(REPO)
    siga = load_energy_panel_bundle(REPO)
    mmgd = load_mmgd_panel_bundle(REPO)
    agro = load_agro_panel_bundle(REPO)
    lc = load_landcover_bundle(REPO)
    if not pop.available:
        raise SystemExit("painel de população indisponível: nada foi gravado")

    pop_by = {str(r["CD_MUN"]): r for r in pop.panel["municipalities"]}
    siga_by = (
        {str(r["CD_MUN"]): r for r in siga.panel["municipalities"]}
        if siga.available
        else {}
    )
    mmgd_by = (
        {str(r["cd_mun"]): r for r in mmgd.panel["municipalities"]}
        if mmgd.available
        else {}
    )

    # ---------------------------------------------------------------- mapa
    mesh = json.loads(
        municipalities_geojson_path(REPO).read_text(encoding="utf-8")
    )
    features = []
    for feature in mesh["features"]:
        code = str(feature["properties"]["CD_MUN"])
        population = pop_by.get(code, {})
        energy = siga_by.get(code, {})
        distributed = mmgd_by.get(code, {})
        habitantes = population.get("populacao_estimada_2026_hab")
        mmgd_mw = distributed.get("potencia_instalada_mw_conhecida")
        props: dict[str, Any] = {
            "cd": code,
            "nome": str(feature["properties"]["NM_MUN"]),
            "area_km2": population.get("area_km2_ibge_2025"),
            "habitantes": habitantes,
            "densidade": population.get(
                "densidade_demografica_estimada_2026_hab_km2"
            ),
            "siga_mw": energy.get("potencia_fiscalizada_mw"),
            "siga_usinas": energy.get("n_empreendimentos"),
            "mmgd_mw": mmgd_mw,
            "mmgd_n": distributed.get("n_empreendimentos"),
            "mmgd_kw_hab": (
                round(float(mmgd_mw) * 1000 / float(habitantes), 3)
                if mmgd_mw is not None and habitantes
                else None
            ),
        }
        if lc.available:
            for key in ("formacao_florestal", "agricultura", "area_urbanizada"):
                share = landcover_share(lc, code, key, lc.panel["last_year"])
                props[f"lc_{key}"] = round(share, 2) if share is not None else None
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": round_coords(feature["geometry"]),
            }
        )
    write("municipios.geojson", {"type": "FeatureCollection", "features": features})

    # ------------------------------------------------------------- resumo
    def fonte(label: str, data: str) -> dict[str, str]:
        return {"fonte": label, "data": data}

    kpis = [
        {
            "id": "municipios",
            "rotulo": "Municípios",
            "valor": len(features),
            "unidade": "",
            "detalhe": "malha oficial conferida",
            "classe": "A",
            **fonte("IBGE, Malha Municipal", "2025"),
        },
        {
            "id": "populacao",
            "rotulo": "População estimada",
            "valor": sum(
                int(r["populacao_estimada_2026_hab"])
                for r in pop.panel["municipalities"]
            ),
            "unidade": "hab",
            "detalhe": "estimativa, não é Censo",
            "classe": "A",
            **fonte("IBGE, Estimativas", "01/07/2026"),
        },
    ]
    if mmgd.available:
        kpis.append(
            {
                "id": "mmgd",
                "rotulo": "Geração distribuída",
                "valor": mmgd.panel["totals"]["potencia_instalada_mw_conhecida"],
                "unidade": "MW",
                "detalhe": (
                    f"{mmgd.panel['totals']['n_empreendimentos']:,}".replace(",", ".")
                    + " instalações"
                ),
                "classe": "A",
                **fonte("ANEEL, MMGD", mmgd.panel["periodo_referencia"]),
            }
        )
    if siga.available:
        kpis.append(
            {
                "id": "siga",
                "rotulo": "Geração centralizada",
                "valor": siga.panel["totals"]["potencia_fiscalizada_mw_conhecida_fase"],
                "unidade": "MW",
                "detalhe": (
                    f"{siga.panel['totals']['n_empreendimentos_fase']} usinas"
                    " em operação"
                ),
                "classe": "A",
                **fonte("ANEEL, SIGA", "11/11/2026"),
            }
        )

    camadas = [
        {
            "id": "mmgd_mw",
            "rotulo": "Geração distribuída",
            "unidade": "MW",
            "descricao": "Potência instalada conhecida de MMGD por município.",
            "cor": "#fcc817",
            "disponivel": mmgd.available,
            "classe": "A",
            "fonte": f"ANEEL MMGD, {mmgd.panel['periodo_referencia']}"
            if mmgd.available
            else "indisponível",
        },
        {
            "id": "siga_mw",
            "rotulo": "Usinas em operação",
            "unidade": "MW",
            "descricao": "Potência fiscalizada conhecida das usinas associadas.",
            "cor": "#73a535",
            "disponivel": siga.available,
            "classe": "A",
            "fonte": "ANEEL SIGA, 11/11/2026" if siga.available else "indisponível",
        },
        {
            "id": "habitantes",
            "rotulo": "População",
            "unidade": "hab",
            "descricao": "População estimada pelo IBGE em 01/07/2026.",
            "cor": "#5b8a3a",
            "disponivel": True,
            "classe": "A",
            "fonte": "IBGE, estimativa 01/07/2026",
        },
        {
            "id": "mmgd_kw_hab",
            "rotulo": "MMGD por habitante",
            "unidade": "kW/hab",
            "descricao": "Potência MMGD dividida pela população estimada.",
            "cor": "#a8cf5f",
            "disponivel": mmgd.available,
            "classe": "B",
            "fonte": "ANEEL MMGD ÷ IBGE",
        },
        {
            "id": "lc_formacao_florestal",
            "rotulo": "Floresta",
            "unidade": "% da área mapeada",
            "descricao": "Parcela de floresta na cobertura da terra de 2025.",
            "cor": "#1f8d49",
            "disponivel": lc.available,
            "classe": "B",
            "fonte": "MapBiomas Coleção 11, 2025"
            if lc.available
            else "indisponível",
        },
        {
            "id": "lc_agricultura",
            "rotulo": "Agricultura",
            "unidade": "% da área mapeada",
            "descricao": "Parcela de agricultura na cobertura da terra de 2025.",
            "cor": "#E974ED",
            "disponivel": lc.available,
            "classe": "B",
            "fonte": "MapBiomas Coleção 11, 2025"
            if lc.available
            else "indisponível",
        },
    ]

    ndvi_targets = load_ndvi_targets(REPO)
    ndvi_plan = load_ndvi_plan(REPO)
    write(
        "resumo.json",
        {
            "gerado_em": "2026-11-22",
            "kpis": kpis,
            "camadas": [c for c in camadas if c["disponivel"]],
            "avisos": [
                "Potência instalada (MW) não é energia gerada (MWh).",
                "Geração distribuída (MMGD) e centralizada (SIGA) são cadastros "
                "diferentes e não se somam sem critério.",
                "Os dados são retratos datados, não tempo real.",
                "Os indicadores apoiam a investigação e não substituem estudo "
                "de viabilidade, licenciamento ou parecer técnico.",
            ],
            "ndvi": {
                "municipios": ndvi_targets["count"] if ndvi_targets else None,
                "com_passagem": (ndvi_plan or {}).get("summary", {}).get(
                    "targets_with_pass"
                ),
                "cenas": (ndvi_plan or {}).get("summary", {}).get("distinct_products"),
                "publicados": 0,
                "medidos": 1,
            },
            "fontes": [
                {
                    "nome": "IBGE",
                    "detalhe": "Malha 2025, estimativas 2026, PAM e PPM 2025",
                },
                {
                    "nome": "ANEEL",
                    "detalhe": "SIGA (11/11/2026) e MMGD (11/2026)",
                },
                {
                    "nome": "MapBiomas",
                    "detalhe": "Coleção 11, cobertura da terra 1985 a 2025",
                },
                {"nome": "Copernicus", "detalhe": "Sentinel-2 L2A, catálogo STAC"},
            ],
        },
    )

    # ------------------------------------------------------------- séries
    series: dict[str, Any] = {}
    if mmgd.available:
        classes = sorted(
            (mmgd.panel["totals"].get("by_classe") or {}).items(),
            key=lambda kv: -int(kv[1]),
        )
        series["mmgd_classes"] = [
            {"nome": nome, "valor": int(qtd)} for nome, qtd in classes
        ]
        top = sorted(
            mmgd_by.values(),
            key=lambda r: -float(r.get("potencia_instalada_mw_conhecida") or 0),
        )[:10]
        series["mmgd_top"] = [
            {
                "nome": r["nome_fonte"],
                "mw": round(float(r["potencia_instalada_mw_conhecida"]), 1),
                "n": int(r["n_empreendimentos"]),
            }
            for r in top
        ]
    if siga.available:
        by_tech: dict[str, float] = {}
        for row in siga.panel["municipalities"]:
            for tipo, metrics in (row.get("por_tipo") or {}).items():
                value = metrics.get("potencia_fiscalizada_mw")
                if value is not None:
                    by_tech[tipo] = by_tech.get(tipo, 0.0) + float(value)
        series["siga_tecnologia"] = [
            {"nome": nome, "mw": round(mw, 1)}
            for nome, mw in sorted(by_tech.items(), key=lambda kv: -kv[1])
        ]
    if lc.available:
        years = lc.panel["years"]
        groups = [g["key"] for g in lc.panel["groups"]]
        labels = {g["key"]: g["label_pt"] for g in lc.panel["groups"]}
        colors = {g["key"]: g["color"] for g in lc.panel["groups"]}
        series["cobertura"] = {
            "anos": years,
            "series": [
                {
                    "chave": key,
                    "nome": labels[key],
                    "cor": colors[key],
                    "ha": [
                        round(
                            float(
                                (lc.panel["totals_ha"].get(str(year)) or {}).get(key, 0)
                            )
                        )
                        for year in years
                    ],
                }
                for key in groups
            ],
        }
        series["cobertura_2025"] = [
            {
                "nome": r["label_pt"],
                "cor": r["color"],
                "ha": round(r["hectares"]),
                "pct": round(r["percent"], 1) if r["percent"] is not None else None,
            }
            for r in landcover_composition(lc, None, lc.panel["last_year"])
        ]
    if agro.available:
        crops = []
        for crop in list_agro_crops(agro):
            area = agro_state_summary(
                agro, agro_indicator(agro, "pam", "area_plantada", str(crop["id"]))
            )
            prod = agro_state_summary(
                agro, agro_indicator(agro, "pam", "producao", str(crop["id"]))
            )
            if area.get("soma_publicada"):
                crops.append(
                    {
                        "nome": str(crop["name"]),
                        "area_ha": int(area["soma_publicada"]),
                        "producao_t": int(prod.get("soma_publicada") or 0),
                    }
                )
        crops.sort(key=lambda c: -c["area_ha"])
        series["lavouras"] = crops[:8]
        series["pecuaria"] = [
            {
                "nome": PPM_LABELS_PT[key],
                "valor": int(
                    agro_state_summary(agro, agro_indicator(agro, "ppm", key))[
                        "soma_publicada"
                    ]
                    or 0
                ),
                "unidade": agro_indicator(agro, "ppm", key).unit,
            }
            for key in PPM_LABELS_PT
        ]
    write("series.json", series)

    # ------------------------------------------------------- ficha por município
    fichas = {}
    for code, row in pop_by.items():
        ficha: dict[str, Any] = {
            "cd": code,
            "nome": row["NM_MUN"],
            "habitantes": row["populacao_estimada_2026_hab"],
            "area_km2": row["area_km2_ibge_2025"],
            "densidade": row.get("densidade_demografica_estimada_2026_hab_km2"),
        }
        if code in siga_by:
            ficha["siga"] = {
                "usinas": siga_by[code]["n_empreendimentos"],
                "mw": siga_by[code]["potencia_fiscalizada_mw"],
            }
        if code in mmgd_by:
            ficha["mmgd"] = {
                "n": mmgd_by[code]["n_empreendimentos"],
                "mw": mmgd_by[code]["potencia_instalada_mw_conhecida"],
            }
        if lc.available:
            ficha["cobertura"] = [
                {
                    "nome": r["label_pt"],
                    "cor": r["color"],
                    "pct": round(r["percent"], 1) if r["percent"] is not None else None,
                }
                for r in landcover_composition(lc, code, lc.panel["last_year"])
            ]
        if agro.available:
            ficha["pecuaria"] = [
                {
                    "nome": PPM_LABELS_PT[key],
                    "valor": agro_cell(agro, code, agro_indicator(agro, "ppm", key))[0],
                }
                for key in PPM_LABELS_PT
            ]
        fichas[code] = ficha
    write("fichas.json", fichas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
