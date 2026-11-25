"""Agregação determinística PAM/PPM → painel municipal (classe A).

Regras:

- Todo código municipal recebido precisa existir na malha IBGE (399).
  Código extra interrompe a carga.
- Município sem linha para um indicador fica ``sem_registro``. Ausência
  não vira zero e não é imputada.
- Símbolos ``..``, ``...`` e ``X`` do IBGE permanecem sem valor.
- Somas estaduais consideram apenas valores municipais publicados e
  registram quantos municípios ficaram de fora. Rendimento não é somado.
"""

from __future__ import annotations

import math
from typing import Any

from geoai.connectors.sidra import (
    STATUS_VALUE,
    STATUS_ZERO,
    SidraError,
    SidraRecord,
    normalize_name,
)

STATUS_NO_RECORD = "sem_registro"
TOP_CROPS = 12

# chave interna → (nome oficial nos metadados, casa por prefixo?)
PAM_VARIABLES: dict[str, tuple[str, bool]] = {
    "area_plantada": ("Área plantada", True),
    "area_colhida": ("Área colhida", False),
    "producao": ("Quantidade produzida", False),
    "rendimento": ("Rendimento médio da produção", False),
}
# chave interna → (tabela lógica, nome oficial da categoria)
PPM_INDICATORS: dict[str, tuple[str, str]] = {
    "bovinos": ("rebanho", "Bovino"),
    "suinos": ("rebanho", "Suíno - total"),
    "galinaceos": ("rebanho", "Galináceos - total"),
    "leite": ("produto", "Leite"),
}
_SUMMABLE = (STATUS_VALUE, STATUS_ZERO)


def _single(values: set[str], what: str) -> str:
    if len(values) != 1:
        raise SidraError(f"{what}: esperado valor único, obtido {sorted(values)}")
    return next(iter(values))


def _check_codes(records: list[SidraRecord], valid: set[str], what: str) -> None:
    extra = sorted({r.municipality_code for r in records} - valid)
    if extra:
        raise SidraError(
            f"{what}: {len(extra)} código(s) fora da malha IBGE do Paraná, "
            f"ex.: {extra[:5]}"
        )


