# MVP 10 — Plano curto (Issue #30)

## Inventário (11/11/2026)

| Peça | Estado |
|---|---|
| `geoai.connectors.aneel` | PROTOTYPE — download CKAN CSV, parse `;`, filtro UF, cache TTL |
| Catálogo `aneel.siga` | URL CSV principal confirmada; MMGD só catalogado (fora do MVP) |
| Fixture `aneel_siga_mini.csv` | 5 PR + 2 MG; inclui `MdaPotenciaFiscalizadaKw` |
| Municípios IBGE 399 | Integrados (#26/#28); ZIP alta fidelidade em `data/raw/ibge/` |
| QGIS/PyQGIS | 3.44.15 + MCP; padrão de relatório municipal já existe |
| Domínio Energia | `partial` — painel SIGA MW municipal (este MVP) |

## Decisões

1. **Fonte:** CSV SIGA principal (recurso `11ec447d-…`), não MMGD.
2. **Métrica principal:** capacidade **fiscalizada** (`MdaPotenciaFiscalizadaKw` → MW); outorgada exibida à parte.
3. **Fase padrão UI:** `Operação`; demais fases filtráveis, nunca somadas no default.
4. **Associação municipal:** point-in-polygon QGIS sobre ZIP IBGE; `DscMuninicpios` só checagem auxiliar.
5. **399 municípios:** sempre no catálogo; `status_dados = sem_empreendimento | agregado | nao_associavel`.
6. **Artefatos versionados:** JSON agregado leve + relatórios; CSV bruto **não** commitado.

## Incrementos

| # | Entrega |
|---|---|
| A | Ingestão PR + relatório qualidade (fases, nulos, coords) |
| B | Worker QGIS join + relatório correspondência + agregados |
| C | `geoai.portal` energia + página Streamlit + testes/CI/evidências |

## Fora

MMGD, MWh, aptidão solar, Cloud, Supabase, serviços pagos, merge automático.
