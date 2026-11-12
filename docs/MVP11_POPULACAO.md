# MVP 11 — População IBGE 2026 e indicadores municipais

Issue: [#32](https://github.com/anuarmincache/napi-geoai/issues/32)

## Fonte

| Campo | Valor |
|---|---|
| Produto | Estimativas da população residente |
| Referência | **01/07/2026** |
| Edição | `POP2026_20261029.xlsx` (FTP IBGE, 29/10/2026) |
| URL | https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2026/POP2026_20261029.xlsx |
| Entrada | https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html |

Não é Censo Demográfico. Total UF Paraná na planilha: **11 952 456** hab.

## Join

`CD_MUN` = `COD. UF` (2) + `COD. MUNIC` (5). Conjunto deve coincidir com os **399** códigos da malha `municipio_2025`. Fail-closed se faltar/sobrar código ou se a soma municipal ≠ total UF.

## Indicadores

| Indicador | Fórmula / nota |
|---|---|
| `populacao_estimada_2026_hab` | Inteiro ≥ 0 da planilha |
| `densidade_demografica_estimada_2026_hab_km2` | pop ÷ `AREA_KM2` (malha 2025); mistura 2026/2025 |
| `potencia_fiscalizada_conhecida_kw_por_habitante` | MW_conhecida×1000 ÷ pop; n/d se cobertura incompleta |
| `potencia_fiscalizada_conhecida_mw_por_km2` | MW_conhecida ÷ área; não é aptidão |
| `usinas_por_100mil_hab` | n_usinas×100000 ÷ pop |

SIGA: geração **centralizada**, fase Operação; **não** MMGD; **não** MWh.

- Painel SIGA **disponível**: exige 399 CD_MUN iguais à malha (fail-closed); `sem_empreendimento` = **zero vinculado** (não absoluto), com ressalva dos não associados.
- Painel SIGA **indisponível**: população/densidade permanecem; MW/kW/hab/`n` = **n/d** (`energia_indisponivel`) — **não** inventa zero.

## QGIS

Sem geoprocessamento novo neste MVP. A malha 399 permanece validada pelo relatório QGIS do MVP 09; indicadores são tabulares por `CD_MUN`.

## Artefatos

- `data/derived/ibge_pr_population_2026_panel.json`
- `data/derived/ibge_pr_population_2026.provenance.json`
- `data/derived/ibge_pr_population_2026.quality.json`
- UI: `app/pages/7_Ficha_Municipal.py`

## Regenerar

```powershell
py -3 scripts/prepare_population_parana.py
py -3 scripts/capture_population_evidence.py
```
