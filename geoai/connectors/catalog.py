"""Catálogo estático das fontes oficiais candidatas ao NAPI GeoAI."""

from __future__ import annotations

from geoai.connectors.contracts import AccessMode, SourceSpec, SourceStatus

# Data da consulta documental/HTTP aos portais oficiais (não = data do dado).
CATALOGUED_AT = "2026-11-11"

SOURCE_CATALOG: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="ibge.malhas_municipais.pr_uf_2025",
        organization="IBGE",
        product="Malhas Territoriais / Malhas Municipais — UF Paraná",
        access_mode=AccessMode.HTTP_FILE,
        entry_url=(
            "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
            "malhas_territoriais/malhas_municipais/"
        ),
        download_url=(
            "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
            "malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/PR_UF_2025.zip"
        ),
        formats=("zip/shp", "geojson-derived"),
        license_note=(
            "Arquivos públicos IBGE/Geociências (geoftp); citar órgão, produto e "
            "edição. Sem SPDX IBGE dedicado; verificar condições institucionais."
        ),
        official_update_cadence="edição anual (municipio_YYYY) — produto versionado",
        verification_policy="TTL local 7d + conditional GET; force_refresh sob demanda",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Paraná (UF)",
        crs_or_coords="EPSG:4674 (SIRGAS 2000)",
        granularity="UF (polígono)",
        auth_required=False,
        status=SourceStatus.PROTOTYPE,
        notes="Conector prototype em geoai.connectors.ibge (compatível MVP 02).",
        connector_module="geoai.connectors.ibge",
    ),
    SourceSpec(
        source_id="ibge.malhas_municipais.pr_municipios_2025",
        organization="IBGE",
        product="Malhas Territoriais / Malhas Municipais — municípios Paraná",
        access_mode=AccessMode.HTTP_FILE,
        entry_url=(
            "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
            "malhas_territoriais/malhas_municipais/"
        ),
        download_url=(
            "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
            "malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/"
            "PR_Municipios_2025.zip"
        ),
        formats=("zip/shp", "geojson-derived-presentation"),
        license_note=(
            "Arquivos públicos IBGE/Geociências (geoftp); citar órgão, produto e "
            "edição. Sem SPDX IBGE dedicado; verificar condições institucionais."
        ),
        official_update_cadence="edição anual (municipio_YYYY) — produto versionado",
        verification_policy="TTL local 7d + conditional GET; force_refresh sob demanda",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Paraná (399 municípios)",
        crs_or_coords="EPSG:4674 (SIRGAS 2000)",
        granularity="município (polígono)",
        auth_required=False,
        status=SourceStatus.PROTOTYPE,
        notes=(
            "MVP 09: 399 CD_MUN; AREA_KM2 oficial; GeoJSON de apresentação "
            "simplificado em data/derived."
        ),
        connector_module="geoai.connectors.ibge",
    ),
    SourceSpec(
        source_id="ibge.estimativas_populacao.municipios_2026",
        organization="IBGE",
        product="Estimativas da população residente — municípios 2026",
        access_mode=AccessMode.HTTP_FILE,
        entry_url=(
            "https://www.ibge.gov.br/estatisticas/sociais/populacao/"
            "9103-estimativas-de-populacao.html"
        ),
        download_url=(
            "https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2026/"
            "POP2026_20261029.xlsx"
        ),
        formats=("xlsx", "ods", "pdf"),
        license_note=(
            "IBGE — Estimativas da população residente; citar fonte e edição. "
            "Não confundir com Censo Demográfico."
        ),
        official_update_cadence="anual (referência 1º de julho)",
        verification_policy="SHA-256 + join estrito 399 CD_MUN × malha 2025",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Brasil (municípios); painel NAPI = Paraná 399",
        crs_or_coords="tabular (CD_MUN); malha associada EPSG:4674",
        granularity="município",
        auth_required=False,
        status=SourceStatus.PROTOTYPE,
        notes=(
            "MVP 11: edição POP2026_20261029; referência 01/07/2026; "
            "conector geoai.connectors.ibge_population."
        ),
        connector_module="geoai.connectors.ibge_population",
    ),
    SourceSpec(
        source_id="aneel.siga.empreendimentos_geracao",
        organization="ANEEL",
        product="SIGA — empreendimentos de geração (CSV principal)",
        access_mode=AccessMode.CKAN_RESOURCE,
        entry_url=(
            "https://dadosabertos.aneel.gov.br/dataset/"
            "siga-sistema-de-informacoes-de-geracao-da-aneel"
        ),
        download_url=(
            "https://dadosabertos.aneel.gov.br/dataset/"
            "6d90b77c-c5f5-4d81-bdec-7bc619494bb9/resource/"
            "11ec447d-698d-4ab8-977f-b424d5deee6a/download/"
            "siga-empreendimentos-geracao.csv"
        ),
        formats=("csv", "xml"),
        license_note=(
            "ODbL (Open Data Commons). Atribuição e share-alike conforme ODbL; "
            "verificar pacote CKAN (license_id=odc-odbl)."
        ),
        official_update_cadence=(
            "Pacote CKAN: 'Mensal e diária' (há recurso CSV diário separado). "
            "Recurso CSV principal consultado em 2026-11-07 (Last-Modified "
            "HTTP 2026-11-01)."
        ),
        verification_policy="TTL 24h + ETag/Last-Modified; force_refresh disponível",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Brasil (SigUFPrincipal; coords empreendimento)",
        crs_or_coords=(
            "coordenadas geográficas WGS84 aproximadas (lat/lon com vírgula decimal)"
        ),
        granularity="empreendimento de geração",
        auth_required=False,
        status=SourceStatus.PROTOTYPE,
        notes="Conector geoai.connectors.aneel. Não calcular aptidão solar.",
        connector_module="geoai.connectors.aneel",
    ),
    SourceSpec(
        source_id="aneel.mmgd.empreendimentos",
        organization="ANEEL",
        product="Mini e Micro Geração Distribuída (MMGD)",
        access_mode=AccessMode.CKAN_RESOURCE,
        entry_url=(
            "https://dadosabertos.aneel.gov.br/dataset/"
            "relacao-de-empreendimentos-de-geracao-distribuida"
        ),
        download_url=(
            "https://dadosabertos.aneel.gov.br/dataset/"
            "relacao-de-empreendimentos-de-geracao-distribuida/resource/"
            "b1bd71e7-d0ad-4214-9053-cbd58e9564a7/download/"
            "empreendimento-geracao-distribuida.zip"
        ),
        formats=("zip/csv", "parquet"),
        license_note="ODbL (portal ANEEL Dados Abertos).",
        official_update_cadence=(
            "Atualização periódica no CKAN; houve suspensão 23/09/2025–13/11/2025 "
            "(migração SISGD→MMGD). Confirmar data do recurso antes de usar."
        ),
        verification_policy="Apenas catalogado; sem conector automático neste MVP",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Brasil (município/UF)",
        crs_or_coords="atributos municipais (sem geometria nativa no CSV principal)",
        granularity="empreendimento MMGD",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="Arquivo grande (~100+ MiB). Não versionar bruto.",
        connector_module=None,
    ),
    SourceSpec(
        source_id="inpe.labren.atlas_solar_2017",
        organization="INPE/LABREN",
        product="Atlas Brasileiro de Energia Solar — 2ª edição (2017)",
        access_mode=AccessMode.FTP_OR_HTTP_INDEX,
        entry_url="https://labren.ccst.inpe.br/atlas_2017.html",
        download_url=None,
        formats=("csv", "shp", "qgs", "pdf-metadados"),
        license_note=(
            "Uso como dado de entrada para análises: permitido com citação "
            "LABREN/CCST/INPE. Reprodução/cópia comercial integral ou parcial: "
            "exige autorização expressa do INPE/CCST. Não redistribuir o Atlas "
            "como produto comercial sem autorização."
        ),
        official_update_cadence=(
            "Produto estático (estimativas 1999–2015). Não é feed near-real-time."
        ),
        verification_policy="Catalogado; download manual/futuro conector por UF",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Brasil / por UF / sedes municipais",
        crs_or_coords="grade 0,1°; lat/lon do centróide (ver metadados do pacote)",
        granularity="célula ~10 km; Wh/m².dia",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="Sem API REST única (índice LABREN / data.inpe.br).",
        connector_module=None,
    ),
    SourceSpec(
        source_id="mapbiomas.brazil.lulc",
        organization="MapBiomas",
        product="Cobertura e uso da terra — Brasil",
        access_mode=AccessMode.GEE_ASSET,
        entry_url="https://plataforma.brasil.mapbiomas.org/",
        download_url="https://storage.googleapis.com/mapbiomas-public/",
        formats=("geotiff", "gee-imagecollection"),
        license_note=(
            "Citar projeto MapBiomas e coleção/versão. Consultar termos vigentes "
            "em mapbiomas.org antes de redistribuir rasters; dados pesados não "
            "devem ser commitados. GEE pode exigir conta Google autorizada."
        ),
        official_update_cadence="Coleções anuais (ex.: Collection 10) — não diário",
        verification_policy="Catalogado; sem download automático no MVP",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Brasil (recortes por território na plataforma)",
        crs_or_coords=(
            "raster projetado (EPSG típico WGS84/Pseudo-Mercator conforme produto)"
        ),
        granularity="30 m (Landsat) / produtos 10 m beta",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="Plataforma web, GEE ou GCS. Sem REST genérico único.",
        connector_module=None,
    ),
    SourceSpec(
        source_id="ons.dados_abertos.capacidade_geracao",
        organization="ONS",
        product="Capacidade Instalada de Geração (Dados Abertos)",
        access_mode=AccessMode.CKAN_RESOURCE,
        entry_url="https://dados.ons.org.br/dataset/capacidade-geracao",
        download_url=None,
        formats=("csv", "xlsx", "parquet", "json-dicionario"),
        license_note=(
            "CC-BY: crédito ao ONS e indicação de alterações. Dados 'como estão'."
        ),
        official_update_cadence=(
            "Portal declara atualização diária (~12h e 19h) para este conjunto "
            "(consulta 2026-11-07)."
        ),
        verification_policy="Catalogado; conector tabular futuro",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="SIN / usinas despachadas ONS",
        crs_or_coords="atributos tabulares (sem geometria neste conjunto)",
        granularity="unidade geradora / usina",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="API SINtegre (login agente) fora do MVP.",
        connector_module=None,
    ),
    SourceSpec(
        source_id="ons.dados_abertos.linha_transmissao",
        organization="ONS",
        product="Linhas de Transmissão da Rede de Operação",
        access_mode=AccessMode.CKAN_RESOURCE,
        entry_url="https://dados.ons.org.br/dataset/linha-transmissao",
        download_url=None,
        formats=("csv", "xlsx", "parquet"),
        license_note=(
            "CC-BY: crédito ao ONS e indicação de alterações. Dados 'como estão'."
        ),
        official_update_cadence=(
            "Portal declara atualização diária (consulta 2026-11-07)."
        ),
        verification_policy="Catalogado; conector tabular futuro",
        catalogued_at=CATALOGUED_AT,
        spatial_coverage="Rede ≥230 kV (UF/subsistema)",
        crs_or_coords="atributos tabulares",
        granularity="linha de transmissão",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="Catalogado; sem conector neste MVP.",
        connector_module=None,
    ),
)


def get_source(source_id: str) -> SourceSpec:
    for spec in SOURCE_CATALOG:
        if spec.source_id == source_id:
            return spec
    known = ", ".join(s.source_id for s in SOURCE_CATALOG)
    raise KeyError(f"fonte desconhecida: {source_id}. Conhecidas: {known}")


def list_sources(*, status: SourceStatus | None = None) -> tuple[SourceSpec, ...]:
    if status is None:
        return SOURCE_CATALOG
    return tuple(s for s in SOURCE_CATALOG if s.status == status)
