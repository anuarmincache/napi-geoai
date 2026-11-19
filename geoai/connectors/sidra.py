"""Conector IBGE/SIDRA — PAM (tabela 5457) e PPM (tabelas 3939 e 74).

Nenhum código de variável ou de categoria é fixado de memória: os
identificadores são resolvidos pelo **nome** nos metadados oficiais do
agregado (``servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados``).
Se um nome esperado não existir, ou existir mais de uma vez, a resolução
falha (fail-closed) em vez de escolher um código por aproximação.

Símbolos da coluna de valor (convenção IBGE):

- ``-``   zero absoluto, não resultante de arredondamento → zero verdadeiro
- ``..``  não se aplica dado numérico
- ``...`` dado numérico não disponível
- ``X``   dado omitido para evitar identificação do informante (sigilo)

Somente o primeiro vira número. Os demais permanecem sem valor.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

SIDRA_VALUES_BASE = "https://apisidra.ibge.gov.br/values"
SIDRA_METADATA_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"
SIDRA_LICENSE_NOTE = (
    "IBGE — SIDRA. Uso livre com citação da fonte (IBGE, pesquisa, tabela e "
    "ano de referência)."
)
PR_UF_CODE = "41"

PAM_TABLE = 5457
PPM_HERD_TABLE = 3939
PPM_ANIMAL_PRODUCT_TABLE = 74

SIDRA_PAM_SOURCE_ID = "ibge.sidra.pam.tabela_5457"
SIDRA_PPM_HERD_SOURCE_ID = "ibge.sidra.ppm.tabela_3939"
SIDRA_PPM_PRODUCT_SOURCE_ID = "ibge.sidra.ppm.tabela_74"

STATUS_VALUE = "valor"
STATUS_ZERO = "zero"
STATUS_NOT_APPLICABLE = "nao_se_aplica"
STATUS_UNAVAILABLE = "indisponivel"
STATUS_SUPPRESSED = "sigilo"

_SYMBOLS = {
    "-": STATUS_ZERO,
    "..": STATUS_NOT_APPLICABLE,
    "...": STATUS_UNAVAILABLE,
    "X": STATUS_SUPPRESSED,
    "x": STATUS_SUPPRESSED,
}


class SidraError(ValueError):
    """Resposta ou metadado SIDRA fora do contrato esperado."""


def normalize_name(text: str) -> str:
    plain = unicodedata.normalize("NFKD", str(text))
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return " ".join(plain.casefold().split())


def parse_sidra_value(raw: Any) -> tuple[float | None, str]:
    """Converte a coluna ``V``. Símbolo desconhecido levanta ``SidraError``."""

    text = str(raw if raw is not None else "").strip()
    if text in _SYMBOLS:
        status = _SYMBOLS[text]
        return (0.0 if status == STATUS_ZERO else None), status
    if not text:
        raise SidraError("valor vazio na coluna V")
    try:
        return float(text), STATUS_VALUE
    except ValueError as exc:
        raise SidraError(f"valor não numérico e não reconhecido: {text!r}") from exc


def metadata_url(table: int) -> str:
    return f"{SIDRA_METADATA_BASE}/{int(table)}/metadados"


def values_url(
    table: int,
    variable_id: int,
    *,
    classification_id: int | None = None,
    category_ids: tuple[int, ...] | None = None,
    period: str = "last 1",
) -> str:
    """URL de valores para os municípios do Paraná (n6 dentro de n3 41)."""

    parts = [
        SIDRA_VALUES_BASE,
        "t",
        str(int(table)),
        "n6",
        f"in%20n3%20{PR_UF_CODE}",
        "v",
        str(int(variable_id)),
        "p",
        period.replace(" ", "%20"),
    ]
    if classification_id is not None:
        cats = (
            ",".join(str(int(c)) for c in category_ids) if category_ids else "all"
        )
        parts += [f"c{int(classification_id)}", cats]
    return "/".join(parts)


@dataclass(frozen=True, slots=True)
class SidraItem:
    """Variável ou categoria resolvida nos metadados oficiais."""

    item_id: int
    name: str
    unit: str | None = None


def _unique_match(
    items: list[dict[str, Any]], wanted: str, *, kind: str, prefix: bool
) -> dict[str, Any]:
    target = normalize_name(wanted)
    hits = [
        item
        for item in items
        if (
            normalize_name(item.get("nome", "")).startswith(target)
            if prefix
            else normalize_name(item.get("nome", "")) == target
        )
    ]
    if len(hits) != 1:
        names = [str(item.get("nome")) for item in hits]
        raise SidraError(
            f"{kind} «{wanted}»: esperado 1 correspondência nos metadados, "
            f"encontradas {len(hits)} {names}"
        )
    return hits[0]


def resolve_variable(
    metadata: dict[str, Any], name: str, *, prefix: bool = False
) -> SidraItem:
    variables = [
        v
        for v in (metadata.get("variaveis") or [])
        if "percentual" not in normalize_name(v.get("nome", ""))
    ]
    hit = _unique_match(variables, name, kind="variável", prefix=prefix)
    return SidraItem(int(hit["id"]), str(hit["nome"]), hit.get("unidade"))


def resolve_classification(
    metadata: dict[str, Any], name_prefix: str
) -> dict[str, Any]:
    return _unique_match(
        list(metadata.get("classificacoes") or []),
        name_prefix,
        kind="classificação",
        prefix=True,
    )


def resolve_category(classification: dict[str, Any], name: str) -> SidraItem:
    hit = _unique_match(
        list(classification.get("categorias") or []),
        name,
        kind="categoria",
        prefix=False,
    )
    return SidraItem(int(hit["id"]), str(hit["nome"]), hit.get("unidade"))


@dataclass(frozen=True, slots=True)
class SidraRecord:
    municipality_code: str
    municipality_name: str
    variable_id: str
    variable_name: str
    unit: str
    period: str
    category_id: str | None
    category_name: str | None
    value: float | None
    status: str


def _column(header: dict[str, Any], label: str) -> str:
    target = normalize_name(label)
    hits = [k for k, v in header.items() if normalize_name(v) == target]
    if len(hits) != 1:
        raise SidraError(f"coluna «{label}» ausente ou ambígua no cabeçalho SIDRA")
    return hits[0]


def parse_sidra_values(
    payload: Any, *, classification_name: str | None = None
) -> list[SidraRecord]:
    """Lê a resposta ``/values``: a primeira linha é o cabeçalho descritivo."""

    if not isinstance(payload, list) or len(payload) < 2:
        raise SidraError("resposta SIDRA sem linhas de dados")
    header = payload[0]
    if not isinstance(header, dict):
        raise SidraError("cabeçalho SIDRA inválido")
    c_mun = _column(header, "Município (Código)")
    n_mun = _column(header, "Município")
    c_var = _column(header, "Variável (Código)")
    n_var = _column(header, "Variável")
    c_per = _column(header, "Ano (Código)")
    n_unit = _column(header, "Unidade de Medida")
    c_val = _column(header, "Valor")
    c_cat = n_cat = None
    if classification_name is not None:
        c_cat = _column(header, f"{classification_name} (Código)")
        n_cat = _column(header, classification_name)

    records: list[SidraRecord] = []
    for row in payload[1:]:
        value, status = parse_sidra_value(row.get(c_val))
        records.append(
            SidraRecord(
                municipality_code=str(row[c_mun]).strip(),
                municipality_name=str(row[n_mun]).strip(),
                variable_id=str(row[c_var]).strip(),
                variable_name=str(row[n_var]).strip(),
                unit=str(row[n_unit]).strip(),
                period=str(row[c_per]).strip(),
                category_id=str(row[c_cat]).strip() if c_cat else None,
                category_name=str(row[n_cat]).strip() if n_cat else None,
                value=value,
                status=status,
            )
        )
    return records
