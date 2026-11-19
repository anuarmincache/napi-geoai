# MVP 14 — Fase 3 (UI Streamlit MMGD)

## Escopo

Página e serviços de apresentação para MMGD/ANEEL no portal Streamlit existente, lendo **somente** artefatos derivados da Fase 2:

- `data/derived/mmgd_pr_panel.json`
- `data/derived/mmgd_pr.quality.json`
- `data/derived/mmgd_pr.provenance.json`

Sem download/agregação nacional em reruns.

## Arquivos

| Arquivo | Papel |
|---|---|
| `geoai/portal/mmgd_panel.py` | Loader fail-closed, KPIs, filtros, ranking, compare, mapa |
| `app/pages/8_Energia_MMGD.py` | UI Streamlit |
| `app/_bootstrap.py` | `cached_mmgd_panel()` |
| Integrações | Home, Domínios, Ficha municipal |

## Regras científicas

- Contagem primária = empreendimentos (`CodEmpreendimento`).
- `QtdUCRecebeCredito` = secundária.
- Filtro categórico (tipo **ou** classe **ou** porte): contagem via histogramas municipais; **MW não desagregado** no artefato → UI mostra `n/d` (não inventa).
- `by_cadastral_update_year` ≠ crescimento de conexões.
- MMGD ≠ SIGA.
- PII ausente nos artefatos públicos; loader bloqueia se detectar campos pessoais.

## Regenerar derivados (offline)

```powershell
py -3 scripts/prepare_mmgd_parana.py
```
