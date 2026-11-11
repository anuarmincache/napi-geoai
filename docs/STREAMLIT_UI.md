# Interface Streamlit — MVP 07 / 08

## Inventário reutilizado

| Origem | Uso na UI |
|---|---|
| `data/derived/parana_uf_2025.*` | Mapa + proveniência + validação |
| `geoai.domains` | Cartões e status dos 4 domínios |
| `geoai.presentation` | Textos didáticos (3 níveis) |
| `geoai.quality` | Snapshot tabular de qualidade |
| `geoai.connectors.catalog` | Tabela de fontes |
| PostGIS :5433 | **Não alterado**; demo não depende dele |

## Arquitetura enxuta

```text
app/                  # Streamlit (thin)
geoai/portal/         # serviços portáveis (sem Streamlit)
geoai/{connectors,quality,domains,presentation,db,boundaries}
```

## Executar localmente

```powershell
py -3 -m pip install -e ".[dev,ui]"
py -3 -m streamlit run app/Home.py
```

Não exige Supabase nem `DATABASE_URL` para a demonstração do mapa.

## Integridade do mapa (fail-closed)

`load_parana_layer` só marca `available=True` se:

1. GeoJSON legível com geometria;
2. CRS verificável (`source_crs` na validação ou CRS no arquivo) = EPSG:4674;
3. `derived_geojson_sha256` confere com os bytes do GeoJSON;
4. validação geométrica não declara `all_valid=false`.

SHA divergente / CRS ausente → erro claro, **sem** exibir mapa como validado.

## UX / acessibilidade (MVP 08)

- Tema institucional em `.streamlit/config.toml` (navy `#1f4e79`)
- Tipografia Source Sans 3 / IBM Plex; contraste e foco visível
- `prefers-reduced-motion` respeitado no CSS
- Badges com texto (não só cor); `help=` em controles principais
- Altura do mapa ajustável; layout wide + sidebar em mobile (☰)
- Footer com limites da demonstração

## Deploy Community Cloud

Guia operacional: [MVP08_DEPLOY.md](MVP08_DEPLOY.md). Plano Supabase futuro:
[SUPABASE_FUTURE.md](SUPABASE_FUTURE.md).

| Item | Valor |
|---|---|
| Entry point | `app/Home.py` |
| Requirements | `requirements-streamlit.txt` → `pip install -e ".[ui]"` |
| Python | 3.12 (`.python-version`) |
| Segredos | só no painel Streamlit Cloud — nunca no Git |
| Postgres local (:5433) | **não** acessível da Cloud |
| `DATABASE_URL` | opcional; demo do mapa **não** depende dela |
| Supabase | não provisionado |
| Publicação | **manual**, após aprovação do responsável |

Smoke CI: `tests/test_streamlit_app.py` + `tests/test_cloud_ready.py`.
