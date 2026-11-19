# MVP 14 — MMGD/ANEEL — Relatório técnico Fase 2

**Data:** 2026-11-18  
**Worktree:** `napi-geoai-mmgd` (`feat/mvp14-aneel-mmgd-pr` @ `0db0ad1` = `origin/main`)  
**Escopo:** pipeline de dados + qualidade + testes. **Sem** integração Streamlit, commit, push, PR, merge ou deploy.

## Veredito

**Fase 2 de dados: CONCLUÍDA COM RESTRIÇÕES.**  
Painel derivado PR reconciliado (399/399), proveniência registrada, privacidade ok nos artefatos públicos, Ruff/Pytest verdes com ZIP real. Interface e MVP ponta a ponta **pendentes**.

## 1. Isolamento

| Item | Status |
|---|---|
| Worktree separado da Sentinel / mvp04 | CONFIRMADO |
| Base `origin/main` verificada | CONFIRMADO (`0db0ad1`) |
| Branch `feat/mvp14-aneel-mmgd-pr` | CONFIRMADO |
| Artefatos SIGA / NDVI não alterados | CONFIRMADO |
| Commit / push / PR | **não realizados** (conforme autorização) |

## 2. Download oficial (uma vez)

| Campo | Valor |
|---|---|
| URL | `https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-b622-40438d40aba2/resource/b1bd71e7-d0ad-4214-9053-cbd58e9564a7/download/empreendimento-geracao-distribuida.zip` |
| Recuperado (UTC) | 2026-11-18T14:16:42Z |
| Tamanho | 113 212 595 bytes (~108 MiB) |
| SHA-256 local | `b6bf91d1cf6f50657730ed3990d3f3b8628afdf90a55a1b951433679986ef45f` |
| Hash CKAN declarado | `9bcca568def744eda95943f22abd866b` (MD5-like; **≠** SHA-256) |
| Licença | ODbL (ANEEL Dados Abertos) |
| ETag / Last-Modified | presentes; LM `Wed, 18 Nov 2026 05:37:58 GMT` |
| Local bruto (gitignored) | `data/raw/aneel/empreendimento-geracao-distribuida.zip` |
| Tempo download | ~331,6 s (1ª vez); revalidação cache ~0,22 s |
| Membro ZIP | `empreendimento-geracao-distribuida.csv` (~1,56 GiB) |

Metadados: `data/raw/aneel/mmgd_download_gate2.json`.

## 3. Esquema e dicionário operacional

31 colunas no CSV (`;`, UTF-8-BOM). Colunas críticas mapeadas:

| Uso | Coluna oficial |
|---|---|
| Município (nome) | `NomMunicipio` |
| Município (IBGE) | `CodMunicipioIbge` — **presente** |
| UF | `SigUF` (+ `CodUFibge`) |
| Tecnologia | `SigTipoGeracao` / `DscFonteGeracao` |
| Potência | `MdaPotenciaInstaladaKW` (kW) |
| Classe | `DscClasseConsumo` |
| Identificador empreendimento | `CodEmpreendimento` |
| UCs com crédito | `QtdUCRecebeCredito` |
| Atualização cadastral | `DthAtualizaCadastralEmpreend` (**≠** conexão) |
| Snapshot | `AnmPeriodoReferencia` = `11/2026`; `DatGeracaoConjuntoDados` = `2026-11-18` |

**IBGE municipal:** CONFIRMADO no dataset. Join por igualdade exata `CodMunicipioIbge` ↔ `CD_MUN` da malha IBGE 2025 PR. Sem fuzzy match.

## 4. Unidades (sem double-count)

| Conceito | Campo / regra | Uso |
|---|---|---|
| Empreendimento gerador | 1 linha ≈ 1 `CodEmpreendimento` | **contagem primária** |
| UC beneficiária de créditos | `QtdUCRecebeCredito` (soma) | **secundária**; não substitui empreendimentos |
| Duplicatas de código | 0 no PR | CONFIRMADO |

## 5. Qualidade Paraná (snapshot preparado)

| Métrica | Valor | Classificação |
|---|---|---|
| Linhas nacionais streamadas | 4 745 133 | CONFIRMADO |
| Linhas PR streamadas | 335 905 | CONFIRMADO |
| Válidos | 335 899 | CONFIRMADO |
| Rejeitados | 6 (`MdaPotenciaInstaladaKW` inválida) | CONFIRMADO |
| Não associados a município IBGE PR | 0 (após filtro UF=PR + códigos 41xxxxxx) | CONFIRMADO |
| Municípios IBGE com ≥1 registro | 399 / 399 | CONFIRMADO |
| Municípios zero confirmado | 0 | CONFIRMADO |
| `reconcile_ok` | `true` | CONFIRMADO |
| Potência conhecida | 6 901 846,59 kW ≈ **6 901,85 MW** | CONFIRMADO |
| Soma UCs crédito | 621 012 | CONFIRMADO |
| Por tipo (válidos) | UFV 335 781; UTE 106; CGH 8; EOL 2; (vazio) 2 | CONFIRMADO |

