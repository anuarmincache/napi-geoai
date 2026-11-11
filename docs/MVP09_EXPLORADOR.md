# MVP 09 — Explorador territorial (399 municípios)

## Objetivo

Explorar, localizar e comparar os **399 municípios do Paraná** com geometria
oficial IBGE, sem inventar indicadores socioeconômicos ou energéticos.

## Fonte e proveniência

| Campo | Valor |
|---|---|
| Órgão | IBGE |
| Produto | Malhas Municipais / Malha Municipal Digital |
| Edição | `municipio_2025` |
| Arquivo bruto | `PR_Municipios_2025.zip` (geoftp; ~11 MB) |
| URL | https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/PR_Municipios_2025.zip |
| CRS | EPSG:4674 (SIRGAS 2000) |
| Contagem | **399** códigos `CD_MUN` distintos |
| Área | atributo oficial `AREA_KM2` (não calculado em graus) |

## Artefatos versionados

| Arquivo | Papel |
|---|---|
| `data/derived/parana_municipios_2025_presentation.geojson` | UI/Cloud (simplificado) |
| `data/derived/parana_municipios_2025.provenance.json` | URL, SHA ZIP, SHA derivado, edição |
| `data/derived/parana_municipios_2025.validation.json` | Contagem, CRS, validação |
| `data/derived/parana_municipios_2025_qgis_report.json` | Evidência QGIS (versões, validade, área elipsoidal, SHA) |

Alta fidelidade: ZIP em `data/raw/ibge/` (**não** versionado). Regenerar:

```powershell
py -3 scripts/prepare_parana_municipalities.py
```

Simplificação de apresentação: `simplify(0.002°, preserve_topology=True)` —
documentada na proveniência. Não usar geometria simplificada para análises
métricas finas.

## Serviços portáveis (`geoai.portal`)

- `load_municipality_layer` — fail-closed (SHA/CRS declarado×efetivo/códigos PR/AREA_KM2 via math.isfinite/geometria + cruzamento QGIS↔proveniência)
- `geoai.qgis` — contrato do relatório QGIS (sem PyQGIS na Cloud)
- `search_municipalities` / `get_municipality` / `list_municipalities`
- `polo_city_records` — 20 atalhos regionais (não ranking)
- `compare_municipalities` — nome, código, `AREA_KM2`
- `municipality_map_html` — Folium com destaque

UI Streamlit: `app/pages/5_Explorador_Territorial.py` (thin).

## Limitações

- Limite administrativo ≠ aptidão solar / viabilidade comercial.
- Sem população, PIB, irradiação ou rankings.
- PostGIS local `:5433` não é alterado; Cloud usa só artefatos versionados.
- Sem publicação Cloud automática e sem Supabase neste MVP.
- QGIS/PyQGIS só no Desktop local (MCP ou `python-qgis-ltr.bat`); Streamlit Cloud não embute QGIS.
- GeoPandas permanece o caminho de preparação/UI; PostGIS continua complementar local.
