# Projetos QGIS — NAPI GeoAI

## `parana_limites.qgz`

Projeto técnico do **limite oficial do Paraná** (IBGE Malha Municipal 2025).

- Camada (caminho **relativo** ao `.qgz`): `../data/derived/parana_uf_2025.geojson`
- CRS do projeto: EPSG:31982 (SIRGAS 2000 / UTM 22S) — visualização; ver limitação oeste/UTM 21S em `docs/FONTES_LIMITES_PARANA.md`
- Finalidade: verificação cartográfica e reprodutibilidade QGIS MCP
- **Não** contém indicadores de aptidão solar; o layout traz aviso explícito

### Teste após clonar em outra pasta

1. `python scripts/prepare_parana_boundary.py` (se `data/derived/` ainda não existir).
2. Abrir `qgis/parana_limites.qgz` no QGIS (perfil qualquer).
3. Confirmar que a camada `PR_UF_2025_IBGE` carrega sem caminho `C:\Users\...`.
4. Layout `mapa_tecnico_parana` → exportar PNG/PDF.

Geração assistida via QGIS MCP após o script de preparação.