def _summary(cells: list[list[Any]], n_expected: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for _value, status in cells:
        counts[status] = counts.get(status, 0) + 1
    counts[STATUS_NO_RECORD] = n_expected - len(cells)
    total = math.fsum(float(v) for v, s in cells if s in _SUMMABLE)
    return {"soma_publicada": total, "contagem_por_status": counts}


def build_agro_panel(
    *,
    municipality_codes: set[str],
    pam_records: dict[str, list[SidraRecord]],
    herd_records: list[SidraRecord],
    product_records: list[SidraRecord],
    top_crops: int = TOP_CROPS,
) -> dict[str, Any]:
    """Monta o painel. ``pam_records`` é indexado pelas chaves PAM_VARIABLES."""

    if set(pam_records) != set(PAM_VARIABLES):
        raise SidraError("PAM: conjunto de variáveis diferente do contrato")
    n_mun = len(municipality_codes)
    municipalities: dict[str, dict[str, Any]] = {
        code: {"pam": {}, "ppm": {}} for code in sorted(municipality_codes)
    }

    # ------------------------------------------------------------- PAM
    pam_years: set[str] = set()
    pam_vars: dict[str, dict[str, Any]] = {}
    crop_names: dict[str, str] = {}
    cells_pam: dict[str, dict[str, dict[str, list[Any]]]] = {}
    for key, records in pam_records.items():
        _check_codes(records, municipality_codes, f"PAM/{key}")
        pam_years |= {r.period for r in records}
        pam_vars[key] = {
            "id": _single({r.variable_id for r in records}, f"PAM/{key} variável"),
            "name": _single({r.variable_name for r in records}, f"PAM/{key} nome"),
            "unit": _single({r.unit for r in records}, f"PAM/{key} unidade"),
        }
        seen: set[tuple[str, str]] = set()
        for r in records:
            if r.category_id is None:
                raise SidraError(f"PAM/{key}: linha sem produto")
            if normalize_name(r.category_name or "") == "total":
                continue
            pair = (r.municipality_code, r.category_id)
            if pair in seen:
                raise SidraError(f"PAM/{key}: linha duplicada {pair}")
            seen.add(pair)
            crop_names[r.category_id] = str(r.category_name)
            cells_pam.setdefault(r.category_id, {}).setdefault(key, {})[
                r.municipality_code
            ] = [r.value, r.status]
    pam_year = _single(pam_years, "PAM ano de referência")

    area_sum = {
        crop: math.fsum(
            float(v)
            for v, s in by_var.get("area_plantada", {}).values()
            if s in _SUMMABLE
        )
        for crop, by_var in cells_pam.items()
    }
    ranked = sorted(area_sum, key=lambda c: (-area_sum[c], int(c)))
    selected = [c for c in ranked if area_sum[c] > 0][: max(0, top_crops)]

    pam_totals: dict[str, Any] = {}
    for crop in selected:
        pam_totals[crop] = {}
        for key in PAM_VARIABLES:
            by_mun = cells_pam[crop].get(key, {})
            for code, cell in by_mun.items():
                municipalities[code]["pam"].setdefault(crop, {})[key] = cell
            summary = _summary(list(by_mun.values()), n_mun)
            if key == "rendimento":
                summary.pop("soma_publicada")
            pam_totals[crop][key] = summary

    # ------------------------------------------------------------- PPM
    ppm_indicators: dict[str, dict[str, Any]] = {}
    ppm_totals: dict[str, Any] = {}
    sources = {"rebanho": herd_records, "produto": product_records}
    years = {"rebanho": set(), "produto": set()}
    for label, records in sources.items():
        _check_codes(records, municipality_codes, f"PPM/{label}")
        years[label] = {r.period for r in records}
    for key, (label, category) in PPM_INDICATORS.items():
        rows = [
            r
            for r in sources[label]
            if normalize_name(r.category_name or "") == normalize_name(category)
        ]
        if not rows:
            raise SidraError(f"PPM/{key}: nenhuma linha para «{category}»")
        if len({r.municipality_code for r in rows}) != len(rows):
            raise SidraError(f"PPM/{key}: município duplicado")
        ppm_indicators[key] = {
            "grupo": label,
            "variable_id": _single({r.variable_id for r in rows}, f"PPM/{key} var"),
            "variable_name": _single(
                {r.variable_name for r in rows}, f"PPM/{key} nome"
            ),
            "category_id": _single(
                {str(r.category_id) for r in rows}, f"PPM/{key} categoria"
            ),
            "category_name": _single(
                {str(r.category_name) for r in rows}, f"PPM/{key} nome categoria"
            ),
            "unit": _single({r.unit for r in rows}, f"PPM/{key} unidade"),
        }
        cells = []
        for r in rows:
            cell = [r.value, r.status]
            municipalities[r.municipality_code]["ppm"][key] = cell
            cells.append(cell)
        ppm_totals[key] = _summary(cells, n_mun)

    return {
        "schema_version": 1,
        "uf": "PR",
        "municipality_count": n_mun,
        "pam": {
            "year": pam_year,
            "variables": pam_vars,
            "crops": [
                {
                    "id": crop,
                    "name": crop_names[crop],
                    "area_plantada_soma_publicada": area_sum[crop],
                }
                for crop in selected
            ],
            "crops_available_in_source": len(crop_names),
            "crop_selection_rule_pt": (
                f"As {len(selected)} culturas com maior soma municipal publicada "
                "de área plantada no Paraná no ano de referência. As demais "
                "culturas da tabela não entram neste painel."
            ),
        },
        "ppm": {
            "year_rebanho": _single(years["rebanho"], "PPM rebanho ano"),
            "year_produto": _single(years["produto"], "PPM produto ano"),
            "indicators": ppm_indicators,
        },
        "municipalities": municipalities,
        "totals": {"pam": pam_totals, "ppm": ppm_totals},
        "notices_pt": [
            "Efetivo de rebanho não é quantidade de resíduo disponível para "
            "biodigestores.",
            "Somas estaduais incluem apenas valores municipais publicados. "
            "Sigilo estatístico e não disponível ficam de fora.",
            "Município sem linha na tabela aparece como sem registro, não "
            "como zero.",
            "Área plantada (PAM) não é área de cobertura do solo (MapBiomas).",
        ],
    }
