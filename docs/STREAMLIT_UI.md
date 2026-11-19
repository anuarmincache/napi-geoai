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
- Mapas Folium via `render_html_map` (`st.iframe` + HTML em cache temp); não usar `st.components.v1.html`

## Deploy Community Cloud

Guia operacional: [MVP08_DEPLOY.md](MVP08_DEPLOY.md). Plano Supabase futuro:
[SUPABASE_FUTURE.md](SUPABASE_FUTURE.md).

| Item | Valor |
|---|---|
| Entry point | `app/Home.py` |
| Requirements (Cloud) | `app/requirements.txt` → `-e ..[ui]` (auto-detectado) |
| Requirements (local) | `pip install -e ".[ui]"` ou `requirements-streamlit.txt` |
| Python | 3.12 (`.python-version`) |
| Segredos | só no painel Streamlit Cloud — nunca no Git |
| Postgres local (:5433) | **não** acessível da Cloud |
| `DATABASE_URL` | opcional; demo do mapa **não** depende dela |
| Supabase | não provisionado |
| Publicação | **manual**, após aprovação do responsável |

Smoke CI: `tests/test_streamlit_app.py` + `tests/test_cloud_ready.py`.

## Portal — Home de impacto, navegação agrupada e ferramentas

- `app/Home.py`: hero, quatro KPIs lidos dos artefatos derivados em tempo de
  execução (malha IBGE, população IBGE, MMGD e SIGA/ANEEL), mapa MMGD,
  busca de município com salto para a Ficha municipal, caminhos por público
  e quadro disponível / aguardando dados / planejado. Nenhum número é fixo
  no código: artefato ausente aparece como "indisponível".
- `app/_bootstrap.py`: menu lateral agrupado (`NAV_GROUPS`) com
  `st.page_link`; a navegação automática foi desligada em
  `.streamlit/config.toml` (`showSidebarNavigation = false`).
- `app/pages/11_Ferramentas.py` + `geoai/tools/energy_calc.py` (Issue #38):
  consumo/custo de equipamentos e dimensionamento fotovoltaico preliminar.
  Funções puras e testadas (`tests/test_energy_calc.py`). Tarifa e
  irradiação (HSP) não têm valor padrão: são entradas obrigatórias do
  usuário. PR e potência do módulo são hipóteses declaradas.

## Identidade visual NAPI Energia Zero-Carbono (2026-11-19)

- `assets/napi-ezc-logo.png`: logotipo cedido pelo projeto. Fundo transparente
  e traços brancos: usar só sobre fundo claro (barra lateral e rodapé).
- `app/ui/theme.py`: folha de estilo. Paleta tirada do logotipo: verde-floresta
  `#2f4a33`, verde `#455b40`, verde-folha `#73a535`, amarelo-sol `#fcc817`.
  Títulos em Montserrat, texto em Source Sans 3.
- `app/ui/art.py`: ilustrações próprias em SVG (paisagem da Home e uma por
  tema). Não reproduzem marca de terceiros.
- `page_header()` em `app/_bootstrap.py`: faixa de título de todas as páginas.
- Menu: Domínios, Mapa do Paraná e o piloto Sentinel saíram do menu principal
  e continuam acessíveis por "Sobre o projeto".
- UEM e Fundação Araucária aparecem por nome no rodapé. Os logotipos delas não
  estão no repositório.
