# Evidências — MVP 09.1 (#28)

## UI Streamlit (capturas reais)

| Arquivo | Conteúdo |
|---|---|
| ui_geral_399.png | 1ª visita: busca visível, 399 de 399, mapa geral |
| ui_busca_maringa.png | Busca Maringá → 1 de 399, destaque no mapa, cartão |
| ui_busca_codigo.png | Busca por código IBGE 4115200 |
| ui_busca_filtro.png | Filtro ativo (contagem parcial) |
| ui_comparacao_maringa_londrina.png | Comparação Maringá × Londrina |

## Mapas (malha IBGE)

| Arquivo | Conteúdo |
|---|---|
| mapa_geral_399.png | 399 municípios (visão estadual) |
| mapa_maringa.png | Destaque Maringá |
| mapa_codigo_4115200.png | Recorte via código IBGE |
| mapa_comparacao_ref_londrina.png | Recorte Londrina (referência A/B) |

Regenerar mapas estáticos:

`	ext
py -3 scripts/capture_explorer_evidence.py
`

Basemap OSM na UI ao vivo; PNGs estáticos priorizam a malha vetorial.
