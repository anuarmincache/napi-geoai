"""Conector mínimo para malhas territoriais do IBGE (UF Paraná).

Reutiliza o download HTTP compartilhado (retries/cache/checksum).
Não interpreta aptidão energética nem indicadores derivados.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from geoai.connectors.http_fetch import download_http_file

IBGE_PR_UF_2025_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/PR_UF_2025.zip"
)

IBGE_PR_MUNICIPIOS_2025_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/"
    "PR_Municipios_2025.zip"
)

IBGE_LICENSE_NOTE = (
    "Arquivos públicos do IBGE/Geociências (geoftp). Uso sujeito às condições "
    "institucionais do IBGE; citar a origem e a edição da malha."
)

EXPECTED_SOURCE_CRS = "EPSG:4674"
IBGE_SOURCE_ID = "ibge.malhas_municipais.pr_uf_2025"
IBGE_MUNICIPIOS_SOURCE_ID = "ibge.malhas_municipais.pr_municipios_2025"
EXPECTED_PR_MUNICIPALITY_COUNT = 399


@dataclass(frozen=True, slots=True)
class IbgeMalhaSource:
    """Metadados de proveniência de uma malha IBGE (compatível com MVP 02)."""

    name: str
    url: str
    edition: str
    territory: str
    license_note: str
    expected_crs: str
    retrieved_at: str
    content_sha256: str
    content_length: int
    http_etag: str | None
    http_last_modified: str | None
    local_zip: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


IBGE_PR_UF_2025 = IbgeMalhaSource(
    name="PR_UF_2025",
    url=IBGE_PR_UF_2025_URL,
    edition="municipio_2025",
    territory="Paraná (UF)",
    license_note=IBGE_LICENSE_NOTE,
    expected_crs=EXPECTED_SOURCE_CRS,
    retrieved_at="",
    content_sha256="",
    content_length=0,
    http_etag=None,
    http_last_modified=None,
    local_zip="",
)


def _territory_label(url: str) -> str:
    upper = url.upper()
    if "PR_MUNICIPIOS" in upper:
        return "Paraná (municípios)"
    if "PR_UF" in upper:
        return "Paraná (UF)"
    return "unknown"


def download_ibge_zip(
    url: str,
    destination: Path,
    *,
    timeout_s: float = 120.0,
    client: httpx.Client | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
    cache_ttl_s: float | None = 604_800.0,
    retries: int = 3,
    source_id: str | None = None,
) -> IbgeMalhaSource:
    """Baixa um ZIP do geoftp.ibge.gov.br e grava metadados de proveniência.

    Mantém a API do MVP 02; cache agora distingue integridade de atualidade.
    """

    resolved_source = source_id or (
        IBGE_MUNICIPIOS_SOURCE_ID
        if "PR_Municipios" in url
        else IBGE_SOURCE_ID
    )
    provenance = download_http_file(
        url,
        destination,
        source_id=resolved_source,
        license_note=IBGE_LICENSE_NOTE,
        timeout_s=timeout_s,
        retries=retries,
        use_cache=use_cache,
        force_refresh=force_refresh,
        cache_ttl_s=cache_ttl_s,
        client=client,
        extra={"expected_crs": EXPECTED_SOURCE_CRS},
    )
    filename = Path(urlparse(url).path).stem or "ibge_malha"
    return IbgeMalhaSource(
        name=filename,
        url=url,
        edition="municipio_2025" if "municipio_2025" in url else "unknown",
        territory=_territory_label(url),
        license_note=IBGE_LICENSE_NOTE,
        expected_crs=EXPECTED_SOURCE_CRS,
        retrieved_at=provenance.retrieved_at,
        content_sha256=provenance.content_sha256,
        content_length=provenance.content_length,
        http_etag=provenance.http_etag,
        http_last_modified=provenance.http_last_modified,
        local_zip=str(Path(destination).resolve()),
    )


def write_provenance(source: IbgeMalhaSource, path: Path) -> Path:
    """Persiste proveniência em JSON UTF-8."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(source.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
