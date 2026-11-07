"""Conector prototype ANEEL — SIGA empreendimentos de geração (CSV).

Foco: download HTTP do recurso CKAN, parse CSV (; / aspas), filtro por UF.
Não calcula indicadores energéticos nem aptidão solar.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx

from geoai.connectors.contracts import IngestResult
from geoai.connectors.errors import ValidationConnectorError
from geoai.connectors.http_fetch import download_http_file

ANEEL_SIGA_SOURCE_ID = "aneel.siga.empreendimentos_geracao"
ANEEL_SIGA_CSV_URL = (
    "https://dadosabertos.aneel.gov.br/dataset/"
    "6d90b77c-c5f5-4d81-bdec-7bc619494bb9/resource/"
    "11ec447d-698d-4ab8-977f-b424d5deee6a/download/"
    "siga-empreendimentos-geracao.csv"
)
ANEEL_LICENSE_NOTE = (
    "ODbL — Open Data Commons Open Database License (ANEEL Dados Abertos)."
)

REQUIRED_SIGA_FIELDS: tuple[str, ...] = (
    "NomEmpreendimento",
    "CodCEG",
    "SigUFPrincipal",
    "SigTipoGeracao",
    "MdaPotenciaOutorgadaKw",
)


def _decode_csv_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationConnectorError("não foi possível decodificar CSV ANEEL SIGA")


def parse_siga_csv(
    text: str,
    *,
    uf: str | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    """Parseia o CSV SIGA (delimiter ';')."""

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValidationConnectorError("CSV SIGA sem cabeçalho")
    missing = [f for f in REQUIRED_SIGA_FIELDS if f not in reader.fieldnames]
    if missing:
        raise ValidationConnectorError(f"CSV SIGA sem campos: {missing}")

    rows: list[dict[str, str]] = []
    uf_norm = uf.upper() if uf else None
    for row in reader:
        cleaned = {k: (v or "").strip() for k, v in row.items() if k is not None}
        if uf_norm and cleaned.get("SigUFPrincipal", "").upper() != uf_norm:
            continue
        rows.append(cleaned)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def parse_siga_file(
    path: Path,
    *,
    uf: str | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    payload = Path(path).read_bytes()
    return parse_siga_csv(_decode_csv_bytes(payload), uf=uf, limit=limit)


def download_siga_csv(
    destination: Path,
    *,
    url: str = ANEEL_SIGA_CSV_URL,
    timeout_s: float = 180.0,
    retries: int = 3,
    retry_backoff_s: float = 0.5,
    use_cache: bool = True,
    client: httpx.Client | None = None,
) -> IngestResult:
    """Baixa o CSV SIGA para ``destination`` com proveniência/cache."""

    provenance = download_http_file(
        url,
        destination,
        source_id=ANEEL_SIGA_SOURCE_ID,
        license_note=ANEEL_LICENSE_NOTE,
        timeout_s=timeout_s,
        retries=retries,
        retry_backoff_s=retry_backoff_s,
        use_cache=use_cache,
        client=client,
        extra={"format": "csv", "delimiter": ";"},
    )
    # Validação leve: cabeçalho presente (não carrega o arquivo inteiro em memória
    # além do necessário — lê só o início).
    with Path(destination).open("rb") as handle:
        head = handle.read(4096)
    text_head = _decode_csv_bytes(head)
    first_line = text_head.splitlines()[0] if text_head else ""
    if "SigUFPrincipal" not in first_line:
        raise ValidationConnectorError(
            "CSV baixado não parece SIGA (faltou SigUFPrincipal no cabeçalho)"
        )
    return IngestResult(
        source_id=ANEEL_SIGA_SOURCE_ID,
        local_path=str(Path(destination).resolve()),
        provenance=provenance,
        records_parsed=None,
        warnings=(),
    )
