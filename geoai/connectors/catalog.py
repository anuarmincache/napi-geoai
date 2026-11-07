"""Catálogo estático das fontes oficiais candidatas ao NAPI GeoAI."""

from __future__ import annotations

from geoai.connectors.contracts import AccessMode, SourceSpec, SourceStatus

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
            "Arquivos públicos IBGE/Geociências (geoftp); citar origem e edição."
        ),
        update_cadence="edição anual (municipio_YYYY)",
        spatial_coverage="Paraná (UF)",
        crs_or_coords="EPSG:4674 (SIRGAS 2000)",
        granularity="UF (polígono)",
        auth_required=False,
        status=SourceStatus.PROTOTYPE,
        notes="Conector prototype em geoai.connectors.ibge.",
        connector_module="geoai.connectors.ibge",
    ),
    SourceSpec(
        source_id="aneel.siga.empreendimentos_geracao",
        organization="ANEEL",
        product="SIGA — Sistema de Informações de Geração",
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
        license_note="ODbL (Open Data Commons Open Database License).",
        update_cadence="mensal e diária (recursos distintos no CKAN)",
        spatial_coverage="Brasil (campo SigUFPrincipal; coords empreendimento)",
        crs_or_coords=(
            "coordenadas geográficas WGS84 aproximadas (lat/lon com vírgula decimal)"
        ),
        granularity="empreendimento de geração",
        auth_required=False,
        status=SourceStatus.PROTOTYPE,
        notes=(
            "Portal CKAN + download HTTP do CSV. API CKAN package_show disponível. "
            "Conector prototype em geoai.connectors.aneel. Não calcular aptidão solar."
        ),
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
        license_note="ODbL.",
        update_cadence=(
            "atualização periódica (houve suspensão 2025 por migração SISGD→MMGD)"
        ),
        spatial_coverage="Brasil (município/UF)",
        crs_or_coords="atributos municipais (sem geometria nativa no CSV principal)",
        granularity="empreendimento MMGD",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="Arquivo grande (~100+ MiB). Não versionar bruto. Prototype futuro.",
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
            "Uso analítico permitido com citação; reprodução comercial integral/"
            "parcial exige autorização do INPE/CCST."
        ),
        update_cadence=(
            "produto estático (série 1999–2015); não confundir com near-real-time"
        ),
        spatial_coverage="Brasil / por UF / sedes municipais",
        crs_or_coords="grade 0,1°; lat/lon do centróide (ver metadados do pacote)",
        granularity="célula ~10 km; Wh/m².dia (GHI, DNI, difusa, plano inclinado, PAR)",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes=(
            "Download via índice LABREN/data.inpe.br (não há API REST única). "
            "Conector de ingestão ainda não implementado neste MVP."
        ),
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
        license_note="Ver termos MapBiomas; citar coleção/versão.",
        update_cadence="coleções anuais (ex.: Collection 10)",
        spatial_coverage="Brasil (recortes por território na plataforma)",
        crs_or_coords=(
            "raster projetado (EPSG típico WGS84/Pseudo-Mercator conforme produto)"
        ),
        granularity="30 m (Landsat) / produtos 10 m beta",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes=(
            "Acesso real: plataforma web (GeoTIFF), Google Earth Engine assets, "
            "ou GCS mapbiomas-public. Sem REST genérico único. Rasters pesados "
            "fora do Git."
        ),
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
        license_note="CC-BY (crédito ao ONS).",
        update_cadence="diária (portal declara ~12h e 19h)",
        spatial_coverage="SIN / usinas despachadas ONS",
        crs_or_coords="atributos tabulares (sem geometria neste conjunto)",
        granularity="unidade geradora / usina",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes=(
            "Portal https://dados.ons.org.br — download sem login. "
            "Portal API SINtegre exige credencial de agente e está fora do MVP."
        ),
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
        license_note="CC-BY (crédito ao ONS).",
        update_cadence="diária",
        spatial_coverage="Rede ≥230 kV (UF/subsistema)",
        crs_or_coords="atributos tabulares",
        granularity="linha de transmissão",
        auth_required=False,
        status=SourceStatus.CATALOGUED,
        notes="Catalogado; conector tabular futuro.",
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
