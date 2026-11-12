# MVP 10 — Painel energético do Paraná (SIGA/ANEEL)

Issue: [#30](https://github.com/anuarmincache/napi-geoai/issues/30)

## Escopo

Painel municipal de **capacidade fiscalizada (MW)** de geração **centralizada** SIGA/ANEEL no Paraná, associado aos **399 municípios IBGE** via join espacial (QGIS oficial + GeoPandas complementar).

## Fora deste MVP

- MMGD (micro/minigeração distribuída) — apenas catalogado
- Geração efetiva em MWh
- Aptidão solar / pesos
- Cloud, Supabase, serviços pagos

## Fonte e métricas

| Campo | Uso |
|---|---|
| `MdaPotenciaFiscalizadaKw` | Métrica principal → MW |
| `MdaPotenciaOutorgadaKw` | Exibida à parte (não misturar) |
| `DscFaseUsina` | Default UI = `Operação`; demais fases filtráveis |
| `NumCoordN` / `NumCoordE` | lon/lat WGS84 ≈ EPSG:4674 |

Licença dos dados abertos ANEEL: **ODbL**. Proveniência e data do conjunto em `data/derived/siga_pr_energy.provenance.json` e `.quality.json`.

## Associação municipal

1. Pontos SIGA (UF=PR) → CRS alinhado à malha IBGE
2. **QGIS** `native:joinattributesbylocation` (`within`) exporta **assignments CodCEG→CD_MUN** (referência espacial)
3. GeoPandas `sjoin` cruza o mesmo universo; `siga_reconcile` compara mapas e hashes CSV/ZIP
4. Divergência de CD_MUN ou hash não explicada → **fail-closed**
5. Agregação municipal usa CD_MUN do QGIS
6. Plantas sem match → `nao_associados` (não inventam município)
7. `sem_empreendimento` = nenhuma usina georreferenciada/associada — **não** zero absoluto

## Capacidade e filtro

- Potência fiscalizada ausente/inválida/negativa **≠** 0 MW; `n_potencia_fiscalizada_ausente_*` e `soma_cobertura`
- Filtro de tecnologia altera MW, contagens, ranking, comparação e mapa (`metric_scope=tipo:X`)

## Artefatos

| Arquivo | Conteúdo |
|---|---|
| `data/derived/siga_pr_energy_panel.json` | Painel 399 municípios + totais |
| `data/derived/siga_pr_operacao_plants.json` | Detalhe plantas em Operação |
| `data/derived/siga_pr_energy.provenance.json` | SHA, URL, recuperado em |
| `data/derived/siga_pr_energy.quality.json` | Fases, coords, join GeoPandas |
| `data/derived/siga_pr_qgis_join_report.json` | Evidência oficial QGIS |

CSV bruto: `data/raw/aneel/` (gitignored).

## Interface

- Página: `app/pages/6_Energia_SIGA.py`
- Serviços: `geoai/portal/energy_panel.py`
- Mapa coroplético, ranking, comparação A/B, atribuição e download do painel

## Como regenerar

```powershell
# 1) Referência espacial QGIS (obrigatória antes do prepare)
& "C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat" scripts\_qgis_siga_join_worker.py
# 2) Download + reconciliação fail-closed + agregados
py -3 scripts/prepare_siga_parana.py
py -3 scripts/capture_energy_evidence.py
```
