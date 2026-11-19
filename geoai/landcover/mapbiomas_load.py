"""Leitura da tabela municipal MapBiomas Coleção 11 e painel do Paraná.

Estrutura confirmada no arquivo oficial em 2026-11-19: aba ``COVERAGE_11``,
layout largo, uma linha por bioma × município × classe folha, colunas
``y1985`` a ``y2025`` em hectares.

Regras:

- Hectares permanecem como publicados. Nada é reescalado para a área IBGE.
- Bioma particiona o município (cada pixel tem um bioma), então a soma das
  parcelas de bioma de um mesmo município e classe é a área da classe.
- O percentual usa a soma das classes folha como denominador (área mapeada).
- A diferença entre área mapeada e ``AREA_KM2`` do IBGE é registrada por
  município e exibida. Não é corrigida.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from pathlib import Path
from typing import Any

from geoai.landcover.mapbiomas_col11 import (
    CLASS_NAME,
    DATA_SHEET,
    DISPLAY_GROUPS,
    YEAR_MAX,
    YEAR_MIN,
    CoverageRecord,
    MapBiomasContractError,
    validate_parana_records,
)

PARANA_STATE = "Paraná"
REQUIRED_COLUMNS = ("biome", "state", "geocode", "class")
MEDIAN_DELTA_LIMIT = 0.01

GROUP_LABELS_PT: dict[str, str] = {
    "formacao_florestal": "Floresta",
    "vegetacao_herbacea_arbustiva": "Vegetação herbácea e arbustiva",
    "pastagem": "Pastagem",
    "agricultura": "Agricultura",
    "silvicultura": "Silvicultura",
    "mosaico_de_usos": "Mosaico de usos",
    "area_urbanizada": "Área urbanizada",
    "outras_nao_vegetadas": "Outras áreas não vegetadas",
    "corpo_dagua": "Corpo d'água",
}
# Cores da aba LEGEND_CODE do arquivo oficial (classe representativa do grupo).
GROUP_COLORS: dict[str, str] = {
    "formacao_florestal": "#1f8d49",
    "vegetacao_herbacea_arbustiva": "#d6bc74",
    "pastagem": "#edde8e",
    "agricultura": "#E974ED",
    "silvicultura": "#7a5900",
    "mosaico_de_usos": "#ffefc3",
    "area_urbanizada": "#d4271e",
    "outras_nao_vegetadas": "#db4d4f",
    "corpo_dagua": "#2532e4",
}
CLASS_TO_GROUP: dict[int, str] = {
    class_id: group for group, ids in DISPLAY_GROUPS.items() for class_id in ids
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_parana_records(xlsx: Path) -> tuple[list[CoverageRecord], dict[str, Any]]:
    """Lê só as linhas do Paraná. Célula vazia ou não numérica interrompe."""

    from openpyxl import load_workbook

    workbook = load_workbook(xlsx, read_only=True, data_only=True)
    try:
        if DATA_SHEET not in workbook.sheetnames:
            raise MapBiomasContractError(f"Aba {DATA_SHEET} ausente")
        rows = workbook[DATA_SHEET].iter_rows(values_only=True)
        header = [str(v) if v is not None else "" for v in next(rows)]
        index = {name: pos for pos, name in enumerate(header)}
        missing = [c for c in REQUIRED_COLUMNS if c not in index]
        if missing:
            raise MapBiomasContractError(f"Colunas ausentes: {missing}")
        years = sorted(
            int(name[1:])
            for name in header
            if len(name) == 5 and name[0] == "y" and name[1:].isdigit()
        )
        if not years or years[0] < YEAR_MIN or years[-1] > YEAR_MAX:
            raise MapBiomasContractError(f"Anos fora do contrato: {years[:1]}")
        records: list[CoverageRecord] = []
        total = pr_rows = 0
        for row in rows:
            total += 1
            if row[index["state"]] != PARANA_STATE:
                continue
            pr_rows += 1
            code = str(row[index["geocode"]]).strip()
            biome = str(row[index["biome"]]).strip()
            class_id = int(str(row[index["class"]]).strip())
            for year in years:
                raw = row[index[f"y{year}"]]
                try:
                    hectares = float(raw)
                except (TypeError, ValueError) as exc:
                    raise MapBiomasContractError(
                        f"Hectare ausente ou não numérico: {code}, classe "
                        f"{class_id}, {year}"
                    ) from exc
                records.append(
                    CoverageRecord(code, biome, "PR", class_id, year, hectares)
                )
    finally:
        workbook.close()
    return records, {
        "sheet": DATA_SHEET,
        "rows_national": total,
        "rows_parana": pr_rows,
        "years_in_file": years,
    }


def choose_panel_years(years: list[int]) -> list[int]:
    """Anos múltiplos de 5 presentes no arquivo, mais o último ano."""

    chosen = {year for year in years if year % 5 == 0}
    chosen.add(max(years))
    return sorted(chosen)


def build_landcover_panel(
    records: list[CoverageRecord],
    ibge_area_km2: dict[str, float],
    *,
    content_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Valida pelo contrato e agrega. Devolve (painel, qualidade)."""

    codes = set(ibge_area_km2)
    summary = validate_parana_records(records, codes, content_sha256=content_sha256)
    years_in_file = list(summary["years"])
    years = choose_panel_years(years_in_file)
    last = max(years)
    keep = set(years)

    groups: dict[str, dict[int, dict[str, float]]] = {c: {} for c in codes}
    classes_last: dict[str, dict[int, float]] = {c: {} for c in codes}
    for record in records:
        if record.year not in keep:
            continue
        group = CLASS_TO_GROUP.get(record.class_id)
        if group is None:
            raise MapBiomasContractError(
                f"Classe {record.class_id} sem grupo de exibição"
            )
        slot = groups[record.geocode].setdefault(record.year, {})
        slot[group] = slot.get(group, 0.0) + record.hectares
        if record.year == last:
            by_class = classes_last[record.geocode]
            by_class[record.class_id] = (
                by_class.get(record.class_id, 0.0) + record.hectares
            )

    municipalities: dict[str, Any] = {}
    deltas: dict[str, float] = {}
    totals: dict[int, dict[str, float]] = {year: {} for year in years}
    for code in sorted(codes):
        mapped = math.fsum(groups[code].get(last, {}).values())
        if mapped <= 0:
            raise MapBiomasContractError(f"Área mapeada nula em {code}, {last}")
        delta = (mapped / 100.0 - ibge_area_km2[code]) / ibge_area_km2[code]
        deltas[code] = delta
        by_year = {}
        for year in years:
            slot = groups[code].get(year, {})
            by_year[str(year)] = {g: round(v, 2) for g, v in sorted(slot.items())}
            for group, value in slot.items():
                totals[year][group] = totals[year].get(group, 0.0) + value
        municipalities[code] = {
            "groups_ha": by_year,
            "classes_ha_last": {
                str(k): round(v, 2) for k, v in sorted(classes_last[code].items())
            },
            "mapped_ha_last": round(mapped, 2),
            "ibge_area_km2": ibge_area_km2[code],
            "relative_delta_vs_ibge": round(delta, 6),
        }

    abs_deltas = sorted(abs(v) for v in deltas.values())
    median = statistics.median(abs_deltas)
    if median > MEDIAN_DELTA_LIMIT:
        raise MapBiomasContractError(
            f"Mediana da diferença para a área IBGE = {median:.4f}: a soma "
            "por bioma não fecha com o município. Carga interrompida."
        )
    worst = sorted(deltas.items(), key=lambda kv: -abs(kv[1]))[:10]
    quality = {
        "geocode_count": summary["geocode_count"],
        "biomes": list(summary["biomes"]),
        "years_in_file": years_in_file,
        "record_count": summary["record_count"],
        "classes_present": sorted({r.class_id for r in records}),
        "area_delta_vs_ibge": {
            "median_abs": round(median, 6),
            "max_abs": round(abs_deltas[-1], 6),
            "municipalities_above_0_5_percent": sum(v > 0.005 for v in abs_deltas),
            "municipalities_above_1_percent": sum(v > 0.01 for v in abs_deltas),
            "largest": [{"cd_mun": c, "relative_delta": round(d, 6)} for c, d in worst],
        },
        "reconcile_ok": True,
    }
    panel = {
        "schema_version": 1,
        "uf": "PR",
        "collection": 11,
        "unit": "ha",
        "years": years,
        "last_year": last,
        "year_rule_pt": (
            "O painel guarda os anos múltiplos de 5 presentes no arquivo e o "
            "último ano. Os demais anos estão na tabela oficial."
        ),
        "groups": [
            {
                "key": key,
                "label_pt": GROUP_LABELS_PT[key],
                "color": GROUP_COLORS[key],
                "class_ids": list(DISPLAY_GROUPS[key]),
            }
            for key in DISPLAY_GROUPS
        ],
        "class_names": {str(k): v for k, v in CLASS_NAME.items()},
        "municipality_count": len(municipalities),
        "municipalities": municipalities,
        "totals_ha": {
            str(year): {g: round(v, 2) for g, v in sorted(slot.items())}
            for year, slot in totals.items()
        },
        "notices_pt": [
            "Cobertura e uso da terra mapeados por satélite (Landsat, 30 m). "
            "Não é cadastro de propriedade nem área plantada da PAM.",
            "O percentual usa a área mapeada do município como denominador, "
            "não a área oficial IBGE.",
            "A diferença entre anos mostra mudança de estoque de cada classe. "
            "Não é taxa de desmatamento nem identifica onde a mudança ocorreu.",
            "Cobertura florestal não é área protegida, e nenhuma classe "
            "indica aptidão ou restrição legal para empreendimentos.",
        ],
    }
    return panel, quality
