# MVP 14 — Fase 3 — Relatório técnico (UI MMGD)

**Data:** 2026-11-19  
**Worktree:** `napi-geoai-mmgd` · branch `feat/mvp14-aneel-mmgd-pr` @ `0db0ad1` + alterações locais  
**Veredito:** **PRONTO PARA REVISÃO LOCAL** (sem commit/push/PR até autorização).

## 1. Arquivos principais

| Arquivo | Papel |
|---|---|
| `geoai/portal/mmgd_panel.py` | Serviço fail-closed (loader, KPIs, filtros, ranking, compare, mapa) |
| `app/pages/8_Energia_MMGD.py` | Página Streamlit |
| `app/_bootstrap.py` | `cached_mmgd_panel()` + `render_html_map` |
| `app/Home.py`, `domain_views.py`, `7_Ficha_Municipal.py` | Navegação / copy / bloco MMGD na ficha |
| `tests/test_mmgd_panel.py`, `tests/test_streamlit_app.py` | Testes |
| `docs/MVP14_FASE3_UI.md`, README(s) | Documentação |
| Artefatos (inalterados) | `mmgd_pr_panel.json`, `.quality.json`, `.provenance.json` |

## 2. Testes

| Check | Resultado |
|---|---|
| Ruff (repo) | **pass** (~0,3 s) |
| Pytest completo | **199 passed**, 9 skipped (~74 s) |
| Novos testes serviço MMGD | 8 passed |
| AppTest página MMGD + filtro UFV | passed |
| Browser real | página OK, mapa iframe, filtro UFV, comparação A/B |

## 3. Capturas

- `reports/local_streamlit_review/screenshots_mmgd/01_mmgd_todas.png`
- `reports/local_streamlit_review/screenshots_mmgd/02_mmgd_ufv.png`  
(`reports/` permanece gitignored)

Portal: http://127.0.0.1:8516/Energia_MMGD

## 4. Métricas reconciliadas (escopo total)

| Métrica | Valor |
|---|---|
| Empreendimentos válidos | **335 899** |
| Rejeitados PR | **6** (`MdaPotenciaInstaladaKW` inválida) |
| MW instalada conhecida | **6 901,8** |
| UCs crédito (secundário) | **621 012** |
| Municípios | **399/399** · `reconcile_ok=true` |
| Período | **11/2026** · conjunto **2026-11-18** |
| Filtro UFV (contagem) | **335 781**; MW = **n/d no filtro** (honesto) |

## 5. Tempos medidos (UI)

| Evento | Tempo |
|---|---|
| Cache artefatos (1ª carga) | ~198 ms |
| Cache (rerun) | ~0 ms |
| Mapa Folium (escopo total) | ~776 ms |

Sem download/agregação nacional no Streamlit.

## 6. Limitações científicas

- Contagem primária = empreendimentos; UCs crédito ≠ empreendimentos.
- Filtro categórico (um por vez): histograma municipal de contagem; **MW/UC não desagregados** no artefato → UI mostra `n/d`, não inventa.
- `by_cadastral_update_year` ≠ crescimento de conexões (aviso explícito).
- MMGD ≠ SIGA; MW ≠ MWh.
- PII excluída; loader bloqueia se detectar campos pessoais no JSON.

## 7. Pendências

- MW por tecnologia/classe/porte exigiria enriquecer o artefato Fase 2 (fora desta UI).
- Commit / push / PR / merge / deploy — **aguardam autorização**.
- Ordem da sidebar: Streamlit ordena por nome de arquivo (`8_` após `7_`); OK funcionalmente.

## 8. Estado Git

Alterações Fase 2 + Fase 3 **locais não commitadas**. Sem push/PR.

## 9. Veredito

Interface MMGD **funciona ponta a ponta** com dados oficiais derivados: filtros com efeito, mapa renderizado, comparação A/B, fail-closed, proveniência ODbL, SIGA preservado.  
**Pronto para revisão humana** antes de commit/PR.
