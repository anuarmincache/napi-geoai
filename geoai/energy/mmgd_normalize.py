"""Normalização de registros MMGD (sem campos pessoais)."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from geoai.energy.siga_normalize import parse_br_decimal

_IBGE_RE = re.compile(r"^\d{7}$")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def parse_nonneg_int(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not math.isfinite(value) or value < 0 or not value.is_integer():
            return None
        return int(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    try:
        num = float(text)
    except ValueError:
        return None
    if not math.isfinite(num) or num < 0 or not float(num).is_integer():
        return None
    return int(num)


def extract_year(value: str | None) -> int | None:
    """Extrai ano de um carimbo textual. Não afirma que seja data de conexão."""

    if not value:
        return None
    match = _YEAR_RE.search(str(value))
    if not match:
        return None
    year = int(match.group(0))
    if 1990 <= year <= 2100:
        return year
    return None


@dataclass(frozen=True, slots=True)
class NormalizedMmgdPlant:
    """Um empreendimento MMGD. Contagem primária = 1 empreendimento."""

    cod_empreendimento: str
    uf: str
    cd_mun: str | None
    municipio_nome: str
    tipo_geracao: str
    fonte_geracao: str
    porte: str
    classe_consumo: str
    potencia_instalada_kw: float | None
    qtd_uc_recebe_credito: int | None
    dat_conjunto: str
    periodo_referencia: str
    cadastral_update_at: str
    cadastral_update_year: int | None
    reject_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_mmgd_row(row: dict[str, str]) -> NormalizedMmgdPlant:
    code = (row.get("CodEmpreendimento") or "").strip()
    uf = (row.get("SigUF") or "").strip().upper()
    ibge = (row.get("CodMunicipioIbge") or "").strip()
    cd_mun = ibge if _IBGE_RE.match(ibge) else None
    pot = parse_br_decimal(row.get("MdaPotenciaInstaladaKW"))
    qtd = parse_nonneg_int(row.get("QtdUCRecebeCredito"))
    cadastral = (row.get("DthAtualizaCadastralEmpreend") or "").strip()
    reason: str | None = None
    if not code:
        reason = "CodEmpreendimento ausente"
    elif uf != "PR":
        reason = "UF diferente de PR"
    elif cd_mun is None:
        reason = "CodMunicipioIbge inválido"
    elif not cd_mun.startswith("41"):
        reason = "CodMunicipioIbge fora do Paraná (prefixo 41)"
    elif pot is None or pot < 0:
        reason = "MdaPotenciaInstaladaKW inválida"
    return NormalizedMmgdPlant(
        cod_empreendimento=code,
        uf=uf,
        cd_mun=cd_mun if reason is None else cd_mun,
        municipio_nome=(row.get("NomMunicipio") or "").strip(),
        tipo_geracao=(row.get("SigTipoGeracao") or "").strip(),
        fonte_geracao=(row.get("DscFonteGeracao") or "").strip(),
        porte=(row.get("DscPorte") or "").strip(),
        classe_consumo=(row.get("DscClasseConsumo") or "").strip(),
        potencia_instalada_kw=pot,
        qtd_uc_recebe_credito=qtd,
        dat_conjunto=(row.get("DatGeracaoConjuntoDados") or "").strip(),
        periodo_referencia=(row.get("AnmPeriodoReferencia") or "").strip(),
        cadastral_update_at=cadastral,
        cadastral_update_year=extract_year(cadastral),
        reject_reason=reason,
    )
