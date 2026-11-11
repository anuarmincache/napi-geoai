# Interface Streamlit — MVP 07

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

## Deploy futuro (não automático)

| Item | Valor |
|---|---|
| Entry point Cloud | `app/Home.py` |
| Requirements | `requirements-streamlit.txt` → `pip install -e ".[ui]"` |
| Python | 3.12 |
| Segredos | só no painel Streamlit Cloud — nunca no Git |
| Postgres local (:5433) | **não** acessível da Cloud |
| `DATABASE_URL` | opcional; demo do mapa **não** depende dela |
| Supabase | não provisionado neste MVP |

Smoke CI: `tests/test_streamlit_app.py` (`streamlit.testing.v1.AppTest`).
Esta etapa **não** publica no Community Cloud.
