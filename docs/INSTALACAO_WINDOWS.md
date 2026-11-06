# Instalação e execução no Windows

Guia validado localmente com **Python 3.12**, **uv** e PowerShell no Windows 10/11. Não cobre implantação em produção, Streamlit publicado, Airflow nem Kafka.

## Pré-requisitos

- Git
- [uv](https://docs.astral.sh/uv/) (gerenciador de ambientes e pacotes)
- Acesso ao repositório `anuarmincache/napi-geoai`

Opcional para desenvolvimento geoespacial local: QGIS Desktop com o plugin MCP (porta local configurada no Cursor). O QGIS **não** é necessário para lint e testes desta fase.

## Setup

### 1. Obter o código (apenas se ainda não houver clone)

No PowerShell, a partir da pasta onde o repositório deve ser criado (não execute isso de dentro de um clone existente):

```powershell
git clone https://github.com/anuarmincache/napi-geoai.git
cd napi-geoai
```

### 2. Ambiente Python (já dentro do clone)

Se o repositório já estiver clonado, abra o PowerShell na pasta `napi-geoai` e continue daqui:

```powershell
uv python install 3.12
uv venv --python 3.12
uv pip install -e ".[dev]"
```

## Comandos validados

Preferência: usar `uv run` (não exige ativar o venv nem alterar a política de execução do PowerShell):

```powershell
uv run ruff check .
uv run pytest -q
```

Alternativa com venv ativado:

```powershell
.\.venv\Scripts\Activate.ps1
ruff check .
pytest -q
```

Se a ativação do script for bloqueada pela política de execução, use `uv run` como acima. Alterar `Set-ExecutionPolicy` não é o procedimento padrão deste guia.

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
