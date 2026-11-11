# MVP 09 — Resultados

| Item | Resultado |
|---|---|
| Base | `main` @ `61745f7` (MVP 08) |
| Malha | IBGE `PR_Municipios_2025` — **399** municípios, EPSG:4674 |
| Área | `AREA_KM2` oficial IBGE |
| UI | `app/pages/5_Explorador_Territorial.py` |
| Portal | `geoai.portal.municipal_explorer` |
| Docs | `docs/MVP09_EXPLORADOR.md` |
| Publish / Supabase | **não** |
| QGIS | 3.44.15 / GDAL 3.13.3 / PROJ 9.8.1 — `native:checkvalidity` + área elipsoidal |
| Relatório QGIS | `data/derived/parana_municipios_2025_qgis_report.json` |

## Aceite

- [x] Mapa 399 + busca/seleção + 20 polos + comparação verificável
- [x] SHA/CRS/contagem/proveniência
- [x] Serviços fora do Streamlit
- [x] Testes + Ruff + CI
- [x] PR sem merge automático
- [x] Processamento QGIS real (validade + área independente) com hashes/versões
- [x] Fail-closed CRS / códigos 41xxxxx / AREA_KM2 / geometria + testes negativos
