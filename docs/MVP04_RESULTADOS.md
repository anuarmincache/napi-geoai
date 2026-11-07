# MVP 04 — Resultados (Issue #14)

## Entregáveis

| Item | Caminho |
|---|---|
| Modelo / limitações locais | `docs/BANCO_DADOS.md` |
| Migração inicial | `db/migrations/0001_init_postgis.sql` |
| Compose PostGIS gratuito | `docker-compose.yml` |
| Migrador | `geoai/db/migrate.py`, `scripts/migrate_db.py` |
| Importador Paraná | `geoai/db/import_parana.py`, `scripts/import_parana_boundary_db.py` |
| Testes unitários (sem DB) | `tests/test_db_foundation.py` |
| Testes PostGIS | `tests/test_db_postgis.py` (marcador `postgis`) |
| CI com serviço PostGIS | `.github/workflows/ci.yml` |

## Critérios de aceite (Issue #14)

- [x] Esquema inicial versionado (fontes, runs, artefatos, unidades territoriais)
- [x] Geometria em EPSG:4674 com índice GiST
- [x] Importação validada do limite do Paraná a partir dos artefatos MVP 02
- [x] Idempotência / reprodutibilidade coberta por testes
- [x] Sem stand-in SQLite espacial
- [x] Sem uso da conta Supabase remota neste PR
- [x] Alternativas locais documentadas quando Docker/Postgres ausentes

## Ambiente de execução deste PR

Na estação Windows do mantenedor: Docker e PostgreSQL locais **não** estavam
disponíveis; WSL exige `sudo` interativo. Por isso:

1. Código + migrações + testes unitários rodam offline.
2. Testes `postgis` rodam no GitHub Actions (serviço `postgis/postgis:16-3.4`).
3. Decisão pendente do mantenedor para instalar Docker Desktop **ou** Postgres/PostGIS
   via WSL/Windows — ver `docs/BANCO_DADOS.md`. Nenhum serviço pago foi provisionado.

### Resultados locais (2026-11-07)

```text
ruff check .     → All checks passed
pytest -q        → 39 passed, 5 skipped (marcador postgis / DATABASE_URL ausente)
import --dry-run → ibge_code=41, uf_sigla=PR, mesh_edition=municipio_2025
```

Os 5 skips são esperados sem PostGIS local; o workflow CI executa a suíte completa
com `DATABASE_URL` do serviço Compose embutido no Actions.
