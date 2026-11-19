# MVP 14 — Handoff Fase 3 (UI Streamlit)

**Pré-condição:** Fase 2 concluída com restrições. Usar **somente** artefatos derivados já validados. Sem re-download salvo revalidação explícita. Sem commit/push/PR sem autorização.

## Onde está o trabalho

| Item | Valor |
|---|---|
| Worktree | `C:\Users\Admin\OneDrive\Área de Trabalho\napi-geoai-mmgd` |
| Branch | `feat/mvp14-aneel-mmgd-pr` @ `0db0ad1` (ainda não commitada a Fase 2) |
| Não usar | `napi-geoai-mvp04` (Sentinel/sujos), worktree portal-tabs legado |

## Dados prontos para a UI

| Artefato | Path |
|---|---|
| Painel municipal | `data/derived/mmgd_pr_panel.json` |
| Qualidade | `data/derived/mmgd_pr.quality.json` |
| Proveniência | `data/derived/mmgd_pr.provenance.json` |
| Paths helpers | `geoai.portal.paths.mmgd_panel_path` / `mmgd_quality_path` / `mmgd_provenance_path` |
| Bruto (gitignored) | `data/raw/aneel/empreendimento-geracao-distribuida.zip` |

Contrato do painel (resumo):

- `municipalities`: dict `CD_MUN` → métricas (`n_empreendimentos`, kW/MW, `qtd_uc_recebe_credito`, `by_tipo`, `by_classe`, `by_porte`, `by_cadastral_update_year`, `coverage`)
- `totals`, `unit_primary`, `unit_secondary_uc_credito`, `temporal_note_pt`, `notices_pt`, `periodo_referencia`
- Sem PII; ausência de potência ≠ zero inventado na UI

## Espelho de implementação (SIGA existente)

| Camada | SIGA (referência) | MMGD (a fazer) |
|---|---|---|
| Página | `app/pages/6_Energia_SIGA.py` | nova página (ex. `8_Energia_MMGD.py`) — não misturar métricas SIGA/MMGD |
| Loader | `geoai/portal/energy_panel.py` + `load_energy_panel_bundle` | loader espelho lendo `mmgd_*` paths |
| Bootstrap | `app/_bootstrap.py` | expor loader MMGD se necessário |
| Ficha | `7_Ficha_Municipal.py` (campos SIGA) | campos MMGD separados, rótulos claros |

## Regras inegociáveis na UI

1. Contagem primária = empreendimentos (`CodEmpreendimento`), não UCs crédito.
2. Mostrar proveniência (URL, SHA-256, `retrieved_at`, período `11/2026`).
3. Aviso: `DthAtualizaCadastralEmpreend` ≠ data de conexão.
4. MW instalado ≠ MWh; sem rentabilidade.
5. MMGD ≠ SIGA; potência MMGD em kW/MW a partir do painel derivado.
6. Se `reconcile_ok` for false ou arquivo ausente → fail-closed (mensagem, sem mapa inventado).
7. Atribuição ODbL / ANEEL na página.

## Checklist Fase 3

- [ ] Loader + validação de schema mínimo do JSON derivado
- [ ] Página Streamlit: mapa 399, filtros (tipo/classe/porte), indicadores, comparação 2 municípios
- [ ] Proveniência + quality summary na UI
- [ ] Ficha municipal: bloco MMGD separado do SIGA
- [ ] Testes de smoke do loader; verificação visual real no browser
- [ ] Ruff + Pytest verdes
- [ ] Pedir autorização antes de commit / push / PR

## Regenerar derivados (se necessário)

```text
cd "C:\Users\Admin\OneDrive\Área de Trabalho\napi-geoai-mmgd"
$env:PYTHONPATH=''; $env:PYTHONNOUSERSITE='1'
py -3 scripts/prepare_mmgd_parana.py
py -3 -m pytest tests/test_aneel_mmgd.py tests/test_mmgd_integration_real.py -q
```

## Estado Git ao encerrar Fase 2

Alterações **locais não commitadas**: conector, normalize/aggregate, prepare, paths, catalog, FONTES, testes, docs, `data/derived/mmgd_*`. ZIP permanece fora do Git.
