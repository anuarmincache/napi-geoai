# MVP 02 — Resultados e evidências (Issue #2)

Registro objetivo da execução local. **Não** apresenta indicadores de aptidão
solar como resultados reais.

## 1. Log QGIS MCP

Instância configurada: `default=127.0.0.1:9875` (arquivo local Cursor; **não** versionado).

| Ferramenta | Resultado |
|---|---|
| `list_qgis_instances` | `reachable: true`, host `127.0.0.1`, porta `9875`, QGIS `3.44.15-Solothurn`, pid observado |
| `ping` | `pong: true` |
| `get_qgis_info` | `qgis_version: 3.44.15-Solothurn`, plugins_count `5`, perfil `default` |
| `get_project_info` (inicial) | projeto sem título, `layer_count: 0`, CRS `EPSG:4326` |
| `get_project_info` (final) | `qgis/parana_limites.qgz`, título técnico, 1 camada, CRS `EPSG:31982` |

Procedimentos: [QGIS_MCP.md](QGIS_MCP.md).

## 2. Dados IBGE

Fonte e critérios: [FONTES_LIMITES_PARANA.md](FONTES_LIMITES_PARANA.md).

| Campo | Valor |
|---|---|
| URL | `.../municipio_2025/UFs/PR/PR_UF_2025.zip` |
| SHA-256 | `9429eaf1b5a15f6b4d2dc2b9762da6f0642c237bfa54b5dab13d078a3dfe2998` |
| Tamanho | 346662 bytes |
| CRS origem | EPSG:4674 |
| Feições | 1 |
| Geometria válida | sim (`all_valid: true`) |
| CRS mapa técnico | EPSG:31982 |

Artefatos: `data/derived/parana_uf_2025.{geojson,provenance.json,validation.json}`.

## 3. Testes automatizados

Comando (venv local):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check geoai tests scripts
```

Resultado observado nesta execução: **8 passed**; Ruff sem erros após correções.

Testes cobrem fixture sintética, reparo geométrico, conector IBGE com HTTP mock e
leitura do ZIP real quando presente (`pytest.mark.integration`).

## 4. Produtos QGIS

| Arquivo | Função |
|---|---|
| `qgis/parana_limites.qgz` | Projeto técnico versionável |
| `qgis/exports/parana_limites_tecnico.png` | Layout A4 com aviso explícito anti-aptidão |
| `qgis/exports/parana_canvas_preview.png` | Preview do canvas |

Legenda/aviso no layout: o mapa **não** representa aptidão solar.

## 5. Reprodutibilidade

1. Configurar QGIS MCP em `127.0.0.1:9875` (local).
2. `uv pip install -e ".[dev]"` (ou venv equivalente).
3. `python scripts/prepare_parana_boundary.py`
4. Abrir `qgis/parana_limites.qgz` no QGIS Desktop.

## 6. Limitações

- CI não executa QGIS Desktop nem baixa o ZIP IBGE.
- O GeoJSON derivado é um produto de verificação; análises de área devem usar CRS métrico.
- Nenhum peso, máscara ou indicador energético foi calculado neste MVP.