Artefatos derivados (sem PII):

- `data/derived/mmgd_pr_panel.json` (~384 KiB)
- `data/derived/mmgd_pr.quality.json`
- `data/derived/mmgd_pr.provenance.json`

## 6. Privacidade e licença

Campos excluídos de iteração pública e artefatos derivados:

`NumCPFCNPJ`, `NomTitularEmpreendimento`, `CodCEP`, `NumCoordESub`, `NumCoordNSub`

Scan textual do painel: ausência de `NomTitular` / `NumCPFCNPJ` / CEP / logradouro — CONFIRMADO.  
Redistribuição/derivação: sujeitas a ODbL — nota registrada na proveniência.

## 7. Código entregue (Fase 2)

| Módulo | Função |
|---|---|
| `geoai/connectors/aneel_mmgd.py` | download/cache, validação ZIP, stream CSV, strip PII |
| `geoai/energy/mmgd_normalize.py` | normalização tipada + reject reasons |
| `geoai/energy/mmgd_aggregate.py` | agregação municipal; primary = empreendimento |
| `scripts/prepare_mmgd_parana.py` | pipeline one-pass nacional → filtro PR |
| `geoai/connectors/catalog.py` | status → `PROTOTYPE` + `connector_module` |
| `geoai/portal/paths.py` | paths `mmgd_*` |
| Testes | `tests/test_aneel_mmgd.py`, `tests/test_mmgd_integration_real.py` |

## 8. Benchmarks e testes

| Check | Resultado |
|---|---|
| Ruff (módulos MMGD) | passou |
| Pytest unitário + catalog | 9 passed (~1,4 s) |
| Pytest + integração ZIP real | **13 passed** (~35 s) |
| Agregação prepare | ~133,2 s; peak tracemalloc ~44,5 MiB |
| Espaço ZIP | 113 212 595 B |

## 9. Restrições explícitas (não inventar)

- Ausência ≠ zero de geração energética histórica; zero municipal só quando o código IBGE está na malha e o recorte PR fechou sem linhas.
- `DthAtualizaCadastralEmpreend` **não** é data de conexão — séries anuais cadastrais ≠ crescimento de conexões.
- MW instalado ≠ MWh gerado; sem estimativa de rentabilidade.
- MMGD ≠ SIGA.

## 10. Status por critério de autorização

1. Worktree isolado — **funcional**  
2. Download único + metadados — **funcional**  
3. Esquema / colunas — **funcional**  
4. Empreendimento vs UC crédito — **funcional**  
5. IBGE municipal — **funcional** (código nativo)  
6. Conector / validação / parser / agregação — **funcional**  
7. Relatório qualidade PR — **funcional**  
8. Sem fictício / ROI / missing-as-zero indevido — **respeitado**  
9. PII / ODbL — **funcional** nos artefatos derivados  
10. Ruff / Pytest / integração real — **funcional**

### Funcional (Fase 2)

- Pipeline local completo até `mmgd_pr_panel.json` + quality + provenance  
- Contagens e MW instalado reconciliados com a malha de 399 municípios  
- Testes automatizados com ZIP oficial

### Pendente (próximas fases — UI / E2E)

- Integração no Streamlit existente (mapa, indicadores, filtros, comparações)  
- Testes visuais reais no painel  
- Tratamento de erro na UI com proveniência exibida ao usuário  
- Revisão ODbL de atribuição na interface pública  
- Política de atualização/TTL do ZIP (hoje: cache local + revalidação)

### Bloqueado / fora de escopo agora

- Commit, push, PR, merge, deploy — **bloqueados até autorização explícita**  
- Declaração de “MVP concluído” — **bloqueada** até E2E Streamlit com dados validados  
- Uso de NDVI/Sentinel ou alteração de artefatos SIGA — **congelados**  
- Qualquer join fuzzy município-nome — **proibido**; não necessário neste dataset

## Artefatos de referência Gate 2

- `data/raw/aneel/mmgd_download_gate2.json`  
- `data/raw/aneel/mmgd_pr_scan_gate2.json`  
- `docs/MVP14_FASE2_RELATORIO.md` (este arquivo)

## Encerramento / próxima etapa

Handoff UI: [`docs/MVP14_FASE3_HANDOFF.md`](MVP14_FASE3_HANDOFF.md).  
Nada commitado. Retomar no worktree `napi-geoai-mmgd` com os JSON derivados já validados.
