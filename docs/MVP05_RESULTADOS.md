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

## Evidência local (WSL nativo :5433) — pós-correção (2026-11-10)

Estado preservado: `napi_geoai` e `template_napi_postgis` **não** foram droados.

```text
ruff check .                  → All checks passed
pytest (ops + restante*)      → 46 passed, 2 skipped (*sem test_aneel_connector pré-existente)
tests/test_db_ops_*           → 9 passed
db_ops doctor                 → OK (exit 0); template presente
db_ops backup                 → sha256=216c164f…7158cc + manifesto
db_ops restore-verify         → match=true; reference_kind=manifest
                              → ingestion_runs=11; fingerprints iguais
                              → temp napi_geoai_tmp_* removido
```

\* `test_download_rejects_invalid_cached_csv` (ANEEL) falha de forma independente deste MVP;
não faz parte do escopo da Issue #16 / revisão do PR #17.

## Fora de escopo

Supabase remoto, novos conectores, análises energéticas, merge automático.
