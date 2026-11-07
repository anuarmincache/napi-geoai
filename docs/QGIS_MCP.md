# QGIS MCP — procedimentos locais (Windows)

Guia operacional da ponte **Cursor → QGIS MCP → QGIS Desktop** usada no MVP 02.
**Não commitar** `C:\Users\Admin\.cursor\mcp.json` (contém configuração local de porta/host).

## Ambiente validado

| Item | Valor |
|---|---|
| QGIS | 3.44.15-Solothurn (LTR) |
| Executável | `C:\Program Files\QGIS 3.44.15\bin\qgis-ltr-bin.exe` |
| Plugin | `qgis_mcp_plugin` (perfil `default`) |
| Host/porta do plugin | `127.0.0.1:9875` |
| Perfil QGIS | `%APPDATA%\QGIS\QGIS3\profiles\default\` |

## Configuração Cursor (referência — não versionar)

Em `C:\Users\Admin\.cursor\mcp.json`, o servidor `qgis` deve apontar a instância default:

```json
"env": {
  "QGIS_MCP_INSTANCES": "default=127.0.0.1:9875"
}
```

A porta padrão do projeto `qgis-mcp` é 9876; neste ambiente usa-se **9875** para evitar conflito com outros add-ons MCP.

## Inicialização

1. Abrir o QGIS Desktop (perfil `default`).
2. Garantir que o plugin MCP está ativo e escutando em **9875** (seta ao lado do botão MCP na barra de ferramentas, ou `QGIS_MCP_PORT=9875` no ambiente de lançamento).
3. No Cursor, confirmar com as ferramentas MCP: `list_qgis_instances`, `ping`, `get_qgis_info`, `get_project_info`.

Esperado: `reachable: true`, `pong: true`, versão `3.44.15-Solothurn`.

## Escopo

- QGIS MCP controla o Desktop **local** para projetos, estilos e exportação de mapas técnicos.
- Não substitui o motor Python (`geoai/`) nem pipelines de produção.
- Não publicar aplicação Streamlit/FastAPI nesta fase.
