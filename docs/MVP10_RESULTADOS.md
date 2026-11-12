# MVP 10 — Resultados

| Item | Valor |
|---|---|
| Issue | #30 |
| Branch | `feat/mvp10-energy-siga` |
| Fonte | ANEEL SIGA CSV (CKAN), `DatGeracaoConjuntoDados` amostra `2026-11-01` |
| SHA CSV | `9f21aa730a5ccde82b62bad64b40ba1ceb245c84e15f05d12df718ac303e72ef` |
| Linhas PR brutas | 330 |
| Fase Operação | 310 |
| Demais fases | Construção 3; Construção não iniciada 17 |
| Municípios no painel | **399** (123 com usinas; 276 sem empreendimento na fase) |
| MW fiscalizada (Operação) | 17 712,187 (17 640,451 associados + 71,736 não associados) |
| QGIS | 3.44.15 / GDAL 3.13.3 / PROJ 9.8.1 — `native:joinattributesbylocation` within |
| QGIS join (Operação c/ coords) | matched 276; unmatched 4; points 280 |
| MMGD | excluído |
| MWh | não usado |
| Evidências | `docs/evidence/mvp10/` |
| Docs | `docs/MVP10_PLAN.md`, `docs/MVP10_ENERGIA.md` |

## Testes locais

```powershell
py -3 -m ruff check .
py -3 -m pytest -q tests/test_energy_siga.py
py -3 -m pytest -q
```

## Semântica de zero / ausência

Município com `status_dados=sem_empreendimento` significa **nenhuma usina SIGA da fase com ponto válido vinculado ao polígono**, não ausência absoluta de empreendimentos nem falha de ingestão. Com 34 usinas não associadas, a UI destaca essa limitação. Potência fiscalizada desconhecida ≠ 0 MW (`n_potencia_fiscalizada_ausente_*`, `soma_cobertura`).

## Reconciliação espacial (revisão PR #31)

- Assignments QGIS: 310 (276 matched + 34 unmatched)
- Acordo CodCEG→CD_MUN com GeoPandas: 0 divergências; hashes CSV/ZIP OK
- Filtro de tecnologia: MW/contagens/ranking/mapa no escopo do tipo
