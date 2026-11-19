"""Conector SIDRA e painel agropecuário — só fixtures sintéticas de teste."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.agriculture import PAM_VARIABLES, STATUS_NO_RECORD, build_agro_panel
from geoai.connectors.sidra import (
    STATUS_SUPPRESSED,
    STATUS_UNAVAILABLE,
    STATUS_VALUE,
    STATUS_ZERO,
    SidraError,
    parse_sidra_value,
    parse_sidra_values,
    resolve_category,
    resolve_classification,
    resolve_variable,
    values_url,
)
from geoai.portal.agro_panel import (
    agro_cell,
    agro_indicator,
    agro_ranked,
    agro_state_summary,
    load_agro_panel_bundle,
)
from geoai.portal.paths import (
    agro_panel_path,
    agro_provenance_path,
    agro_quality_path,
)

CODES = {f"41{n:05d}" for n in range(1, 400)}
CLASS = "Produto das lavouras temporárias e permanentes"


def _payload(var_id, var_name, unit, class_name, rows):
    header = {
        "NC": "Nível Territorial (Código)",
        "NN": "Nível Territorial",
        "MC": "Unidade de Medida (Código)",
        "MN": "Unidade de Medida",
        "V": "Valor",
        "D1C": "Município (Código)",
        "D1N": "Município",
        "D2C": "Variável (Código)",
        "D2N": "Variável",
        "D3C": "Ano (Código)",
        "D3N": "Ano",
        "D4C": f"{class_name} (Código)",
        "D4N": class_name,
    }
    body = [
        {
            "NC": "6",
            "NN": "Município",
            "MC": "1",
            "MN": unit,
            "V": value,
            "D1C": code,
            "D1N": f"Mun {code} - PR",
            "D2C": str(var_id),
            "D2N": var_name,
            "D3C": "2025",
            "D3N": "2025",
            "D4C": str(cat_id),
            "D4N": cat_name,
        }
        for code, cat_id, cat_name, value in rows
    ]
    return [header, *body]


def _records():
    codes = sorted(CODES)
    pam = {}
    for idx, key in enumerate(PAM_VARIABLES):
        rows = []
        for code in codes[:-1]:  # último município sem linha
            rows.append((code, 1, "Soja (em grão)", "100"))
            rows.append((code, 2, "Milho (em grão)", "X" if code == codes[0] else "50"))
            rows.append((code, 3, "Abacaxi", "-"))
            rows.append((code, 0, "Total", "150"))
        pam[key] = parse_sidra_values(
            _payload(10 + idx, f"var {key}", "Hectares", CLASS, rows),
            classification_name=CLASS,
        )
    herd_rows = []
    for code in codes:
        herd_rows.append((code, 7, "Bovino", "10"))
        herd_rows.append(
            (code, 8, "Suíno - total", "..." if code == codes[1] else "20")
        )
        herd_rows.append((code, 9, "Galináceos - total", "30"))
    herd = parse_sidra_values(
        _payload(105, "Efetivo dos rebanhos", "Cabeças", "Tipo de rebanho", herd_rows),
        classification_name="Tipo de rebanho",
    )
    product = parse_sidra_values(
        _payload(
            106,
            "Produção de origem animal",
            "Mil litros",
            "Tipo de produto de origem animal",
            [(code, 5, "Leite", "4") for code in codes],
        ),
        classification_name="Tipo de produto de origem animal",
    )
    return pam, herd, product


def _panel():
    pam, herd, product = _records()
    return build_agro_panel(
        municipality_codes=CODES,
        pam_records=pam,
        herd_records=herd,
        product_records=product,
    )


def test_value_symbols_are_never_coerced_to_numbers() -> None:
    assert parse_sidra_value("12.5") == (12.5, STATUS_VALUE)
    assert parse_sidra_value("-") == (0.0, STATUS_ZERO)
    assert parse_sidra_value("...") == (None, STATUS_UNAVAILABLE)
    assert parse_sidra_value("X") == (None, STATUS_SUPPRESSED)
    with pytest.raises(SidraError):
        parse_sidra_value("abc")
    with pytest.raises(SidraError):
        parse_sidra_value("")


def test_identifiers_resolved_by_name_fail_closed() -> None:
    meta = {
        "variaveis": [
            {"id": 1, "nome": "Área plantada ou destinada à colheita"},
            {"id": 2, "nome": "Área plantada ou destinada à colheita - percentual"},
            {"id": 3, "nome": "Área colhida", "unidade": "Hectares"},
        ],
        "classificacoes": [
            {
                "id": 782,
                "nome": CLASS,
                "categorias": [{"id": 9, "nome": "Soja (em grão)"}],
            }
        ],
    }
    assert resolve_variable(meta, "Área plantada", prefix=True).item_id == 1
    assert resolve_variable(meta, "Área colhida").unit == "Hectares"
    cls = resolve_classification(meta, "Produto das lavouras")
    assert resolve_category(cls, "soja (em grao)").item_id == 9
    with pytest.raises(SidraError):
        resolve_variable(meta, "Quantidade produzida")
    with pytest.raises(SidraError):
        resolve_category(cls, "Milho (em grão)")


def test_values_url_targets_parana_municipalities() -> None:
    url = values_url(3939, 105, classification_id=79, category_ids=(1, 2))
    assert url.endswith("/t/3939/n6/in%20n3%2041/v/105/p/last%201/c79/1,2")
    assert values_url(5457, 214, classification_id=782).endswith("/c782/all")


def test_panel_keeps_missing_suppressed_and_zero_apart() -> None:
    panel = _panel()
    codes = sorted(CODES)
    crops = {c["name"]: c["id"] for c in panel["pam"]["crops"]}
    assert set(crops) == {"Soja (em grão)", "Milho (em grão)"}  # sem Total/zero
    milho = crops["Milho (em grão)"]
    first = panel["municipalities"][codes[0]]["pam"][milho]["area_plantada"]
    assert first == [None, STATUS_SUPPRESSED]
    assert panel["municipalities"][codes[-1]]["pam"] == {}
    total = panel["totals"]["pam"][milho]["area_plantada"]
    assert total["soma_publicada"] == 50 * 397
    assert total["contagem_por_status"][STATUS_SUPPRESSED] == 1
    assert total["contagem_por_status"][STATUS_NO_RECORD] == 1
    assert "soma_publicada" not in panel["totals"]["pam"][milho]["rendimento"]
    suinos = panel["totals"]["ppm"]["suinos"]
    assert suinos["soma_publicada"] == 20 * 398
    assert suinos["contagem_por_status"][STATUS_UNAVAILABLE] == 1


def test_panel_rejects_codes_outside_mesh() -> None:
    pam, herd, product = _records()
    with pytest.raises(SidraError):
        build_agro_panel(
            municipality_codes=CODES - {sorted(CODES)[5]},
            pam_records=pam,
            herd_records=herd,
            product_records=product,
        )


def _write(root: Path, panel: dict, *, reconcile: bool = True) -> None:
    agro_panel_path(root).parent.mkdir(parents=True, exist_ok=True)
    agro_panel_path(root).write_text(json.dumps(panel), encoding="utf-8")
    agro_quality_path(root).write_text(
        json.dumps({"reconcile_ok": reconcile}), encoding="utf-8"
    )
    agro_provenance_path(root).write_text("{}", encoding="utf-8")


def test_loader_fail_closed(tmp_path: Path) -> None:
    assert load_agro_panel_bundle(tmp_path).available is False
    _write(tmp_path, _panel(), reconcile=False)
    assert load_agro_panel_bundle(tmp_path).available is False
    broken = _panel()
    broken["municipalities"].pop(sorted(CODES)[0])
    _write(tmp_path, broken)
    assert load_agro_panel_bundle(tmp_path).available is False


def test_presentation_service_reads_cells(tmp_path: Path) -> None:
    _write(tmp_path, _panel())
    bundle = load_agro_panel_bundle(tmp_path)
    assert bundle.available, bundle.missing_reason_pt
    codes = sorted(CODES)
    suinos = agro_indicator(bundle, "ppm", "suinos")
    assert suinos.unit == "Cabeças" and suinos.year == "2025"
    assert agro_cell(bundle, codes[1], suinos) == (None, STATUS_UNAVAILABLE)
    assert agro_cell(bundle, codes[2], suinos) == (20.0, STATUS_VALUE)
    assert agro_state_summary(bundle, suinos)["soma_publicada"] == 20 * 398
    crop = bundle.panel["pam"]["crops"][0]["id"]
    rend = agro_indicator(bundle, "pam", "rendimento", crop)
    assert rend.summable is False
    assert agro_cell(bundle, codes[-1], rend) == (None, STATUS_NO_RECORD)
    top = agro_ranked(bundle, suinos, {}, limit=3)
    assert len(top) == 3 and all(r["valor"] == 20.0 for r in top)
