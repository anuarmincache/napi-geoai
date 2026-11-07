"""Conector mínimo para malhas territoriais do IBGE (UF Paraná).

Baixa o ZIP oficial, calcula checksum e registra proveniência.
Não interpreta aptidão energética nem indicadores derivados.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Malha Municipal 2025 — Unidades da Federação do Paraná (IBGE/Geociências).
# Índice: https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/
IBGE_PR_UF_2025_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2025/UFs/PR/PR_UF_2025.zip"
)

# IBGE declara os arquivos do geoftp como públicos; atribuição à fonte é obrigatória
# para rastreabilidade científica do projeto (não há SPDX IBGE-específico aqui).
IBGE_LICENSE_NOTE = (
    "Arquivos públicos do IBGE/Geociências (geoftp). Uso sujeito às condições "
    "institucionais do IBGE; citar a origem e a edição da malha."
)

EXPECTED_SOURCE_CRS = "EPSG:4674"  # SIRGAS 2000 (geográfico)


@dataclass(frozen=True, slots=True)
class IbgeMalhaSource:
    """Metadados de proveniência de uma malha IBGE."""

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_ibge_zip(
    url: str,
    destination: Path,
    *,
    timeout_s: float = 120.0,
    client: httpx.Client | None = None,
) -> IbgeMalhaSource:
    """Baixa um ZIP do geoftp.ibge.gov.br e grava metadados de proveniência."""

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    owns_client = client is None
    http = client or httpx.Client(follow_redirects=True, timeout=timeout_s)
    try:
        with http.stream("GET", url) as response:
            response.raise_for_status()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    finally:
        if owns_client:
            http.close()

    sha256 = _sha256_file(destination)
    size = destination.stat().st_size
    filename = Path(urlparse(url).path).stem or "ibge_malha"

    return IbgeMalhaSource(
        name=filename,
        url=url,
        edition="municipio_2025" if "municipio_2025" in url else "unknown",
        territory="Paraná (UF)" if "PR_UF" in url.upper() else "unknown",
        license_note=IBGE_LICENSE_NOTE,
        expected_crs=EXPECTED_SOURCE_CRS,
        retrieved_at=datetime.now(UTC).isoformat(),
        content_sha256=sha256,
        content_length=size,
        http_etag=etag,
        http_last_modified=last_modified,
        local_zip=str(destination.resolve()),
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
