# MVP 02 — Resultados e evidências (Issue #2)

Registro objetivo da execução local. **Não** apresenta indicadores de aptidão
solar como resultados reais.

## 1. Log QGIS MCP

Instância configurada: `default=127.0.0.1:9875` (arquivo local Cursor; **não** versionado).

| Ferramenta | Resultado |
|---|---|
| `list_qgis_instances` | `reachable: true`, host `127.0.0.1`, porta `9875`, QGIS `3.44.15-Solothurn` |
| `ping` | `pong: true` |
| `get_qgis_info` | `qgis_version: 3.44.15-Solothurn`, plugins_count `5`, perfil `default` |
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
| Geometria válida / exportável | sim (`all_valid` + `validation_exportable`) |
| CRS mapa técnico | EPSG:31982 (visualização; oeste do PR → UTM 21S, ver docs) |

Artefatos: `data/derived/parana_uf_2025.{geojson,provenance.json,validation.json}` com caminhos **relativos**.

## 3. Testes automatizados

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check geoai tests scripts
```

Resultado local (pós-revisão PR #12): **14 passed**; Ruff limpo.

| Ambiente | Cobertura |
|---|---|
| CI (GitHub Actions) | mocks HTTP + fixture sintética; **não** baixa ZIP IBGE; **não** abre QGIS |
| Windows local | testes `pytest.mark.integration` executados com `data/raw/ibge/PR_UF_2025.zip` presente |

Inclui rejeição de CRS ausente/divergente, geometria vazia, não poligonal e checagem fatal pré-exportação.

## 4. Produtos QGIS

| Arquivo | Função |
|---|---|
| `qgis/parana_limites.qgz` | Projeto com datasource relativo `../data/derived/parana_uf_2025.geojson` |
| `qgis/exports/parana_limites_tecnico.png` | Layout com polígono do Paraná visível + legenda/norte/escala/fonte/aviso |
| `qgis/exports/parana_canvas_preview.png` | Preview do canvas |

### Teste visual do layout (pós-revisão cartográfica)

Causa do PNG em branco: camada do layout com datasource relativo inválido na sessão (`isValid=False`, `featureCount=-2`), enquanto o canvas ainda refletia estado anterior.

Correção aplicada:
1. Recarregar `parana_uf_2025.geojson` com camada válida (1 feição).
2. Item `QgsLayoutItemMap` com CRS `EPSG:31982`, `setLayers([layer])`, extent transformada de `layer.extent()` + margem 8%.
3. Simbologia reforçada (preenchimento verde, contorno escuro).
4. Reexportar PNG e **inspecionar visualmente** o contorno do Paraná centralizado/legível (não basta `exportToImage` OK).
5. Regravar `.qgz` com datasource relativo.

Checklist visual confirmado no PNG final: polígono presente; legenda; norte; escala; fonte IBGE; aviso de que **não** é aptidão solar.

Teste pós-clone: ver [qgis/README.md](../qgis/README.md).

## 5. Reprodutibilidade

1. Configurar QGIS MCP em `127.0.0.1:9875` (local).
2. `uv pip install -e ".[dev]"` (ou venv equivalente).
3. `python scripts/prepare_parana_boundary.py`
4. Abrir `qgis/parana_limites.qgz` em outra pasta clonada e confirmar camada válida.

## 6. Limitações

- CI não executa QGIS Desktop nem baixa o ZIP IBGE.
- UTM 22S não cobre bem a faixa oeste do Paraná para área estadual total.
- Nenhum peso, máscara ou indicador energético foi calculado neste MVP.
