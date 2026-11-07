# NAPI GeoAI

<div align="center">

![NAPI GeoAI — Inteligência geoespacial para planejamento energético sustentável](assets/napi-geoai-banner.svg)

[![Status: Em desenvolvimento](https://img.shields.io/badge/Status-Em%20desenvolvimento-F0B429?style=for-the-badge)](ROADMAP.md)
[![Python](https://img.shields.io/badge/Python-Planejado-3776AB?style=for-the-badge&logo=python&logoColor=white)](docs/ARQUITETURA.md)
[![QGIS](https://img.shields.io/badge/QGIS-MCP-589632?style=for-the-badge&logo=qgis&logoColor=white)](docs/ARQUITETURA.md)

</div>

**Plataforma de inteligência geoespacial para o planejamento energético sustentável.**

**Idioma:** [Português](README.md) | [English](README.en.md)

> **Status:** projeto em fase de planejamento e implementação inicial. Ainda não há resultados territoriais validados ou aplicação em produção.

## Visão geral

O NAPI GeoAI é uma iniciativa de pesquisa e desenvolvimento liderada por **Anuar Mincache**, membro do **NAPI Energia Zero Carbono (NAPI EZC)**. O objetivo é desenvolver uma plataforma reprodutível para integrar dados geoespaciais públicos, avaliar cenários de planejamento energético e disponibilizar mapas, indicadores e relatórios científicos.

O primeiro caso de uso planejado é a **avaliação preliminar da aptidão territorial para sistemas fotovoltaicos no Paraná**. A aptidão não equivale a viabilidade técnica, econômica, ambiental ou regulatória de implantação.

## Objetivos

- Conectar fontes oficiais de dados por APIs e formatos geoespaciais documentados.
- Aplicar processamento raster e vetorial com Python e QGIS/PyQGIS.
- Desenvolver um motor científico independente da interface.
- Disponibilizar mapas e cenários em um aplicativo Streamlit, com API FastAPI.
- Registrar proveniência, versões dos dados, parâmetros e validações.
- Oferecer interface e documentação em português e inglês.

## Arquitetura planejada

```text
Fontes públicas (API / CSV / GeoTIFF / serviços GIS)
           ↓
Conectores e validação de dados
           ↓
Processamento científico (Python, QGIS/PyQGIS)
           ↓
Banco geoespacial (PostgreSQL/PostGIS) + arquivos raster
           ↓
API (FastAPI) → Interface (Streamlit PT/EN)
```

**Desenvolvimento:** Cursor + QGIS MCP + GitHub. A inclusão de Airflow será avaliada conforme a complexidade dos pipelines; Kafka não faz parte do MVP.

## Fontes candidatas

- INPE/LABREN — dados de recurso solar.
- ANEEL — dados de geração.
- IBGE — limites e identificação territorial.
- MapBiomas — cobertura e uso da terra.
- ONS e órgãos ambientais — dados adicionais, conforme disponibilidade e licenças.

Cada fonte será avaliada quanto a formato, licenciamento, resolução, atualização e qualidade. A lista acima não implica que os conectores já estejam implementados.

## Equipe e reconhecimento

**Idealização e liderança técnica:** Anuar Mincache.

**Colaboradores científicos (participação confirmada pelo responsável do projeto):** Luiz Fernando Cotica; Ivair Aparecido Santos; Gustavo Sanguino Dias.

Veja [AUTHORS.md](AUTHORS.md). O projeto está inicialmente hospedado nesta conta pessoal. Eventual vinculação ou transferência institucional dependerá de definição e autorização apropriadas.

## Plano de desenvolvimento

Consulte [ROADMAP.md](ROADMAP.md) e [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Desenvolvimento local (Windows)

A fundação Python desta fase foi validada localmente com `uv`, Python 3.12, `ruff check` e `pytest`. Guia completo: [docs/INSTALACAO_WINDOWS.md](docs/INSTALACAO_WINDOWS.md).

```powershell
uv python install 3.12
uv venv --python 3.12
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
ruff check .
pytest -q
```

O pacote `geoai/` inclui fundação Python e, no MVP 02, conector IBGE + validação do limite do Paraná (produto técnico territorial). Ainda não há aplicação publicada nem mapas de aptidão solar.

Documentação do recorte: [docs/FONTES_LIMITES_PARANA.md](docs/FONTES_LIMITES_PARANA.md), [docs/QGIS_MCP.md](docs/QGIS_MCP.md), [docs/MVP02_RESULTADOS.md](docs/MVP02_RESULTADOS.md). O CRS de mapa EPSG:31982 (UTM 22S) é para visualização da maior parte do estado; a faixa oeste exige UTM 21S/outra projeção justificada para métricas estaduais.

Catálogo de fontes e contratos de ingestão (MVP 03): [docs/FONTES_OFICIAIS.md](docs/FONTES_OFICIAIS.md), [docs/CONTRATOS_INGESTAO.md](docs/CONTRATOS_INGESTAO.md).

## Reprodutibilidade e responsabilidade

Não serão apresentados dados ilustrativos como resultados científicos. Critérios de aptidão, restrições territoriais e pesos devem ser transparentes, revisados e submetidos a análise de sensibilidade. Nenhuma decisão de investimento deve ser tomada exclusivamente com base em mapas preliminares.

## Licença

**Ainda não definida.** O repositório é público para consulta, mas não há licença de reutilização concedida neste momento. A licença será escolhida após avaliação dos requisitos institucionais e de propriedade intelectual.
