"""Conector ANEEL MMGD — ZIP/CSV de empreendimentos de geração distribuída.

Baixa o recurso oficial, valida o cabeçalho e permite leitura em streaming.
Não calcula rentabilidade nem mistura SIGA. Campos pessoais não são
expostos pelos helpers públicos deste módulo.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import httpx

from geoai.connectors.contracts import IngestResult
from geoai.connectors.errors import ValidationConnectorError
from geoai.connectors.http_fetch import download_http_file

ANEEL_MMGD_SOURCE_ID = "aneel.mmgd.empreendimentos"
ANEEL_MMGD_ZIP_URL = (
    "https://dadosabertos.aneel.gov.br/dataset/"
    "5e0fafd2-21b9-4d5b-b622-40438d40aba2/resource/"
    "b1bd71e7-d0ad-4214-9053-cbd58e9564a7/download/"
    "empreendimento-geracao-distribuida.zip"
)
ANEEL_MMGD_LICENSE_NOTE = (
    "ODbL — Open Data Commons Open Database License (ANEEL Dados Abertos). "
    "Redistribuição/derivação sujeitas aos termos ODbL."
)
ANEEL_MMGD_CKAN_RESOURCE_ID = "b1bd71e7-d0ad-4214-9053-cbd58e9564a7"
ANEEL_MMGD_CSV_MEMBER = "empreendimento-geracao-distribuida.csv"
MMGD_DELIMITER = ";"

# Cabeçalho confirmado no ZIP oficial baixado em 2026-11-18 (Gate 2).
REQUIRED_MMGD_FIELDS: tuple[str, ...] = (
    "DatGeracaoConjuntoDados",
    "AnmPeriodoReferencia",
    "SigAgente",
    "CodClasseConsumo",
    "DscClasseConsumo",
    "CodUFibge",
    "SigUF",
    "CodMunicipioIbge",
    "NomMunicipio",
    "CodEmpreendimento",
    "DthAtualizaCadastralEmpreend",
    "QtdUCRecebeCredito",
    "SigTipoGeracao",
    "DscFonteGeracao",
    "DscPorte",
    "MdaPotenciaInstaladaKW",
)

# Não entram em artefatos públicos derivados.
PERSONAL_OR_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "NumCPFCNPJ",
        "NomTitularEmpreendimento",
        "CodCEP",
        "NumCoordESub",
        "NumCoordNSub",
    }
)

PUBLIC_FIELDS: tuple[str, ...] = (
    "DatGeracaoConjuntoDados",
    "AnmPeriodoReferencia",
    "NumCNPJDistribuidora",
    "SigAgente",
    "NomAgente",
    "CodClasseConsumo",
    "DscClasseConsumo",
    "CodSubGrupoTarifario",
    "DscSubGrupoTarifario",
    "CodUFibge",
    "SigUF",
    "CodRegiao",
    "NomRegiao",
    "CodMunicipioIbge",
    "NomMunicipio",
    "SigTipoConsumidor",
    "CodEmpreendimento",
    "DthAtualizaCadastralEmpreend",
    "SigModalidadeEmpreendimento",
    "DscModalidadeHabilitado",
    "QtdUCRecebeCredito",
    "SigTipoGeracao",
    "DscFonteGeracao",
    "DscPorte",
    "MdaPotenciaInstaladaKW",
    "NomSubEstacao",
)


def _decode_header_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationConnectorError("não foi possível decodificar cabeçalho MMGD")


def _csv_member_name(zf: zipfile.ZipFile) -> str:
    names = zf.namelist()
    if ANEEL_MMGD_CSV_MEMBER in names:
        return ANEEL_MMGD_CSV_MEMBER
    csv_names = [n for n in names if n.lower().endswith(".csv")]
    if len(csv_names) == 1:
        return csv_names[0]
    raise ValidationConnectorError(
        f"ZIP MMGD sem CSV esperado; membros={names[:5]}"
    )


def validate_mmgd_zip_file(path: Path) -> list[str]:
    """Valida ZIP e cabeçalho CSV sem carregar o arquivo inteiro na memória."""

    path = Path(path)
    if path.stat().st_size <= 0:
        raise ValidationConnectorError("ZIP MMGD vazio")
    try:
        with zipfile.ZipFile(path) as zf:
            member = _csv_member_name(zf)
            with zf.open(member) as handle:
                head = handle.read(65_536)
    except zipfile.BadZipFile as exc:
        raise ValidationConnectorError("ZIP MMGD inválido") from exc
    if b"\x00" in head[:1024]:
        raise ValidationConnectorError("CSV MMGD parece binário/inválido")
    text = _decode_header_bytes(head)
    first = text.splitlines()[0] if text else ""
    if MMGD_DELIMITER not in first:
        raise ValidationConnectorError(
            f"CSV MMGD: delimitador '{MMGD_DELIMITER}' ausente no cabeçalho"
        )
    reader = csv.reader(io.StringIO(first), delimiter=MMGD_DELIMITER)
    try:
        fields = [f.strip() for f in next(reader)]
    except StopIteration as exc:
        raise ValidationConnectorError("CSV MMGD sem cabeçalho") from exc
    missing = [f for f in REQUIRED_MMGD_FIELDS if f not in fields]
    if missing:
        raise ValidationConnectorError(f"CSV MMGD sem campos: {missing}")
    return fields


def iter_mmgd_rows(
    zip_path: Path,
    *,
    uf: str | None = None,
    public_only: bool = True,
) -> Iterator[dict[str, str]]:
    """Itera linhas do CSV dentro do ZIP. ``public_only`` omite campos sensíveis."""

    validate_mmgd_zip_file(zip_path)
    uf_norm = uf.upper() if uf else None
    with zipfile.ZipFile(zip_path) as zf:
        member = _csv_member_name(zf)
        with zf.open(member) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text, delimiter=MMGD_DELIMITER)
            if not reader.fieldnames:
                raise ValidationConnectorError("CSV MMGD sem cabeçalho")
            missing = [f for f in REQUIRED_MMGD_FIELDS if f not in reader.fieldnames]
            if missing:
                raise ValidationConnectorError(f"CSV MMGD sem campos: {missing}")
            for row in reader:
                cleaned = {
                    k: (v or "").strip()
                    for k, v in row.items()
                    if k is not None
                }
                if uf_norm and cleaned.get("SigUF", "").upper() != uf_norm:
                    continue
                if public_only:
                    yield {key: cleaned.get(key, "") for key in PUBLIC_FIELDS}
                else:
                    yield cleaned


def download_mmgd_zip(
    destination: Path,
    *,
    url: str = ANEEL_MMGD_ZIP_URL,
    timeout_s: float = 600.0,
    retries: int = 3,
    retry_backoff_s: float = 1.0,
    use_cache: bool = True,
    force_refresh: bool = False,
    cache_ttl_s: float | None = 86_400.0,
    client: httpx.Client | None = None,
) -> IngestResult:
    """Baixa o ZIP MMGD com validação de cabeçalho antes de promover o cache."""

    provenance = download_http_file(
        url,
        destination,
        source_id=ANEEL_MMGD_SOURCE_ID,
        license_note=ANEEL_MMGD_LICENSE_NOTE,
        timeout_s=timeout_s,
        retries=retries,
        retry_backoff_s=retry_backoff_s,
        use_cache=use_cache,
        force_refresh=force_refresh,
        cache_ttl_s=cache_ttl_s,
        content_validator=validate_mmgd_zip_file,
        client=client,
        extra={
            "format": "zip/csv",
            "delimiter": MMGD_DELIMITER,
            "ckan_resource_id": ANEEL_MMGD_CKAN_RESOURCE_ID,
            "csv_member": ANEEL_MMGD_CSV_MEMBER,
        },
    )
    validate_mmgd_zip_file(Path(destination))
    return IngestResult(
        source_id=ANEEL_MMGD_SOURCE_ID,
        local_path=str(Path(destination).resolve()),
        provenance=provenance,
        records_parsed=None,
        warnings=(),
    )
