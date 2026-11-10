# Operação do banco PostGIS (MVP 05 / Issue #16)

Procedimentos de **robustez operacional** do NAPI GeoAI. Política: software
gratuito e instalações locais primeiro; **Supabase remoto somente com
autorização explícita** (fora deste MVP).

## Ambiente de referência (WSL2)

| Item | Valor |
|---|---|
| SO | Ubuntu 24.04 em WSL2 |
| PostgreSQL | 16 (`pg_lsclusters`) |
| PostGIS | 3.4 |
| Banco principal | `napi_geoai` (não destruir) |
| Usuário | `napi` |
| Porta | **5433** neste host (não assumir 5432) |
| URL (exemplo) | `postgresql://napi:***@127.0.0.1:5433/napi_geoai` |

A senha de exemplo do MVP04 é ilustrativa — **rotacione** antes de qualquer
exposição. Nunca commitar `.env` nem dumps.

## Ferramentas

```powershell
$env:DATABASE_URL="postgresql://napi:SENHA@127.0.0.1:5433/napi_geoai"
py -3 -m pip install -e ".[dev,db]"
```

Clientes `pg_dump` / `pg_restore` / `psql` no Ubuntu WSL; os scripts detectam
binários no PATH ou via `wsl -d Ubuntu-24.04`.

CLI única:

```text
py -3 scripts/db_ops.py doctor
py -3 scripts/db_ops.py backup --output-dir backups
py -3 scripts/db_ops.py restore-verify --dump backups/<arquivo>.dump
py -3 scripts/db_ops.py security-audit
```

Saídas **não** imprimem senhas (URL redigida).

## 1. Diagnóstico (`doctor`)

Não destrutivo. Verifica versão PG/PostGIS, schema da extensão, migrações,
GiST, SRID 4674, validade geométrica, fontes/artefatos/runs.

Códigos de saída: `0` ok · `1` warn · `2` crítico.

## 2. Backup

```powershell
py -3 scripts/db_ops.py backup --output-dir backups
```

- Formato custom PostgreSQL (`pg_dump -Fc`).
- Arquivos em `backups/` (gitignore; permissões 700/600 quando o SO permitir).
- Retorna `sha256` do dump — guarde fora do Git.

**Nunca** versionar dumps no repositório.

## 3. Restauração verificada (banco temporário)

Pré-requisito local (uma vez): template vazio com PostGIS, porque a role `napi`
não é superuser e não pode `CREATE EXTENSION`:

```bash
# Ubuntu WSL — digite a senha sudo no terminal
# Script IDEMPOTENTE: se o template já está adequado, sai sem alterações.
# NÃO faz DROP/terminate se o template já existe.
PGPORT=5433 bash scripts/ensure_postgis_template.sh
```

Isso cria `template_napi_postgis` (IS_TEMPLATE) **sem dados** de `napi_geoai`
somente quando ausente. Se existir mas estiver incorreto, **falha com
diagnóstico** (sem destruição automática). No CI, a role do serviço PostGIS é
superuser e cria a extensão no temporário.

```powershell
py -3 scripts/db_ops.py backup --output-dir backups
py -3 scripts/db_ops.py restore-verify --dump backups\napi_geoai_YYYYMMDD.dump
```

Fluxo:

1. `backup` grava dump `-Fc` + manifesto `*.dump.manifest.json` sob o mesmo
   snapshot MVCC (`REPEATABLE READ` + `pg_export_snapshot` / `pg_dump
   --snapshot`): contagens e fingerprints (unidades/artefatos/`ingestion_runs`)
   coerentes com o dump mesmo se houver escrita concorrente.
2. Cria `napi_geoai_tmp_*` (via `TEMPLATE template_napi_postgis` quando existir).
3. `pg_restore --exit-on-error` **sem** `--clean`; se PostGIS já está no alvo,
   remove entradas `EXTENSION` do TOC (conflito esperado) — qualquer outro erro
   falha o restore (`exit != 0` ⇒ sem `match=true`).
4. Compara o restaurado ao **manifesto** (não a um snapshot live posterior).
5. Remove **somente** o temporário (`confirm=True` + prefixo `napi_geoai_tmp_`).

Recusado por construção: `DROP`/`pg_restore --clean` em `napi_geoai`,
`postgres`, `template0`, `template1`, `template_napi_postgis`.

## 4. Segurança local (`security-audit`)

Somente leitura. Cobre:

- `.gitignore` para `.env` e dumps
- host loopback / porta
- senha de exemplo
- `listen_addresses` e `pg_hba_file_rules` (se legíveis)
- privilégios da role atual

**Não altera** `postgresql.conf`, `pg_hba.conf` nem roles de outros projetos.
Mudanças necessárias aparecem como *recommendation* para aprovação humana.

### Propostas típicas (não aplicadas automaticamente)

1. Se `listen_addresses=*`: restringir a `localhost` **só** se nenhum outro
   serviço depender disso.
2. Preferir `scram-sha-256` em conexões locais não-peer.
3. Rotacionar senha `napi` e atualizar `.env` local.

## 5. Migrações

- Aplicar: `py -3 scripts/migrate_db.py`
- A migração `0001_init_postgis` **não** deve ser editada em instâncias já
  aplicadas; novas mudanças → `0002_*.sql` com plano de compatibilidade.
- Reexecução é idempotente (registro em `geoai.schema_migrations`).

## 6. Checklist pré-ingestão

- [ ] `db_ops.py doctor` sem `crit`
- [ ] Backup recente com SHA anotado
- [ ] `security-audit` revisado
- [ ] `DATABASE_URL` aponta para o banco pretendido (porta correta)
- [ ] Espaço em disco para dump + temporário

## 7. Incidentes e recuperação

| Sintoma | Ação |
|---|---|
| Doctor `crit` em geometria | Não sobrescrever produção; restaurar dump em temp e inspecionar |
| Falha no `pg_restore` | Temp é descartável; principal intacto; corrigir dump e repetir |
| Porta errada (5432 vs 5433) | `pg_lsclusters` / doctor mostra a URL redigida com porta |
| Suspeita de vazamento de senha | Rotacionar no Postgres; atualizar `.env`; não commitar |

Observabilidade básica: saída JSON do doctor/security; contagens no
restore-verify; logs do cluster em `/var/log/postgresql/`.

## 8. PowerShell ↔ WSL

```powershell
# Status do cluster
wsl -d Ubuntu-24.04 -- pg_lsclusters

# psql direto
wsl -d Ubuntu-24.04 -- env PGPASSWORD=*** psql -h 127.0.0.1 -p 5433 -U napi -d napi_geoai -c "SELECT PostGIS_Version();"
```

WSL encaminha `127.0.0.1:5433` do Windows para o Postgres no Ubuntu.

## Fora de escopo (MVP 05)

Novos conectores, aptidão solar, dashboard, Supabase remoto, pgvector/RAG,
Sentinel, Kafka, Airflow, infraestrutura paga.
