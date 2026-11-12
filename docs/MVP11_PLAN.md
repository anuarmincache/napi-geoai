# MVP 11 — Plano curto (Issue #32)

## Inventário (11/11/2026)

| Peça | Estado |
|---|---|
| Malha 399 + `AREA_KM2` | Integrada (MVP 09 / QGIS) |
| SIGA painel MW conhecida | Integrado (MVP 10); 34 não associados |
| Estimativas IBGE 2026 | FTP `POP2026_20261029.xlsx` (edição 29/10/2026) |
| Conector populacional | A criar |
| Ficha/comparação/mapas | Extender Explorador + serviços portal |

## Decisões

1. **Edição oficial:** `POP2026_20261029.xlsx` (mais recente no FTP; referência **01/07/2026**).
2. **Join:** `CD_MUN` = `COD. UF` (2) + `COD. MUNIC` (5); fail-closed se ≠ 399 ou conjunto ≠ malha.
3. **UF Paraná:** total publicado 11 952 456; soma municipal PR deve bater.
4. **Densidade:** hab / `AREA_KM2` malha 2025 — misturar referências 2026/2025 com ressalva explícita.
5. **kW/hab:** MW fiscalizada conhecida × 1000 / pop; n/d se pop≤0 ou MW incompleto conforme política.
6. **QGIS:** sem geoprocessamento novo; malha já validada. Indicadores tabulares por código.

## Fora

MMGD, Censo como substituto da estimativa, Cloud, Supabase, serviços pagos, merge automático.
