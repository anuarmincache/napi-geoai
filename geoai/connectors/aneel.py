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
    "ODbL — Open Data Commons Open Database License (ANEEL Dados Abertos). "
    "Redistribuição/derivação sujeitas aos termos ODbL (manter atribuição e "
    "share-alike quando aplicável)."
)

REQUIRED_SIGA_FIELDS: tuple[str, ...] = (
    "DatGeracaoConjuntoDados",
    "NomEmpreendimento",
    "IdeNucleoCEG",
    "CodCEG",
    "SigUFPrincipal",
    "SigTipoGeracao",
    "DscFaseUsina",
    "DscOrigemCombustivel",
    "DscFonteCombustivel",
    "MdaPotenciaOutorgadaKw",
    "NumCoordNEmpreendimento",
    "NumCoordEEmpreendimento",
)

SIGA_DELIMITER = ";"


def _decode_csv_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationConnectorError("não foi possível decodificar CSV ANEEL SIGA")


def _read_header_fields(text: str) -> list[str]:
    first = text.splitlines()[0] if text else ""
    if not first.strip():
        raise ValidationConnectorError("CSV SIGA sem cabeçalho")
    reader = csv.reader(io.StringIO(first), delimiter=SIGA_DELIMITER)
    try:
        fields = next(reader)
    except StopIteration as exc:
        raise ValidationConnectorError("CSV SIGA sem cabeçalho") from exc
    return [f.strip() for f in fields]


def validate_siga_csv_file(path: Path) -> list[str]:
    """Valida encoding, delimitador e conjunto de colunas obrigatórias.

    Usado antes de promover o artefato ao destino/cache.
    """

    path = Path(path)
    # Cabeçalho cabe em poucos KB; evita carregar CSV completo.
    with path.open("rb") as handle:
        head = handle.read(65536)
    if b"\x00" in head[:1024]:
        raise ValidationConnectorError("CSV SIGA parece binário/inválido")
    text = _decode_csv_bytes(head)
    if SIGA_DELIMITER not in text.splitlines()[0]:
        raise ValidationConnectorError(
            f"CSV SIGA: delimitador esperado '{SIGA_DELIMITER}' ausente no cabeçalho"
        )
    fields = _read_header_fields(text)
    missing = [f for f in REQUIRED_SIGA_FIELDS if f not in fields]
    if missing:
        raise ValidationConnectorError(f"CSV SIGA sem campos: {missing}")
    return fields


def parse_siga_csv(
    text: str,
    *,
    uf: str | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    """Parseia o CSV SIGA (delimiter ';').

    ``limit``: ``None`` = sem limite; ``0`` = lista vazia; ``<0`` = erro.
    """

    if limit is not None and limit < 0:
        raise ValidationConnectorError("limit não pode ser negativo")
    if limit == 0:
        # Ainda valida o cabeçalho.
        missing_check = csv.DictReader(io.StringIO(text), delimiter=SIGA_DELIMITER)
        if not missing_check.fieldnames:
            raise ValidationConnectorError("CSV SIGA sem cabeçalho")
        missing = [
            f for f in REQUIRED_SIGA_FIELDS if f not in missing_check.fieldnames
        ]
        if missing:
            raise ValidationConnectorError(f"CSV SIGA sem campos: {missing}")
        return []

    reader = csv.DictReader(io.StringIO(text), delimiter=SIGA_DELIMITER)
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
    validate_siga_csv_file(path)
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
    force_refresh: bool = False,
    cache_ttl_s: float | None = 86_400.0,
    client: httpx.Client | None = None,
) -> IngestResult:
    """Baixa o CSV SIGA com validação de cabeçalho antes do cache."""

    provenance = download_http_file(
        url,
        destination,
        source_id=ANEEL_SIGA_SOURCE_ID,
        license_note=ANEEL_LICENSE_NOTE,
        timeout_s=timeout_s,
        retries=retries,
        retry_backoff_s=retry_backoff_s,
        use_cache=use_cache,
        force_refresh=force_refresh,
        cache_ttl_s=cache_ttl_s,
        content_validator=validate_siga_csv_file,
        client=client,
        extra={"format": "csv", "delimiter": SIGA_DELIMITER},
    )
    # Revalidar destino final (inclui cache hit de arquivo previamente inválido
    # se metadados estiverem inconsistentes).
    validate_siga_csv_file(Path(destination))
    return IngestResult(
        source_id=ANEEL_SIGA_SOURCE_ID,
        local_path=str(Path(destination).resolve()),
        provenance=provenance,
        records_parsed=None,
        warnings=(),
    )
