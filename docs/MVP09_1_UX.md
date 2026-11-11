# MVP 09.1 — UX do Explorador Territorial (#28)

## Objetivo

Tornar inequívoco que **todos os 399 municípios** estão disponíveis, com busca
visível, sincronização correta e mapa geral na primeira visita — sem nova
ingestão e sem alterar contratos QGIS/IBGE.

## Mudanças

| Área | Comportamento |
|---|---|
| Busca | Destacada antes do mapa; placeholder `Digite cidade ou código IBGE, ex.: Maringá / 4115200` |
| Contagem | `N de 399` sempre visível |
| Catálogo | Campo limpo → seletor com os **399**; `limit=None` em `search_municipalities` |
| Sem resultado | `Nenhum município encontrado` — **sem** fallback para 399 |
| Atalhos | 20 polos; ao aplicar, limpam a busca e sincronizam seletor + mapa |
| 1ª visita | Mapa geral do Paraná, sem município pré-selecionado |
| Metadados | `st.expander('Fonte e metodologia')` fechado |
| Controles | `st.expander('Personalizar mapa')` |
| Comparação | Município A usa a seleção atual quando houver; só nome/código/`AREA_KM2` |

## Preservado

- Dados IBGE, SHA/CRS/fail-closed, relatório QGIS
- GeoPandas/PostGIS complementares; Streamlit sem QGIS na Cloud
- Serviços em `geoai.portal`

## Limitações

- Basemap OSM depende de rede no navegador do usuário.
- HTML Folium em iframe Streamlit pode variar visualmente entre navegadores;
  fundo `#e8eef5` e padding no `fit_bounds` reduzem faixa preta, sem garantia
  pixel-perfect em todos os zoom levels.
- Screenshots de mapa estático (evidência) usam limites vetoriais; o basemap OSM
  aparece na UI ao vivo.

## Evidências

`docs/evidence/mvp09_1/`
