# NAPI GeoAI

**Geospatial intelligence platform for sustainable energy planning.**

**Language:** [Português](README.md) | [English](README.en.md)

> **Status:** in development, with no public deployment. The repository already includes territorial artifacts with provenance: IBGE 2025 municipalities (MVP 09), the ANEEL SIGA panel (MVP 10), and IBGE 2026 population estimates (MVP 11). That is in-repository data validation. It is not a production application, not a photovoltaic-suitability result, and not a Streamlit Cloud release.

## Overview

NAPI GeoAI is a research and development initiative led by **Anuar Mincache**, a member of **NAPI Energia Zero Carbono (NAPI EZC)**. Its goal is to build a reproducible platform that integrates public geospatial datasets, explores energy-planning scenarios, and provides maps, indicators, and scientific reports.

The initial use case is a **preliminary land-suitability assessment for photovoltaic systems in Paraná, Brazil**. Suitability scores are not equivalent to technical, economic, environmental, or regulatory feasibility.

## Planned capabilities

- Data ingestion through documented APIs and geospatial datasets.
- Raster and vector processing with Python and QGIS/PyQGIS.
- A testable scientific engine separate from the web interface.
- FastAPI backend and bilingual Streamlit frontend.
- Dataset provenance, versioning, parameter tracking, and validation.

## Proposed stack

Python; QGIS/PyQGIS and QGIS MCP; Cursor; GitHub; FastAPI; Streamlit; PostgreSQL/PostGIS. Airflow may be adopted if workflow complexity justifies it; Kafka is not part of the MVP.

Candidate datasets include INPE/LABREN, ANEEL, IBGE, MapBiomas, ONS, and relevant environmental agencies, subject to source verification, access terms, and data quality.

## Leadership and collaboration

**Initiator and technical lead:** Anuar Mincache.

**Scientific collaborators (participation confirmed by the project lead):** Luiz Fernando Cotica; Ivair Aparecido Santos; Gustavo Sanguino Dias.

See [AUTHORS.md](AUTHORS.md), [ROADMAP.md](ROADMAP.md), and [architecture](docs/ARQUITETURA.md).

## Local development (Windows)

The Python foundation for this phase was validated locally with `uv`, Python 3.12, `ruff check`, and `pytest`. Full guide: [docs/INSTALACAO_WINDOWS.md](docs/INSTALACAO_WINDOWS.md).

```powershell
uv python install 3.12
uv venv --python 3.12
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
ruff check .
pytest -q
```

Delivered MVP status is documented in the [Portuguese README](README.md). This English page does not repeat that history.

**Current state (19 November 2026).** The Streamlit portal runs locally with official data for all 399 municipalities of Paraná:

- Territory and population: IBGE 2025 municipal mesh and 2026 population estimates.
- Energy: ANEEL SIGA plants in operation and ANEEL MMGD distributed generation (November 2026 snapshot). MW is not MWh, and the two registries are not added together.
- Agriculture and livestock: IBGE PAM and PPM, 2025, through the SIDRA API.
- Land cover: MapBiomas Collection 11, 1985 to 2025. Change between years is a stock difference, not a deforestation rate.
- Calculators: appliance consumption and preliminary photovoltaic sizing, with user inputs only.
- Satellite vegetation (NDVI): a list of 97 municipalities and a download plan. Only Maringá has a measured scene and no NDVI map is published.

The portal is not deployed publicly. It does not compute solar suitability and does not state economic feasibility. Details, tables and examples are in the [Portuguese README](README.md).

## Scientific integrity and license

Illustrative data must never be presented as measured results. All models must document assumptions, constraints, uncertainty, and sensitivity analyses. **No software license has been selected yet**; public repository access does not imply permission to reuse the code.
