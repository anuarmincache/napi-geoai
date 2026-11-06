# Instalação e execução no Windows

Guia validado localmente com **Python 3.12**, **uv** e PowerShell no Windows 10/11. Não cobre implantação em produção, Streamlit publicado, Airflow nem Kafka.

## Pré-requisitos

- Git
- [uv](https://docs.astral.sh/uv/) (gerenciador de ambientes e pacotes)
- Acesso ao repositório `anuarmincache/napi-geoai`

Opcional para desenvolvimento geoespacial local: QGIS Desktop com o plugin MCP (porta local configurada no Cursor). O QGIS **não** é necessário para lint e testes desta fase.

## Setup

No PowerShell, a partir da pasta do repositório:

```powershell
git clone https://github.com/anuarmincache/napi-geoai.git
cd napi-geoai
uv python install 3.12
uv venv --python 3.12
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
```

Se a política de execução bloquear a ativação do venv:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Comandos validados

```powershell
ruff check .
pytest -q
```

Resultados esperados nesta fase: Ruff sem erros; pytest com os testes de importação do pacote `geoai` passando.

## Escopo desta fase

Incluído:

- pacote `geoai/`
- `pyproject.toml` com Ruff e pytest
- `.gitignore`
- workflow GitHub Actions de lint/testes (sem QGIS Desktop)

Fora do escopo:

- conectores oficiais de dados
- mapas ou resultados territoriais
- FastAPI / Streamlit em produção
- Airflow / Kafka
