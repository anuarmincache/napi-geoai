"""Normalização de registros SIGA (decimais pt-BR, coords, fases)."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

# Lat/lon geográficas aproximadas WGS84/SIRGAS (ANEEL). Não inventar centróides.
_COORD_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def parse_br_decimal(value: str | float | int | None) -> float | None:
    """Converte número com vírgula decimal (pt-BR) em float finito."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) else None
    text = str(value).strip()
    if not text or text in {".", ",", "-", ",00"}:
        return None
    text = text.replace(" ", "").replace(".", "").replace(",", ".")
    # Caso já venha com ponto decimal sem milhar: "10000.00"
    if text.count(".") > 1:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    return num if math.isfinite(num) else None


def parse_coord_pair(
    lat_raw: str | None,
    lon_raw: str | None,
) -> tuple[float, float] | None:
    """Retorna (lon, lat) se válidos para o território brasileiro aproximado."""

    if lat_raw is None or lon_raw is None:
        return None
    lat_s = str(lat_raw).strip()
    lon_s = str(lon_raw).strip()
    if not (_COORD_RE.match(lat_s) and _COORD_RE.match(lon_s)):
        return None
    try:
        lat = float(lat_s.replace(",", "."))
        lon = float(lon_s.replace(",", "."))
    except ValueError:
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    # Bounding box folgado do Brasil (+ margem); rejeita (0,0).
    if not (-35.0 <= lat <= 6.0 and -75.0 <= lon <= -28.0):
        return None
    if abs(lat) < 1e-6 and abs(lon) < 1e-6:
        return None
    return (lon, lat)


@dataclass(frozen=True, slots=True)
class NormalizedPlant:
    cod_ceg: str
    name: str
    uf: str
    phase: str
    tipo_geracao: str
    origem_combustivel: str
    potencia_outorgada_kw: float | None
    potencia_fiscalizada_kw: float | None
    lon: float | None
    lat: float | None
    municipios_declarados: str
    dat_conjunto: str
    coord_ok: bool
    reject_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_siga_rows(
    rows: list[dict[str, str]],
    *,
    uf: str = "PR",
) -> tuple[list[NormalizedPlant], list[NormalizedPlant]]:
    """Normaliza linhas já filtradas (ou não). Retorna (aceitas, rejeitadas)."""

    accepted: list[NormalizedPlant] = []
    rejected: list[NormalizedPlant] = []
    seen: set[str] = set()
    uf_norm = uf.upper()

    for row in rows:
        code = (row.get("CodCEG") or "").strip()
        uf_row = (row.get("SigUFPrincipal") or "").strip().upper()
        name = (row.get("NomEmpreendimento") or "").strip()
        phase = (row.get("DscFaseUsina") or "").strip()
        tipo = (row.get("SigTipoGeracao") or "").strip()
        origem = (row.get("DscOrigemCombustivel") or "").strip()
        mun = (row.get("DscMuninicpios") or "").strip()
        dat = (row.get("DatGeracaoConjuntoDados") or "").strip()
        out_kw = parse_br_decimal(row.get("MdaPotenciaOutorgadaKw"))
        fis_kw = parse_br_decimal(row.get("MdaPotenciaFiscalizadaKw"))
        pair = parse_coord_pair(
            row.get("NumCoordNEmpreendimento"),
            row.get("NumCoordEEmpreendimento"),
        )
        lon = pair[0] if pair else None
        lat = pair[1] if pair else None
        coord_ok = pair is not None

        reason: str | None = None
        if not code:
            reason = "CodCEG ausente"
        elif code in seen:
            reason = "CodCEG duplicado na carga"
        elif uf_row != uf_norm:
            reason = f"UF {uf_row!r} != {uf_norm}"
        elif out_kw is None and fis_kw is None:
            reason = "potências outorgada e fiscalizada ausentes/inválidas"

        plant = NormalizedPlant(
            cod_ceg=code or "(sem-ceg)",
            name=name,
            uf=uf_row,
            phase=phase,
            tipo_geracao=tipo,
            origem_combustivel=origem,
            potencia_outorgada_kw=out_kw,
            potencia_fiscalizada_kw=fis_kw,
            lon=lon,
            lat=lat,
            municipios_declarados=mun,
            dat_conjunto=dat,
            coord_ok=coord_ok,
            reject_reason=reason,
        )
        if reason:
            rejected.append(plant)
            continue
        seen.add(code)
        accepted.append(plant)

    return accepted, rejected
