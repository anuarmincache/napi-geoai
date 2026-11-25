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
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.connectors.catalog import list_sources  # noqa: E402
from geoai.portal import (  # noqa: E402
    load_energy_panel_bundle,
    load_mmgd_panel_bundle,
    load_population_panel_bundle,
)
from geoai.portal.agro_panel import (  # noqa: E402
    PPM_LABELS_PT,
    agro_attribution_lines,
    agro_cell,
    agro_indicator,
    agro_notices_pt,
    agro_state_summary,
    list_agro_crops,
    load_agro_panel_bundle,
)
from geoai.portal.landcover_panel import (  # noqa: E402
    landcover_attribution_lines,
    landcover_change,
    landcover_composition,
    landcover_share,
    load_landcover_bundle,
)
from geoai.portal.paths import municipalities_geojson_path  # noqa: E402
from geoai.portal.similaridade import (  # noqa: E402
    FORMULA_PT,
    VARIAVEIS,
    construir_indice,
    linhas_dos_paineis,
    municipios_parecidos,
    nota_isolamento_pt,
)
from geoai.portal.textos_legados import atualizar, atualizar_lista  # noqa: E402

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
            "descricao": (
                "Potência instalada de geração distribuída por município."
            ),
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
            "descricao": (
                "Potência fiscalizada das usinas associadas ao município."
            ),
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
            "rotulo": "Geração distribuída por habitante",
            "unidade": "kW/hab",
            "descricao": (
                "Potência instalada de geração distribuída dividida pela "
                "população estimada."
            ),
            "cor": "#a8cf5f",
            "disponivel": mmgd.available,
            "classe": "B",
            "fonte": "ANEEL MMGD ÷ IBGE",
            "escala": "faixa",
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
    # Municípios parecidos: vizinho mais próximo em um espaço declarado.
    # Município sem alguma variável fica fora do índice, não entra com zero.
    indice_parecidos = None
    if lc.available and mmgd.available:
        indice_parecidos = construir_indice(
            linhas_dos_paineis(populacao=pop, cobertura=lc, mmgd=mmgd)
        )

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
        if indice_parecidos is not None:
            vizinhos = municipios_parecidos(indice_parecidos, code, quantidade=5)
            if vizinhos:
                ficha["parecidos"] = {
                    "metodo": FORMULA_PT,
                    "variaveis": [v.rotulo_pt for v in VARIAVEIS],
                    "aviso": nota_isolamento_pt(vizinhos),
                    "lista": [
                        {
                            "cd": v.cd_mun,
                            "nome": v.nome,
                            "distancia": v.distancia,
                            "parecido_em": list(v.parecido_em),
                            "diferente_em": list(v.diferente_em),
                        }
                        for v in vizinhos
                    ],
                }
        if agro.available:
            ficha["pecuaria"] = [
                {
                    "nome": PPM_LABELS_PT[key],
                    "valor": agro_cell(agro, code, agro_indicator(agro, "ppm", key))[0],
                    "unidade": agro_indicator(agro, "ppm", key).unit,
                }
                for key in PPM_LABELS_PT
            ]
        fichas[code] = ficha
    write("fichas.json", fichas)

    # --------------------------------------------------------- energia
    siga_tipos: dict[str, float] = {}
    siga_tipos_n: dict[str, int] = {}
    energia: dict[str, Any] = {
        "mmgd": None,
        "siga": None,
    }
    if mmgd.available:
        energia["mmgd"] = {
            "periodo": mmgd.panel["periodo_referencia"],
            "unidade": "MW",
            "totais": {
                "instalacoes": mmgd.panel["totals"]["n_empreendimentos"],
                "mw": round(
                    float(mmgd.panel["totals"]["potencia_instalada_mw_conhecida"]), 1
                ),
                "uc_credito": mmgd.panel["totals"]["qtd_uc_recebe_credito_total"],
                "sem_potencia": sum(
                    int(r.get("n_potencia_ausente") or 0)
                    for r in mmgd.panel["municipalities"]
                ),
                "por_tipo": mmgd.panel["totals"].get("by_tipo") or {},
                "por_classe": mmgd.panel["totals"].get("by_classe") or {},
            },
            "municipios": [
                {
                    "cd": str(r["cd_mun"]),
                    "nome": r["nome_fonte"],
                    "n": r["n_empreendimentos"],
                    "mw": round(float(r["potencia_instalada_mw_conhecida"] or 0), 3),
                    "uc_credito": r.get("qtd_uc_recebe_credito"),
                    "por_tipo": r.get("by_tipo") or {},
                    "por_classe": r.get("by_classe") or {},
                    "por_porte": r.get("by_porte") or {},
                }
                for r in mmgd.panel["municipalities"]
            ],
            "avisos": atualizar_lista(mmgd.panel.get("notices_pt")),
            "nota_temporal": atualizar(mmgd.panel.get("temporal_note_pt")),
        }
    if siga.available:
        municipios_siga = []
        for r in siga.panel["municipalities"]:
            por_tipo = {
                tipo: round(float(m.get("potencia_fiscalizada_mw") or 0), 3)
                for tipo, m in (r.get("por_tipo") or {}).items()
            }
            for tipo, valor in por_tipo.items():
                siga_tipos[tipo] = siga_tipos.get(tipo, 0.0) + valor
            for tipo, m in (r.get("por_tipo") or {}).items():
                siga_tipos_n[tipo] = siga_tipos_n.get(tipo, 0) + int(m.get("n") or 0)
            municipios_siga.append(
                {
                    "cd": str(r["CD_MUN"]),
                    "nome": r["NM_MUN"],
                    "status": r.get("status_dados"),
                    "n": r["n_empreendimentos"],
                    "mw_fiscalizada": round(
                        float(r["potencia_fiscalizada_mw"] or 0), 3
                    ),
                    "mw_outorgada": round(float(r["potencia_outorgada_mw"] or 0), 3),
                    "por_tipo": por_tipo,
                }
            )
        energia["siga"] = {
            "fase": siga.panel.get("phase_filter"),
            "coleta": "11/11/2026",
            "unidade": "MW",
            "totais": {
                "usinas": siga.panel["totals"]["n_empreendimentos_fase"],
                "mw": round(
                    float(
                        siga.panel["totals"]["potencia_fiscalizada_mw_conhecida_fase"]
                    ),
                    1,
                ),
                "nao_associados": siga.panel["totals"][
                    "n_empreendimentos_nao_associados"
                ],
                "mw_nao_associados": round(
                    float(siga.panel["totals"]["potencia_fiscalizada_mw_nao_associados"]),
                    3,
                ),
                "sem_potencia": int(
                    siga.panel["totals"]["n_potencia_fiscalizada_ausente_fase"]
                ),
                "por_tipo": {k: round(v, 1) for k, v in siga_tipos.items()},
                "usinas_por_tipo": dict(siga_tipos_n),
            },
            "municipios": municipios_siga,
            "limitacao": atualizar(siga.panel.get("nao_associados_limitation_pt")),
            "nota_metrica": siga.panel.get("metric_note"),
        }
    write("energia.json", energia)

    # ----------------------------------------------------- agricultura
    if agro.available:
        culturas = []
        for crop in list_agro_crops(agro):
            ind_area = agro_indicator(agro, "pam", "area_plantada", str(crop["id"]))
            ind_colhida = agro_indicator(agro, "pam", "area_colhida", str(crop["id"]))
            ind_prod = agro_indicator(agro, "pam", "producao", str(crop["id"]))
            ind_rend = agro_indicator(agro, "pam", "rendimento", str(crop["id"]))
            valores = {}
            for code in pop_by:
                area, status_area = agro_cell(agro, code, ind_area)
                colhida, _s_colhida = agro_cell(agro, code, ind_colhida)
                prod, _status_prod = agro_cell(agro, code, ind_prod)
                rend, _s_rend = agro_cell(agro, code, ind_rend)
                if area is None and prod is None and rend is None:
                    continue
                valores[code] = {
                    "area": area,
                    "colhida": colhida,
                    "producao": prod,
                    "rendimento": rend,
                    "status": status_area,
                }
            culturas.append(
                {
                    "id": str(crop["id"]),
                    "nome": str(crop["name"]),
                    "unidade_area": ind_area.unit,
                    "unidade_producao": ind_prod.unit,
                    "unidade_rendimento": ind_rend.unit,
                    "estado_area": agro_state_summary(agro, ind_area),
                    "estado_colhida": agro_state_summary(agro, ind_colhida),
                    "estado_producao": agro_state_summary(agro, ind_prod),
                    "municipios": valores,
                }
            )
        rebanhos = []
        for key, rotulo in PPM_LABELS_PT.items():
            ind = agro_indicator(agro, "ppm", key)
            valores = {}
            for code in pop_by:
                valor, status_cell = agro_cell(agro, code, ind)
                valores[code] = {"v": valor, "s": status_cell}
            rebanhos.append(
                {
                    "chave": key,
                    "nome": rotulo,
                    "unidade": ind.unit,
                    "fonte": ind.source_pt,
                    "estado": agro_state_summary(agro, ind),
                    "municipios": valores,
                }
            )
        write(
            "agricultura.json",
            {
                "ano_pam": agro.panel["pam"]["year"],
                "ano_ppm": agro.panel["ppm"]["year_rebanho"],
                "culturas": culturas,
                "rebanhos": rebanhos,
                "avisos": list(agro_notices_pt(agro)),
                "fontes": list(agro_attribution_lines(agro)),
            },
        )

    # ------------------------------------------------------- cobertura
    if lc.available:
        anos = lc.panel["years"]
        grupos = [
            {"chave": g["key"], "nome": g["label_pt"], "cor": g["color"]}
            for g in lc.panel["groups"]
        ]
        municipios_lc = {}
        for code in pop_by:
            linha = lc.panel["municipalities"][code]
            por_ano = {}
            for ano in anos:
                por_ano[str(ano)] = {
                    g["chave"]: round(
                        landcover_share(lc, code, g["chave"], ano) or 0.0, 2
                    )
                    for g in grupos
                }
            municipios_lc[code] = {
                "pct": por_ano,
                "ha_mapeada": linha["mapped_ha_last"],
                "area_ibge_km2": linha["ibge_area_km2"],
                "delta_ibge": linha["relative_delta_vs_ibge"],
            }
        write(
            "cobertura.json",
            {
                "colecao": lc.panel["collection"],
                "anos": anos,
                "ultimo_ano": lc.panel["last_year"],
                "grupos": grupos,
                "regra_anos": lc.panel["year_rule_pt"],
                "estado": {
                    str(ano): {
                        g["chave"]: round(
                            float(
                                (lc.panel["totals_ha"].get(str(ano)) or {}).get(
                                    g["chave"], 0
                                )
                            )
                        )
                        for g in grupos
                    }
                    for ano in anos
                },
                "mudanca_estado": [
                    {
                        "nome": r["label_pt"],
                        "ha_inicio": round(r["hectares_a"]),
                        "ha_fim": round(r["hectares_b"]),
                        "delta_ha": round(r["delta_ha"]),
                        "delta_pp": round(r["delta_pp"], 2)
                        if r["delta_pp"] is not None
                        else None,
                    }
                    for r in landcover_change(
                        lc, None, anos[0], lc.panel["last_year"]
                    )
                ],
                "municipios": municipios_lc,
                "avisos": lc.panel.get("notices_pt") or [],
                "fontes": list(landcover_attribution_lines(lc)),
                "qualidade": lc.quality.get("area_delta_vs_ibge"),
            },
        )

    # ---------------------------------------------------------- fontes
    catalogo = []
    for fonte in list_sources():
        item = asdict(fonte)
        catalogo.append(
            {
                "id": item["source_id"],
                "organizacao": item["organization"],
                "produto": item["product"],
                "url": item["entry_url"],
                "formatos": list(item["formats"]),
                "licenca": item["license_note"],
                "cadencia": item["official_update_cadence"],
                "cobertura": item["spatial_coverage"],
                "granularidade": item["granularity"],
                "crs": item["crs_or_coords"],
                "catalogado_em": item["catalogued_at"],
                "status": str(getattr(item["status"], "value", item["status"])),
                "autenticacao": bool(item["auth_required"]),
                "notas": item["notes"],
            }
        )
    artefatos = []
    for rotulo, caminho in (
        ("População IBGE 2026", "ibge_pr_population_2026"),
        ("Usinas ANEEL SIGA", "siga_pr_energy"),
        ("Geração distribuída ANEEL MMGD", "mmgd_pr"),
        ("Lavouras e pecuária IBGE", "agro_pr"),
        ("Cobertura da terra MapBiomas", "mapbiomas_pr_landcover"),
    ):
        proveniencia = REPO / "data" / "derived" / f"{caminho}.provenance.json"
        if not proveniencia.is_file():
            continue
        dados_prov = json.loads(proveniencia.read_text(encoding="utf-8"))
        artefatos.append(
            {
                "rotulo": rotulo,
                "arquivo": f"{caminho}_panel.json",
                "preparado_em": dados_prov.get("prepared_at", "")[:10],
                "organizacao": dados_prov.get("organization"),
                "produto": dados_prov.get("product"),
                "sha256": dados_prov.get("content_sha256"),
                "licenca": dados_prov.get("license_note"),
            }
        )
    write(
        "fontes.json",
        {
            "catalogo": catalogo,
            "artefatos": artefatos,
            "regras": [
                "Dado oficial (classe A): registrado diretamente na fonte.",
                "Indicador calculado (classe B): conta determinística sobre "
                "dados oficiais, com fórmula e unidade declaradas.",
                "Simulação (classe C): estimativa com hipóteses declaradas.",
                "Zero verdadeiro, dado indisponível, sigilo estatístico e "
                "município sem registro aparecem de forma diferente.",
                "Falta de dado é mostrada como falta de dado.",
            ],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
