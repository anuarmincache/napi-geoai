# MVP 05 — Resultados (Issue #16 / PR #17)

## Entregáveis

| Item | Caminho |
|---|---|
| Operação / runbooks | `docs/OPERACAO_BANCO.md` |
| CLI | `scripts/db_ops.py` |
| Template PostGIS (idempotente) | `scripts/ensure_postgis_template.sh` |
| Módulos | `geoai/db/doctor.py`, `backup.py`, `security_audit.py`, … |
| Testes | `tests/test_db_ops_unit.py`, `tests/test_db_ops_postgis.py` |

## Correções pós-revisão (segurança operacional)

| Ponto da revisão | Correção |
|---|---|
| Template com `DROP` incondicional | Script create-if-absent; se existe e OK → no-op; se inadequado → falha sem DROP |
| `pg_restore` exit 1 ignorado | Exige exit 0 + `--exit-on-error`; TOC sem EXTENSION quando PostGIS já no alvo |
| `ingestion_runs` não comparado | Contagem + fingerprint `runs_fingerprint` no manifesto/restore |
| Referência live vs dump antigo | Manifesto `*.dump.manifest.json` acoplado ao dump |
| Limpeza de temp | `finally` só dropa `napi_geoai_tmp_*` se criado; protegidos recusados |

## Correções pós-revisão (commit 784644e / CI + cache)

| Ponto da revisão | Correção |
|---|---|
| `pg_restore` / `transaction_timeout` no CI | `postgresql-client-16` + PATH `/usr/lib/postgresql/16/bin` + assert major cliente=servidor |
| Cache CSV ANEEL inválido | `content_validator` antes de reuso/TTL/304; testes com datas relativas + MockTransport |
| Manifesto vs dump sob escrita concorrente | `REPEATABLE READ` + `pg_export_snapshot` + `pg_dump --snapshot` |
| Template `TEMPLATE`/`OWNER` vs GRANT literais | Nomes fixos `template_napi_postgis`/`napi`; só `PGPORT` configurável (5433) |

## Evidência local (WSL nativo :5433)

Estado preservado: `napi_geoai` e `template_napi_postgis` **não** são droados por estes fluxos.

Ver logs atualizados no comentário do PR após Ruff/pytest/CI desta rodada.

## Fora de escopo

Supabase remoto, novos conectores, análises energéticas, merge automático.
