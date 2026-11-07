# MVP 03 — Resultados (Issue #3)

## Entregas

- Catálogo auditável: [FONTES_OFICIAIS.md](FONTES_OFICIAIS.md) + `SOURCE_CATALOG`
- Contratos: [CONTRATOS_INGESTAO.md](CONTRATOS_INGESTAO.md)
- Conectores prototype: IBGE (reuso) e ANEEL SIGA
- Testes offline com fixtures/mocks; sem rasters/credenciais no Git

## Verificação de acesso (2026-11-07)

| Endpoint | Resultado |
|---|---|
| IBGE `PR_UF_2025.zip` | HTTP 200 |
| ANEEL SIGA CSV | HTTP 200 (~7,5 MiB) |
| ANEEL CKAN `package_show` | `success: true`, license ODbL |

## Testes locais

```powershell
.\.venv\Scripts\ruff.exe check geoai tests scripts
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado local (2026-11-07): **Ruff limpo**; **pytest 22 passed, 2 skipped** (integração IBGE ZIP ausente no clone fresco).

## Fora de escopo (confirmado)

Aptidão solar, Sentinel, Airflow, Kafka, FastAPI/Streamlit.
