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

## Evidência (local)

```text
ruff check .     → All checks passed
pytest -q        → 79 passed, 2 skipped
napi_geoai + template_napi_postgis (:5433) preservados
```

CI e URL do PR: ver comentário na Issue #22 / PR correspondente.
