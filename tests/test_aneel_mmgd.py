"""Testes do conector e agregação MMGD. Fixtures sintéticas ≠ dados oficiais."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest
from geoai.connectors.aneel_mmgd import (
    PERSONAL_OR_SENSITIVE_FIELDS,
    REQUIRED_MMGD_FIELDS,
    iter_mmgd_rows,
    validate_mmgd_zip_file,
)
from geoai.connectors.errors import ValidationConnectorError
from geoai.energy.mmgd_aggregate import aggregate_mmgd_by_municipality
from geoai.energy.mmgd_normalize import normalize_mmgd_row, parse_nonneg_int


def _write_zip(path: Path, rows: list[dict[str, str]]) -> None:
    fields = list(REQUIRED_MMGD_FIELDS) + [
        "NumCPFCNPJ",
        "NomTitularEmpreendimento",
        "CodCEP",
        "NumCoordESub",
        "NumCoordNSub",
        "NumCNPJDistribuidora",
        "NomAgente",
        "CodSubGrupoTarifario",
        "DscSubGrupoTarifario",
        "CodRegiao",
        "NomRegiao",
        "SigTipoConsumidor",
        "SigModalidadeEmpreendimento",
        "DscModalidadeHabilitado",
        "NomSubEstacao",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=fields,
        delimiter=";",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("empreendimento-geracao-distribuida.csv", buf.getvalue())


def _base_row(**overrides: str) -> dict[str, str]:
    row = {
        "DatGeracaoConjuntoDados": "2026-11-18",
        "AnmPeriodoReferencia": "11/2026",
        "SigAgente": "DIST",
        "CodClasseConsumo": "1",
        "DscClasseConsumo": "Residencial",
        "CodUFibge": "41",
        "SigUF": "PR",
        "CodMunicipioIbge": "4115200",
        "NomMunicipio": "Maringá",
        "CodEmpreendimento": "GD.PR.TEST.001",
        "DthAtualizaCadastralEmpreend": "2024-05-01",
        "QtdUCRecebeCredito": "1",
        "SigTipoGeracao": "UFV",
        "DscFonteGeracao": "Radiação solar",
        "DscPorte": "Microgeracao",
        "MdaPotenciaInstaladaKW": "5,00",
        "NumCPFCNPJ": "00000000000",
        "NomTitularEmpreendimento": "PESSOA FICTICIA",
        "CodCEP": "87000000",
        "NumCoordESub": "0",
        "NumCoordNSub": "0",
    }
    row.update(overrides)
    return row


def test_validate_zip_and_strip_personal_fields(tmp_path: Path) -> None:
    zip_path = tmp_path / "mmgd.zip"
    _write_zip(zip_path, [_base_row()])
    fields = validate_mmgd_zip_file(zip_path)
    assert "CodMunicipioIbge" in fields
    rows = list(iter_mmgd_rows(zip_path, uf="PR", public_only=True))
    assert len(rows) == 1
    assert "NumCPFCNPJ" not in rows[0]
    assert "NomTitularEmpreendimento" not in rows[0]
    assert rows[0]["CodMunicipioIbge"] == "4115200"
    for key in PERSONAL_OR_SENSITIVE_FIELDS:
        assert key not in rows[0]


def test_missing_required_column_fails(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    buf = io.StringIO("SigUF;CodEmpreendimento\nPR;X\n")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("empreendimento-geracao-distribuida.csv", buf.getvalue())
    with pytest.raises(ValidationConnectorError, match="sem campos"):
        validate_mmgd_zip_file(zip_path)


def test_aggregate_does_not_treat_uc_credito_as_plant_count() -> None:
    rows = [
        normalize_mmgd_row(
            _base_row(
                CodEmpreendimento="A",
                QtdUCRecebeCredito="3",
                MdaPotenciaInstaladaKW="10,00",
            )
        ),
        normalize_mmgd_row(
            _base_row(
                CodEmpreendimento="B",
                CodMunicipioIbge="4100103",
                NomMunicipio="Abatiá",
                QtdUCRecebeCredito="1",
                MdaPotenciaInstaladaKW="2,50",
            )
        ),
        normalize_mmgd_row(
            _base_row(
                CodEmpreendimento="C",
                SigUF="SP",
                CodMunicipioIbge="3550308",
            )
        ),
    ]
    panel = aggregate_mmgd_by_municipality(
        rows,
        ibge_codes={"4115200", "4100103", "4100202"},
    )
    assert panel["n_valid"] == 2
    assert panel["n_rejected"] == 1
    assert panel["municipalities"]["4115200"]["n_empreendimentos"] == 1
    assert panel["municipalities"]["4115200"]["qtd_uc_recebe_credito"] == 3
    assert panel["municipalities"]["4100103"]["potencia_instalada_kw_conhecida"] == 2.5
    assert panel["municipalities"]["4100202"]["n_empreendimentos"] == 0
    assert panel["municipalities"]["4100202"]["zero_confirmado_no_recorte"] is True
    assert panel["qtd_uc_recebe_credito_total"] == 4
    nota = panel["temporal_note_pt"].lower()
    assert "cadastro" in nota
    assert "não é a data" in nota


def test_negative_power_and_bad_ibge_rejected() -> None:
    bad_pot = normalize_mmgd_row(_base_row(MdaPotenciaInstaladaKW="-1,00"))
    bad_ibge = normalize_mmgd_row(_base_row(CodMunicipioIbge="41"))
    assert bad_pot.reject_reason
    assert bad_ibge.reject_reason
    assert parse_nonneg_int("2,00") == 2
    assert parse_nonneg_int("-1") is None


def test_duplicate_cod_empreendimento_rejected() -> None:
    plants = [
        normalize_mmgd_row(_base_row(CodEmpreendimento="DUP")),
        normalize_mmgd_row(_base_row(CodEmpreendimento="DUP")),
    ]
    panel = aggregate_mmgd_by_municipality(plants, ibge_codes={"4115200"})
    assert panel["n_valid"] == 1
    assert panel["duplicate_cod_empreendimento"] == 1
