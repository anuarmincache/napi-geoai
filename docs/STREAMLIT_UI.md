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

## Deploy futuro (não automático)

Ver página **Sobre e deploy** na app e `requirements-streamlit.txt`.
Segredos só no painel Streamlit Cloud. Postgres local não é exposto.
