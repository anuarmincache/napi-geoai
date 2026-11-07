# MVP 04 — Resultados (Issue #14 / PR #15)

## Entregáveis

| Item | Caminho |
|---|---|
| Modelo / limitações locais | `docs/BANCO_DADOS.md` |
| Migração inicial (PostGIS portátil) | `db/migrations/0001_init_postgis.sql` |
| Compose (loopback only) | `docker-compose.yml` |
| Setup WSL nativo | `scripts/setup_postgis_wsl.sh` |
| Migrador / importador | `geoai/db/*`, `scripts/*` |
| Testes | `tests/test_db_foundation.py`, `tests/test_db_postgis.py` |
| CI PostGIS | `.github/workflows/ci.yml` |

## Correções pós-revisão ChatGPT (PR #15)

| Problema | Correção |
|---|---|
| CI: `extensions.geometry` inexistente (PostGIS em `public`) | DDL resolve schema via `pg_extension`; import usa `search_path` |
| `SOURCE_ID` BCIM ≠ catálogo MVP 03 | `ibge.malhas_municipais.pr_uf_2025` |
| `timestamptz DEFAULT (now() AT TIME ZONE 'utc')` | `DEFAULT now()` |
| Defaults silenciosos CD_UF/SIGLA_UF | Rejeição se ausentes |
| SHA GeoJSON opcional | `derived_geojson_sha256` obrigatório no provenance |
| Compose `0.0.0.0:5432` | `127.0.0.1:5432:5432` |
| `.env` não carrega sozinho | `load_dotenv_file()` + documentação |
| Rollback em DB compartilhado | fixture `clean_probe` |

## Ambiente

- Ubuntu-24.04 **WSL2** confirmado; pacotes Postgres/PostGIS **a instalar** via script (sudo interativo do usuário).
- Sem Supabase remoto; sem serviços pagos.

### Resultados locais (Postgres nativo WSL)

Instalação apt concluída (`postgresql-16` + `postgresql-16-postgis-3`, PostGIS 3.4).
Cluster `16/main` em **127.0.0.1:5433**.

```text
ruff check .                 → All checks passed
scripts/migrate_db.py        → Aplicada: 0001_init_postgis (nativo)
import Paraná                → succeeded, CD_UF=41, hash canônico LF
pytest -q                    → 45 passed, 2 skipped
```

### CI (GitHub Actions)

Commits `ba5f3b1` / `7c0f909` — após correções de PostGIS portátil + SHA/EOL LF:

- Runs `42404685730` e `42404681174` → **success** (Ruff + pytest com serviço PostGIS).
