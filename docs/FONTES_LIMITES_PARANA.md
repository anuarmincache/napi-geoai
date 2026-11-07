# Fontes — limites territoriais do Paraná

Documento da Issue #2 (MVP 02). Descreve a procedência oficial usada para o
**primeiro recorte territorial técnico**. Não constitui mapa de aptidão solar
nem indicador energético.

## Fonte selecionada

| Campo | Valor |
|---|---|
| Órgão | IBGE — Instituto Brasileiro de Geografia e Estatística |
| Produto | Malhas Territoriais / Malhas Municipais |
| Edição | `municipio_2025` |
| Recorte | Unidade da Federação — Paraná (`PR_UF_2025.zip`) |
| URL | https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/PR_UF_2025.zip |
| Índice | https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/ |
| Disponibilidade | Arquivos públicos no geoftp do IBGE/Geociências |
| Licença / uso | Dados públicos do IBGE; citar órgão, produto e edição. Ver condições institucionais do IBGE. |
| Last-Modified HTTP (observado) | Thu, 26 Feb 2026 20:02:50 GMT |
| CRS de origem esperado | **EPSG:4674** (SIRGAS 2000, geográfico; unidades em graus) |
| CRS recomendado para mapa métrico (visualização) | **EPSG:31982** (SIRGAS 2000 / UTM zone 22S; metros) — maior parte do PR |
| Limitação UTM | A porção **ocidental** do Paraná (~oeste de 54°W) está na zona **UTM 21S (EPSG:31981)**. Área estadual total ou perímetros longos **não** devem usar só UTM 22S; preferir projeção justificada (ex. Albers) ou cálculo por zona. |

## O que este produto é / não é

- **É:** limite oficial da UF Paraná, validado geometricamente, com proveniência e checksum.
- **Não é:** aptidão fotovoltaica, viabilidade, ranking municipal, nem resultado energético.

## Reprodutibilidade

```powershell
uv run python scripts/prepare_parana_boundary.py
```

Artefatos gerados:

- `data/raw/ibge/PR_UF_2025.zip` — bruto (não versionado)
- `data/derived/parana_uf_2025.geojson` — limite derivado
- `data/derived/parana_uf_2025.provenance.json` — URL, ETag, SHA-256, data de obtenção
- `data/derived/parana_uf_2025.validation.json` — relatório de integridade geométrica

## Critérios de validação

1. Download HTTP 200 a partir da URL oficial.
2. SHA-256 do ZIP registrado.
3. Leitura vetorial do ZIP; **CRS ausente gera erro** (sem inferência silenciosa). Só com `assume_crs='EPSG:4674'` explícito.
4. Comparação de CRS via `pyproj.CRS.equals` (não por substring).
5. Geometrias `Polygon`/`MultiPolygon` válidas; `make_valid` pode reparar, mas `GeometryCollection` sem polígono é rejeitada.
6. Exportação **só** se `report.is_exportable` (sem vazios, não polígonos, CRS ok, `all_valid`).
7. Metadados explícitos de que o mapa **não** é aptidão solar.
8. Caminhos em JSON de proveniência/validação são **relativos ao repositório**.

## Limitações

- A malha municipal/UF é um produto cartográfico oficial de referência territorial; generalização e escala devem ser respeitadas em análises posteriores.
- Medidas de área/comprimento devem usar CRS projetado adequado (UTM 22S no Paraná), não graus.
- O conector desta fase cobre apenas o ZIP da UF Paraná; municípios e outras edições virão em issues futuras.
- CI não baixa o ZIP do IBGE por padrão; testes unitários usam fixture sintética e HTTP mock.
