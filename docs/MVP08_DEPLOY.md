# MVP 08 — Preparação de deploy (Streamlit Community Cloud)

> **Status:** app pronta para deploy controlado. **Publicação pública só após
> aprovação explícita** do responsável (nome/URL + prévia visual).
> Este documento **não** publica a aplicação e **não** provisiona Supabase.

## Objetivo

Disponibilizar caminho reproduzível para a **primeira versão demonstrativa
institucional** do NAPI GeoAI, reutilizando artefatos do MVP 07, sem banco
remoto e sem inventar camadas temáticas.

## Pré-requisitos auditados

| Item | Valor / evidência |
|---|---|
| Entry point | `app/Home.py` |
| Requirements Cloud (auto) | **`app/requirements.txt`** → `-e ..[ui]` (mesmo dir do entrypoint) |
| Atalho local | `requirements-streamlit.txt` → `-e .[ui]` (raiz; **não** auto-detectado) |
| Python | **3.12** (`.python-version`, `requires-python >=3.12`) |
| Tema / UX | `.streamlit/config.toml` + CSS em `app/_bootstrap.py` |
| CORS / XSRF | CORS no default (`true`); `enableXsrfProtection = true` |
| Artefatos IBGE | `data/derived/parana_uf_2025.{geojson,provenance,validation}.json` no Git |
| PostGIS local `:5433` | **não** usado pela demo; **não** expor |
| Segredos | `.env` no `.gitignore`; nenhum secret no repo |
| Licença | ainda **não definida** (README) — repositório público para consulta |

## Arquitetura preservada

```text
app/                 # Streamlit thin (hospedável)
geoai/portal/        # serviços portáveis (migração futura p/ site próprio)
geoai/*              # motor científico (independente da UI)
data/derived/        # GeoJSON + proveniência + validação
```

Fail-closed do mapa, proveniência sem metadados inventados e testes AppTest
permanecem obrigatórios.

## Execução local (prévia)

```powershell
py -3 -m pip install -e ".[dev,ui]"
py -3 -m streamlit run app/Home.py
```

Percorrer: Início → Domínios → Mapa Paraná → Fontes e qualidade → Sobre e deploy.
Em mobile/estreito: menu lateral ☰; ajustar “Altura do mapa” na página do mapa.

## Checklist de implantação manual (responsável)

1. Conta [Streamlit Community Cloud](https://share.streamlit.io/) vinculada ao GitHub `anuarmincache`.
2. **New app** → Repository `anuarmincache/napi-geoai`.
3. Branch: `main` (após merge do PR deste MVP) **ou** branch de prévia se autorizada.
4. Main file path: **`app/Home.py`**.
5. Advanced:
   - Python version: **3.12**
   - Dependências: a Cloud deve achar sozinha `app/requirements.txt`
     (não depende de `requirements-streamlit.txt`, que **não** é nome oficial).
6. **Não** definir secrets `DATABASE_URL` / chaves Supabase nesta etapa.
7. Escolher **nome e URL** (`….streamlit.app`) — **pausar** se ainda não aprovados.
8. Deploy → inspecionar logs (`-e ..[ui]` / napi-geoai[ui], sem erro de GDAL/wheel).
9. Smoke manual pós-deploy: Home carrega; mapa Folium; badges de domínio; JSON de qualidade.
10. Privacidade: manter privada ou pública **somente** com decisão explícita.

### Detecção oficial de dependências

Ordem da Community Cloud (pasta do entrypoint, depois raiz): `uv.lock` →
`Pipfile` → `environment.yml` → **`requirements.txt`** → `pyproject.toml`
([docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)).
`app/requirements.txt` prevalece sobre o `pyproject.toml` da raiz e evita o
gerenciador Poetry implícito. O editável `-e ..[ui]` aponta para a raiz do
monorepo (pai de `app/`).

### Rollback

- No painel Streamlit: **Reboot** / redeploy do commit anterior da branch; ou
- Pausar/deletar o app (não apaga o Git); ou
- Reverter o merge no GitHub e redeployar `main` estável.

### Limitações / custos Community Cloud

| Tema | Nota |
|---|---|
| Recursos | App sleep após inatividade (plano free); cold start |
| Rede | Cloud **não** alcança Postgres WSL `:5433` |
| Binários | Wheels manylinux de geopandas/pyogrio — `packages.txt` vazio de propósito |
| Uso | Free tier: adequado a demo institucional leve; monitorar minutos/recursos |
| Analytics | `gatherUsageStats = false` em `.streamlit/config.toml` |

## Plano futuro Supabase (não executar agora)

Ver [SUPABASE_FUTURE.md](SUPABASE_FUTURE.md). Resumo: projeto isolado, leitura
mínima, replicação seletiva versionada, só quando houver consulta dinâmica
real. **Proibido** criar projeto ou copiar dados neste MVP.

## Testes e CI

```powershell
py -3 -m ruff check .
py -3 -m pytest -q
```

Inclui `tests/test_streamlit_app.py` (AppTest) e `tests/test_cloud_ready.py`
(configuração de hospedagem). Workflow `.github/workflows/ci.yml` instala `.[dev,db,ui]`.
