# MVP 11 — Resultados

| Item | Valor |
|---|---|
| Issue | #32 |
| Branch | `feat/mvp11-population-ibge-2026` |
| Edição IBGE | `POP2026_20261029` |
| Referência | 2026-07-01 |
| SHA XLSX | `6a5b50c76a5747102a6b40c0aa62498baf7ecc1f128e051e1400dfb57b88117a` |
| Municípios PR | **399** (join estrito com malha 2025) |
| Soma populacional | **11 952 456** (= total UF) |
| Evidências | `docs/evidence/mvp11/` |
| Docs | `docs/MVP11_PLAN.md`, `docs/MVP11_POPULACAO.md` |

## Testes

```powershell
py -3 -m ruff check .
py -3 -m pytest -q
```
