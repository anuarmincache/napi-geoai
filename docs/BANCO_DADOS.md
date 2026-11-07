# Banco de dados — fundação PostGIS (MVP 04 / Issue #14)

## Objetivo

Persistência espacial versionada para o NAPI GeoAI: fontes, corridas de ingestão,
artefatos com SHA-256 e unidades territoriais em **EPSG:4674** (SIRGAS 2000).

Este MVP **não** conecta nem altera a conta Supabase remota. O alvo de
desenvolvimento é PostgreSQL + PostGIS **local**; o CI usa o serviço gratuito
`postgis/postgis` no GitHub Actions.

## Decisão de ambiente (máquina Windows / WSL2)

Verificação em 2026-11-07:

| Componente | Status |
|---|---|
| Ubuntu-24.04 | **WSL2** (`VERSION 2`), kernel Microsoft |
| Pacotes `postgresql-16` / `postgresql-16-postgis-3` | **Não instalados** (candidatos no apt) |
| Porta `127.0.0.1:5432` | Fechada até a instalação |
| Docker Desktop (Windows) | Ausente |
| Docker **dentro do WSL** | Presente (outros stacks); **não** usado como caminho preferido deste MVP |
| Conta Supabase remota | **Fora de escopo** |

### Caminho escolhido pelo responsável

**PostgreSQL + PostGIS nativo no Ubuntu WSL2** (não Docker Desktop por ora).

Script: [`scripts/setup_postgis_wsl.sh`](../scripts/setup_postgis_wsl.sh).

```bash
# No terminal Ubuntu (digite a senha sudo pessoalmente; não compartilhe):
cd /mnt/c/Users/Admin/OneDrive/Área\ de\ Trabalho/napi-geoai-mvp04
bash scripts/setup_postgis_wsl.sh
```

Alternativas gratuitas (se necessário depois): Compose deste repo (porta só em
`127.0.0.1`), instalador Windows, ou validação só no CI. **Serviços pagos** e a
conta Supabase existente **não** entram sem nova decisão.

## Stack e layout

```
db/migrations/0001_init_postgis.sql   # DDL portátil (PostGIS em public ou extensions)
docker-compose.yml                    # alternativa; bind 127.0.0.1:5432
.env.example                          # nomes de variáveis (sem segredos reais)
geoai/db/                             # migrate, import, resolve PostGIS schema
scripts/migrate_db.py
scripts/import_parana_boundary_db.py
scripts/setup_postgis_wsl.sh
```

Schemas:

- `extensions` — criado sempre; PostGIS é instalado aí **somente se ainda não existir**.
- Se a imagem já trouxe PostGIS em `public` (CI Docker), a extensão permanece em
  `public` e o DDL resolve o schema via `pg_extension`.
- `geoai` — tabelas de aplicação.

Funções `ST_*` no Python usam `search_path` configurado em runtime
(`geoai.db.postgis.configure_search_path`), sem hardcode `extensions.ST_*`.

## Modelo inicial

| Tabela | Papel |
|---|---|
| `geoai.data_sources` | Catálogo de fontes (`source_id` alinhado ao MVP 03) |
| `geoai.ingestion_runs` | Auditoria de cada corrida de carga |
| `geoai.data_artifacts` | Artefato + SHA-256 + referência de storage |
| `geoai.territorial_units` | Geometria `MultiPolygon,4674` + GiST; unicidade `(ibge_code, mesh_edition)` |
| `geoai.schema_migrations` | Versões SQL aplicadas |

Timestamps: `timestamptz DEFAULT now()` (instante absoluto; exibir em UTC na app).

Não há stand-in espacial em SQLite: testes de banco exigem PostGIS real
(`DATABASE_URL` / marcador `postgis`).

## `DATABASE_URL` e `.env`

```text
postgresql://napi:napi_local_dev_only@127.0.0.1:5432/napi_geoai
```

- WSL2 encaminha `127.0.0.1:5432` do Windows para o Postgres escutando em localhost
  no Ubuntu (quando o serviço está ativo).
- Copiar `.env.example` → `.env` **não** injeta variáveis sozinho. Os scripts
  chamam `load_dotenv_file()`; no PowerShell você também pode exportar:

```powershell
$env:DATABASE_URL="postgresql://napi:napi_local_dev_only@127.0.0.1:5432/napi_geoai"
```

## Como validar (após instalação WSL)

```powershell
$env:DATABASE_URL="postgresql://napi:napi_local_dev_only@127.0.0.1:5432/napi_geoai"
py -3 -m pip install -e ".[dev,db]"
py -3 scripts/migrate_db.py
py -3 scripts/import_parana_boundary_db.py
py -3 -m ruff check .
py -3 -m pytest -q
```

## Importação Paraná (reprodutibilidade)

Entrada (MVP 02):

- `data/derived/parana_uf_2025.geojson`
- `data/derived/parana_uf_2025.provenance.json`
- `data/derived/parana_uf_2025.validation.json`

Checksums:

- `provenance.content_sha256` → **ZIP bruto** IBGE.
- `provenance.derived_geojson_sha256` → **GeoJSON derivado** (obrigatório na importação).

`source_id` no banco: `ibge.malhas_municipais.pr_uf_2025` (mesmo do catálogo MVP 03).

Pré-checagens: CRS `EPSG:4674`, 1 feature, geometria válida, SHA do GeoJSON,
`CD_UF`/`SIGLA_UF`/`NM_UF` presentes (sem defaults silenciosos).

Pós-carga: `ST_IsValid`, `ST_SRID=4674`, `GeometryType=MULTIPOLYGON`,
consulta espacial (ponto em Maringá ∩ PR).

## Compatibilidade futura com Supabase

- Schema `extensions` preparado; extensão criada lá em bancos limpos.
- SQL versionado; sem secrets no Git; sem executar nada na conta existente.

## Segurança local

- Compose (se usado): porta `127.0.0.1:5432:5432` apenas.
- Credenciais do exemplo são só para desenvolvimento local.
- Não expor Postgres à rede; não commit de `.env`.
