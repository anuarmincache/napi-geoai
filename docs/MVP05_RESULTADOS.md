# MVP 05 — Resultados (Issue #16)

## Entregáveis

| Item | Caminho |
|---|---|
| Operação / runbooks | `docs/OPERACAO_BANCO.md` |
| CLI | `scripts/db_ops.py` (`doctor`, `backup`, `restore-verify`, `security-audit`) |
| Template PostGIS (restore) | `scripts/ensure_postgis_template.sh` |
| Módulos | `geoai/db/doctor.py`, `backup.py`, `security_audit.py`, `pg_tools.py`, `url_safety.py` |
| Testes | `tests/test_db_ops_unit.py`, `tests/test_db_ops_postgis.py` |

## Aceite

- [x] Diagnóstico coerente com PG16/PostGIS 3.4 / SRID 4674 (porta **5433**)
- [x] Backup `-Fc` com SHA-256; dumps em `backups/` (gitignore); URL redigida
- [x] Restore em `napi_geoai_tmp_*` (via `template_napi_postgis` ou superuser CI)
- [x] Banco `napi_geoai` preservado; demais serviços intocados
- [x] Auditoria de segurança somente leitura
- [x] Sem Supabase / sem novos conectores / sem análise energética

## Evidência local (WSL nativo :5433)

```text
ensure_postgis_template.sh → template_napi_postgis OK (PostGIS 3.4)
db_ops doctor              → OK (exit 0), template presente
db_ops backup              → ~442 KB, sha256 dc208f5c…d4bbf09
db_ops restore-verify      → match=true; temp removido; napi_geoai intacto
tests/test_db_ops_*        → 8 passed
```

## CI

Serviço `postgis/postgis` + `postgresql-client`; role superuser cria extensão no
temporário sem template. Esperado: suite completa incluindo backup/restore.
