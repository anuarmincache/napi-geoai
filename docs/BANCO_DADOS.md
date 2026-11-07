# Banco de dados — fundação PostGIS (MVP 04 / Issue #14)

## Objetivo

Persistência espacial versionada para o NAPI GeoAI: fontes, corridas de ingestão,
artefatos com SHA-256 e unidades territoriais em **EPSG:4674** (SIRGAS 2000).

Este MVP **não** conecta nem altera a conta Supabase remota. O alvo de
desenvolvimento/CI é PostgreSQL + PostGIS local (Docker) ou serviço equivalente
gratuito no GitHub Actions.

## Decisão de ambiente (máquina Windows atual)

Verificação em 2026-11-07 neste workspace de trabalho:

| Componente | Status |
|---|---|
| `docker` / Docker Desktop | **Ausente** |
| `psql` / PostgreSQL em `127.0.0.1:5432` | **Ausente** |
| WSL2 Ubuntu | Presente, mas operações com `sudo` pedem senha interativa |
| Conta Supabase remota | **Fora de escopo** deste PR (não usar) |

### Alternativas gratuitas (escolha do mantenedor)

1. **Recomendada:** instalar [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   (licença gratuita para uso pessoal/pequeno time) e subir o Compose deste repo.
2. **WSL2:** instalar `postgresql` + `postgis` via `apt` no Ubuntu WSL
   (requer senha `sudo` uma vez).
3. **Windows nativo:** instalador PostgreSQL + extensão PostGIS (EDB/OSGeo).
4. **Somente CI:** validar PostGIS no GitHub Actions (já previsto neste MVP);
   desenvolvimento local fica bloqueado até (1)–(3).

**Serviços pagos** (Supabase Pro, RDS, etc.) **não** devem ser usados nesta etapa
sem decisão explícita. Nenhum connection string remoto foi commitado.

## Stack e layout

```
db/migrations/0001_init_postgis.sql   # DDL idempotente
docker-compose.yml                    # postgis/postgis:16-3.4
.env.example                          # DATABASE_URL local
geoai/db/                             # migrate + import Paraná
scripts/migrate_db.py
scripts/import_parana_boundary_db.py
```

Schemas:

- `extensions` — extensão PostGIS (padrão alinhado ao Supabase).
- `geoai` — tabelas de aplicação.

## Modelo inicial

| Tabela | Papel |
|---|---|
| `geoai.data_sources` | Catálogo de fontes (ex.: IBGE malha UF) |
| `geoai.ingestion_runs` | Auditoria de cada corrida de carga |
| `geoai.data_artifacts` | Artefato + SHA-256 + referência de storage |
| `geoai.territorial_units` | Geometria `MultiPolygon,4674` + GiST; unicidade `(ibge_code, mesh_edition)` |
| `geoai.schema_migrations` | Versões SQL aplicadas |

Não há stand-in espacial em SQLite: testes de banco exigem PostGIS real
(`DATABASE_URL` ou marcador `postgis`).

## Como subir (quando Docker estiver disponível)

```powershell
copy .env.example .env
docker compose up -d
py -3 -m pip install -e ".[dev,db]"
py -3 scripts/migrate_db.py
py -3 scripts/import_parana_boundary_db.py
py -3 -m pytest -q
py -3 -m pytest -q -m postgis
```

`DATABASE_URL` de exemplo (Compose):

```text
postgresql://napi:napi_local_dev_only@127.0.0.1:5432/napi_geoai
```

## Importação Paraná (reprodutibilidade)

Entrada (MVP 02, já versionada):

- `data/derived/parana_uf_2025.geojson`
- `data/derived/parana_uf_2025.provenance.json`
- `data/derived/parana_uf_2025.validation.json`

Pré-checagens: CRS `EPSG:4674`, 1 feature, geometria válida, SHA-256 do GeoJSON,
`CD_UF=41`, `SIGLA_UF=PR`.

Pós-carga no PostGIS: `ST_IsValid`, `ST_SRID=4674`, `GeometryType=MULTIPOLYGON`.

Reexecução com o mesmo SHA é **idempotente** (`already_present=true`); não duplica
a unidade territorial.

## Compatibilidade futura com Supabase

- Extensão em schema `extensions`.
- SQL puro versionado (sem dependência de GUI).
- Sem secrets no repositório.

Quando houver decisão de usar um projeto Supabase **novo/dedicado**, basta apontar
`DATABASE_URL` e rodar as mesmas migrações — sem misturar com outros projetos.

## Limitações conhecidas

- Sem Docker/Postgres local nesta máquina, os testes marcados `postgis` são
  **skipped** no desktop e executados no CI.
- A senha do Compose é apenas para desenvolvimento local; troque antes de qualquer
  exposição de rede.
