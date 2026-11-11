# MVP 07 — Resultados (Issue #22)

## Entregáveis

| Item | Caminho |
|---|---|
| App Streamlit | `app/Home.py`, `app/pages/*` |
| Serviços portáveis | `geoai/portal/` |
| Guia UI / deploy | `docs/STREAMLIT_UI.md` |
| Requirements Cloud | `requirements-streamlit.txt` |
| Extra pip | `napi-geoai[ui]` (`streamlit`, `folium`) |
| Testes | `tests/test_portal.py` |

## O que funciona

- Navegação dos quatro domínios com status honesto (parcial/planejado).
- Mapa Folium do Paraná com GeoJSON IBGE versionado + proveniência.
- Controles reais: nível didático + opacidade/espessura do contorno.
- Catálogo de fontes e snapshot de qualidade sem novos downloads.
- Política de conexão local vs stub Supabase futuro (não provisionado).

## O que não faz (proposital)

Site institucional, ML, novos conectores, aptidão solar, publish Cloud,
criação de projeto Supabase, alteração do PostGIS :5433.

## Correções pós-revisão (PR #23)

| Ponto | Correção |
|---|---|
| Fail-closed do mapa | SHA/CRS/geometria inválidos → `available=False`; sem mapa |
| Proveniência | sem data/atributos inventados; status `undetermined` se faltar meta |
| Smoke Streamlit | `tests/test_streamlit_app.py` + CI com `.[ui]` |

## Evidência

Registrada no PR #23 após Ruff / pytest / CI desta rodada.
