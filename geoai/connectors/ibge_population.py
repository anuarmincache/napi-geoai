"""Conector IBGE — Estimativas da população residente (municípios)."""

from __future__ import annotations

from pathlib import Path

from geoai.connectors.contracts import IngestResult
from geoai.connectors.http_fetch import download_http_file

IBGE_POP_SOURCE_ID = "ibge.estimativas_populacao.municipios_2026"
IBGE_POP_PRODUCT = "Estimativas da população residente — municípios 2026"
IBGE_POP_ENTRY_URL = (
    "https://www.ibge.gov.br/estatisticas/sociais/populacao/"
    "9103-estimativas-de-populacao.html"
)
IBGE_POP_FTP_INDEX = (
    "https://ftp.ibge.gov.br/Estimativas_de_Populacao/Estimativas_2026/"
)
# Edição oficial mais recente identificada em 11/11/2026 (FTP).
IBGE_POP_FILENAME = "POP2026_20261029.xlsx"
IBGE_POP_DOWNLOAD_URL = IBGE_POP_FTP_INDEX + IBGE_POP_FILENAME
IBGE_POP_REFERENCE_DATE = "2026-07-01"
IBGE_POP_EDITION_ID = "POP2026_20261029"
IBGE_POP_LICENSE_NOTE = (
    "IBGE — Estimativas da população residente; citar fonte e edição. "
    "Não confundir com população do Censo Demográfico."
)
EXPECTED_PR_POPULATION_UF_TOTAL = 11_952_456


def default_population_xlsx_path(raw_dir: Path) -> Path:
    return raw_dir / IBGE_POP_FILENAME


def download_population_xlsx(
    destination: Path,
    *,
    timeout_s: float = 120.0,
    force_refresh: bool = False,
) -> IngestResult:
    """Baixa a planilha oficial XLSX (cache HTTP com SHA)."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    provenance = download_http_file(
        IBGE_POP_DOWNLOAD_URL,
        destination,
        source_id=IBGE_POP_SOURCE_ID,
        license_note=IBGE_POP_LICENSE_NOTE,
        timeout_s=timeout_s,
        force_refresh=force_refresh,
        extra={
            "product": IBGE_POP_PRODUCT,
            "entry_url": IBGE_POP_ENTRY_URL,
            "ftp_index": IBGE_POP_FTP_INDEX,
            "edition_id": IBGE_POP_EDITION_ID,
            "reference_date": IBGE_POP_REFERENCE_DATE,
            "filename": IBGE_POP_FILENAME,
        },
    )
    return IngestResult(
        source_id=IBGE_POP_SOURCE_ID,
        local_path=str(destination),
        provenance=provenance,
    )
