# MVP 03 — Resultados (Issue #3 / PR #13)

## Entregas

- Catálogo auditável: [FONTES_OFICIAIS.md](FONTES_OFICIAIS.md) + `SOURCE_CATALOG`
- Contratos: [CONTRATOS_INGESTAO.md](CONTRATOS_INGESTAO.md)
- Conectores prototype: IBGE (API MVP 02) e ANEEL SIGA
- Pós-revisão PR #13: cache com TTL/ETag, download atômico, validação SIGA completa

## Verificação de acesso (catalogued_at: 2026-11-07)

| Endpoint | Resultado |
|---|---|
| IBGE `PR_UF_2025.zip` | HTTP 200 |
| ANEEL SIGA CSV | HTTP 200 (~7,5 MiB; Last-Modified 2026-11-01) |
| ANEEL CKAN `package_show` | `success: true`, license ODbL |

## Política cache (pós-revisão)

- Integridade (SHA-256) ≠ atualidade.
- `retrieved_at` vs `last_checked_at` distintos.
- TTL + conditional GET (304); `force_refresh` disponível.
- Escrita atômica (`.partial` → `os.replace`); destino prévio preservado em falha.

## Limitações

- Periodicidade oficial vem do portal; nossa verificação é TTL/ETag locais.
- INPE/MapBiomas/ONS/MMGD permanecem catalogados (sem download automático).
- Fixture ANEEL é amostra sintética/reduzida para CI — não republica o CSV completo.

## Testes

```powershell
.\.venv\Scripts\ruff.exe check geoai tests scripts
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado local após correções da revisão: Ruff limpo; pytest conforme execução do PR.
