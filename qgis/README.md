# Projetos QGIS — NAPI GeoAI

## `parana_limites.qgz`

Projeto técnico do **limite oficial do Paraná** (IBGE Malha Municipal 2025).

- Camada: `data/derived/parana_uf_2025.geojson`
- CRS do projeto: EPSG:31982 (SIRGAS 2000 / UTM 22S)
- Finalidade: verificação cartográfica e reprodutibilidade QGIS MCP
- **Não** contém indicadores de aptidão solar; qualquer legenda deve deixar isso explícito

Geração assistida via QGIS MCP após executar `scripts/prepare_parana_boundary.py`.
