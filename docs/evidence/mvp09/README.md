# Evidências — MVP 09

| Arquivo | Conteúdo |
|---|---|
| `mapa_399_maringa.png` | 399 municípios IBGE + destaque Maringá (artefato real) |
| `ui_explorador.png` | Captura localhost Streamlit (Explorador) |
| `ui_home_nav.png` | Navegação multipágina |

Prévia: `streamlit run app/Home.py` → **Explorador Territorial**.
Não é publicação Cloud.

## QGIS

- Relatório: `data/derived/parana_municipios_2025_qgis_report.json`
- Engine: QGIS 3.44.15-Solothurn, GDAL 3.13.3, PROJ 9.8.1
- Método: `native:checkvalidity` + área elipsoidal `QgsDistanceArea` (EPSG:7019)
- Resultado: 399 válidos / 0 inválidos; `cd_mun_prefix_41_ok`; max |Δrel| área ~5.4e-5
- Escopo: validação geométrica no ZIP IBGE; SHA do GeoJSON de apresentação é vínculo de bytes separado

