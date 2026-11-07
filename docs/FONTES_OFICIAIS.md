# Catálogo de fontes oficiais — MVP 03

Tabela auditável das fontes candidatas. **Mecanismos reais de acesso** (não se
assume API REST para todas). `catalogued_at`: **2026-11-07**.

Distinguir: **periodicidade oficial** (portal) ≠ **política de verificação** local
(TTL/ETag no conector). Integridade de cache ≠ dado atualizado na origem.

Nenhum cálculo de aptidão solar é derivado aqui.

## Resumo

| source_id | Órgão | Formatos | Acesso real | Auth | Status no repo |
|---|---|---|---|---|---|
| `ibge.malhas_municipais.pr_uf_2025` | IBGE | ZIP/SHP | HTTP file (geoftp) | não | prototype |
| `aneel.siga.empreendimentos_geracao` | ANEEL | CSV/XML | CKAN + HTTP download | não | prototype |
| `aneel.mmgd.empreendimentos` | ANEEL | ZIP/CSV/Parquet | CKAN + HTTP download | não | catalogued |
| `inpe.labren.atlas_solar_2017` | INPE/LABREN | CSV/SHP/QGS | índice web / data.inpe.br | não* | catalogued |
| `mapbiomas.brazil.lulc` | MapBiomas | GeoTIFF / GEE | plataforma web, GEE, GCS | GEE opcional | catalogued |
| `ons.dados_abertos.capacidade_geracao` | ONS | CSV/XLSX/Parquet | portal dados.ons.org.br | não** | catalogued |
| `ons.dados_abertos.linha_transmissao` | ONS | CSV/XLSX/Parquet | portal dados.ons.org.br | não** | catalogued |

\* Uso comercial do Atlas Solar exige autorização INPE; citação obrigatória.  
\*\* Portal API SINtegre do ONS exige login de agente — fora do MVP.

Catálogo machine-readable: `geoai.connectors.catalog.SOURCE_CATALOG`.

## IBGE — Malhas Municipais (UF)

| Campo | Valor |
|---|---|
| Entrada | https://geoftp.ibge.gov.br/.../malhas_municipais/ |
| Download verificado | `PR_UF_2025.zip` (HTTP 200, ~347 KiB) |
| Licença / uso | arquivos públicos; citar IBGE + edição |
| CRS | EPSG:4674 |
| Conector | `geoai.connectors.ibge` |

Detalhes do recorte Paraná: [FONTES_LIMITES_PARANA.md](FONTES_LIMITES_PARANA.md).

## ANEEL — SIGA e MMGD

| Campo | SIGA | MMGD |
|---|---|---|
| Portal | dadosabertos.aneel.gov.br (CKAN) | idem |
| Download verificado | `siga-empreendimentos-geracao.csv` (HTTP 200, ~7,5 MiB) | ZIP ~100+ MiB |
| Licença | ODbL | ODbL |
| API auxiliar | ` /api/3/action/package_show` | idem |
| Conector | `geoai.connectors.aneel` (CSV SIGA) | apenas catalogado |
| Observação | coords com vírgula decimal; delimiter `;` | migração SISGD→MMGD em 2025 |

SIGEL/ArcGIS (`sigel.aneel.gov.br`) existe como camada geoespacial complementar; não é o conector deste MVP.

## INPE/LABREN — Atlas Solar 2017

| Campo | Valor |
|---|---|
| Entrada | https://labren.ccst.inpe.br/atlas_2017.html |
| Metadados | data.inpe.br / GeoNetwork |
| Formatos | CSV (`;`, UTF-8), SHP, QGS |
| Resolução | 0,1° ≈ 10 km; Wh/m².dia |
| API REST única? | **não** — download por índice/estado |
| Conector | não implementado (catalogado) |

## MapBiomas

| Campo | Valor |
|---|---|
| Plataforma | https://plataforma.brasil.mapbiomas.org/ → GeoTIFF |
| Programático | Google Earth Engine ImageCollection; GCS `mapbiomas-public` |
| API REST genérica? | **não** |
| Conector | não implementado; rasters pesados fora do Git |

## ONS

| Campo | Valor |
|---|---|
| Dados abertos | https://dados.ons.org.br (CSV/Parquet/XLSX, CC-BY) |
| API agentes | https://portal-integra.ons.org.br/api-docs (login SINtegre) |
| Conector | não implementado; preferir dados abertos no MVP |

## O que não entra neste MVP

- Cálculos de aptidão solar / pesos / máscaras
- Sentinel / GEE operacional no CI
- Airflow, Kafka, FastAPI, Streamlit
- Credenciais ou rasters grandes no Git
