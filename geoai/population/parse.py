"""Parse e validação da planilha IBGE de estimativas populacionais."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geoai.connectors.errors import ValidationConnectorError
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.connectors.ibge_population import (
    EXPECTED_PR_POPULATION_UF_TOTAL,
    IBGE_POP_EDITION_ID,
    IBGE_POP_REFERENCE_DATE,
)

SHEET_MUNICIPIOS = "MUNICÍPIOS"
SHEET_UF = "BRASIL E UFS"


def _require_openpyxl() -> None:
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "openpyxl é necessário para ler XLSX IBGE: pip install openpyxl"
        ) from exc


def parse_population_int(value: Any) -> int | None:
    """Converte célula de população em inteiro ≥ 0; None se inválida."""

    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if value != value or value < 0 or value != int(value):
            return None
        return int(value)
    text = str(value).strip().replace(".", "").replace(" ", "")
    if not text:
        return None
    # Remove marcações de nota (1), (2) etc. se coladas no número.
    if text.endswith(")") and "(" in text:
        text = text[: text.rfind("(")].strip()
    try:
        num = int(text)
    except ValueError:
        return None
    return num if num >= 0 else None


def read_uf_population_total(
    xlsx_path: Path,
    *,
    uf_name: str = "Paraná",
) -> int | None:
    """Lê total UF na aba BRASIL E UFS (quando disponível)."""

    _require_openpyxl()
    import pandas as pd

    frame = pd.read_excel(xlsx_path, sheet_name=SHEET_UF, header=None, dtype=object)
    target = uf_name.casefold()
    for _, row in frame.iterrows():
        label = str(row.iloc[0] or "").strip()
        if label.casefold() == target:
            return parse_population_int(row.iloc[1])
    return None


def parse_municipality_populations(
    xlsx_path: Path,
    *,
    uf: str = "PR",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extrai municípios da UF com CD_MUN de 7 dígitos.

    Retorna (registros, qualidade parcial). Fail-closed se UF ≠ 399 únicos
    ou população inválida.
    """

    _require_openpyxl()
    import pandas as pd

    path = Path(xlsx_path)
    if not path.is_file():
        raise ValidationConnectorError(f"XLSX populacional ausente: {path}")

    raw = pd.read_excel(
        path,
        sheet_name=SHEET_MUNICIPIOS,
        header=1,
        dtype=str,
    )
    if raw.empty:
        raise ValidationConnectorError("Aba MUNICÍPIOS vazia")
    cols = {str(c).strip(): c for c in raw.columns}
    required = [
        "UF",
        "COD. UF",
        "COD. MUNIC",
        "NOME DO MUNICÍPIO",
        "POPULAÇÃO ESTIMADA",
    ]
    missing = [name for name in required if name not in cols]
    if missing:
        raise ValidationConnectorError(
            f"Colunas ausentes na planilha populacional: {missing}"
        )

    uf_norm = uf.upper().strip()
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()

    for idx, row in raw.iterrows():
        row_uf = str(row[cols["UF"]] or "").strip().upper()
        if row_uf != uf_norm:
            continue
        cod_uf = str(row[cols["COD. UF"]] or "").strip().zfill(2)
        cod_mun = str(row[cols["COD. MUNIC"]] or "").strip().zfill(5)
        name = str(row[cols["NOME DO MUNICÍPIO"]] or "").strip()
        pop = parse_population_int(row[cols["POPULAÇÃO ESTIMADA"]])
        cd_mun = f"{cod_uf}{cod_mun}"
        if len(cd_mun) != 7 or not cd_mun.isdigit():
            errors.append(f"linha {idx}: CD_MUN inválido {cd_mun!r}")
            continue
        if cd_mun in seen:
            errors.append(f"linha {idx}: CD_MUN duplicado {cd_mun}")
            continue
        if pop is None:
            errors.append(f"linha {idx} ({cd_mun}): população inválida")
            continue
        seen.add(cd_mun)
        records.append(
            {
                "CD_MUN": cd_mun,
                "NM_MUN_IBGE_POP": name,
                "populacao_estimada_2026_hab": pop,
                "uf": row_uf,
            }
        )

    if errors:
        raise ValidationConnectorError(
            "Falhas no parse populacional: " + "; ".join(errors[:8])
        )
    if len(records) != EXPECTED_PR_MUNICIPALITY_COUNT:
        raise ValidationConnectorError(
            f"Esperado {EXPECTED_PR_MUNICIPALITY_COUNT} municípios {uf_norm}; "
            f"obtido {len(records)}"
        )

    uf_total = read_uf_population_total(path)
    mun_sum = sum(int(r["populacao_estimada_2026_hab"]) for r in records)
    quality = {
        "edition_id": IBGE_POP_EDITION_ID,
        "reference_date": IBGE_POP_REFERENCE_DATE,
        "uf": uf_norm,
        "municipality_count": len(records),
        "population_sum_municipalities": mun_sum,
        "population_uf_sheet": uf_total,
        "population_uf_expected": EXPECTED_PR_POPULATION_UF_TOTAL,
        "uf_total_matches_municipal_sum": uf_total == mun_sum if uf_total else False,
        "uf_total_matches_expected": uf_total == EXPECTED_PR_POPULATION_UF_TOTAL
        if uf_total
        else False,
    }
    if uf_total is not None and uf_total != mun_sum:
        raise ValidationConnectorError(
            f"Soma municipal PR ({mun_sum}) ≠ total UF na planilha ({uf_total})"
        )
    if uf_total is not None and uf_total != EXPECTED_PR_POPULATION_UF_TOTAL:
        raise ValidationConnectorError(
            f"Total UF PR ({uf_total}) ≠ esperado "
            f"{EXPECTED_PR_POPULATION_UF_TOTAL}"
        )
    return records, quality


def assert_codes_match_mesh(
    population_records: list[dict[str, Any]],
    mesh_codes: set[str],
) -> None:
    """Fail-closed: conjuntos CD_MUN população ↔ malha devem coincidir."""

    pop_codes = {str(r["CD_MUN"]) for r in population_records}
    if pop_codes != mesh_codes:
        only_pop = sorted(pop_codes - mesh_codes)
        only_mesh = sorted(mesh_codes - pop_codes)
        raise ValidationConnectorError(
            "Conjuntos CD_MUN divergentes população×malha: "
            f"só_pop={only_pop[:5]} só_malha={only_mesh[:5]}"
        )
