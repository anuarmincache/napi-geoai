# MVP 06 — Resultados (Issue #19)

## Entregáveis

| Item | Caminho |
|---|---|
| ADR organização modular | `docs/adr/0001-domain-modules.md` |
| Arquitetura modular | `docs/ARQUITETURA_MODULAR.md` |
| Qualidade / schemas | `geoai/quality/` |
| Domínios + indicadores | `geoai/domains/` |
| Metadados didáticos | `geoai/presentation/` |
| Testes | `tests/test_quality_contracts.py`, `tests/test_domains_and_presentation.py` |

## Reuso MVPs 01–05

- Conectores/contratos MVP 03 (`SourceSpec`, `ProvenanceRecord`, catálogo IBGE).
- Limite PR MVP 02–04 como piloto de schema (`territorial_pr_uf_schema`).
- PostGIS/ops MVP 04–05 **intocados** (sem migração; porta 5433 preservada).

## Fora de escopo (cumprido)

Site/dashboard, ML, novos conectores, ingestão massiva, Supabase remoto, Kafka/Airflow.

## Correções pós-revisão (PR #21)

| Ponto | Correção |
|---|---|
| Não-finitos / bool | `math.isfinite`; rejeita NaN/Inf/bool; aceita string numérica |
| SHA-256 | formato 64 hex + verificação opcional contra bytes |
| Grandezas energéticas | tipagem por campo + unidades canônicas; colunas multi-grandeza OK |
| Metadados didáticos | `updated_at` ISO nullable + `update_policy`; sem “reprojetada” |
| Escopo do piloto | `validate_tabular_record`; smoke com artefatos PR em `data/derived` |

## Evidência

Registrada no PR #21 após Ruff / pytest / CI desta rodada.
