# Instalação e execução no Windows

Guia validado localmente com **Python 3.12**, **uv** e PowerShell no Windows 10/11. Não cobre implantação em produção, Streamlit publicado, Airflow nem Kafka.

## Pré-requisitos

- Git
- [uv](https://docs.astral.sh/uv/) (gerenciador de ambientes e pacotes)
- Acesso ao repositório `anuarmincache/napi-geoai`

Opcional para desenvolvimento geoespacial local: QGIS Desktop com o plugin MCP em `127.0.0.1:9875` (ver [QGIS_MCP.md](QGIS_MCP.md)). O QGIS **não** é necessário para lint e a maior parte dos testes unitários; o download IBGE é opcional via `scripts/prepare_parana_boundary.py`.

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
uv pip install -e ".[dev,db]"
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

Resultados esperados nesta fase: Ruff sem erros; pytest passando (importação + limites/conector IBGE com mocks/fixtures). Testes marcados `postgis` só passam com `DATABASE_URL` apontando para PostgreSQL/PostGIS (Docker Compose ou CI).

## PostGIS local (MVP 04)

Ver [BANCO_DADOS.md](BANCO_DADOS.md). Resumo:

1. Instalar Docker Desktop (gratuito para uso pessoal) **ou** PostgreSQL+PostGIS no Windows/WSL.
2. `docker compose up -d` e copiar `.env.example` → `.env`.
3. `uv run python scripts/migrate_db.py`
4. `uv run python scripts/import_parana_boundary_db.py`

Sem Docker/Postgres nesta máquina, os testes `postgis` são *skipped* localmente e executados no GitHub Actions. **Não** use a conta Supabase remota neste MVP.

## Escopo desta fase

Incluído:

- pacote `geoai/` (metadados, conector IBGE, validação de limites, camada `geoai.db`)
- script `scripts/prepare_parana_boundary.py`
- migrações PostGIS e importador do limite UF Paraná
- projeto QGIS técnico do Paraná (`qgis/`)
- `pyproject.toml` com Ruff e pytest
- `.gitignore`
- workflow GitHub Actions de lint/testes + serviço PostGIS (sem QGIS Desktop; sem Supabase remoto)

Fora do escopo:

- mapas de aptidão solar ou indicadores energéticos
- FastAPI / Streamlit em produção
- Airflow / Kafka
- conexão à conta Supabase existente
