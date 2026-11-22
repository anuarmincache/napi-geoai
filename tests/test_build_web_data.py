"""Gerador dos dados do protótipo web. Não acessa rede."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from geoai.portal import load_population_panel_bundle

REPO = Path(__file__).resolve().parents[1]


def _modulo():
    caminho = REPO / "scripts" / "build_web_data.py"
    spec = importlib.util.spec_from_file_location(caminho.stem, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_round_coords_preserva_estrutura() -> None:
    gerador = _modulo()
    bruto = {
        "type": "Polygon",
        "coordinates": [[[-51.123456789, -23.987654321], [-51.0, -23.0]]],
    }
    arredondado = gerador.round_coords(bruto["coordinates"])
    assert arredondado == [[[-51.12346, -23.98765], [-51.0, -23.0]]]
    assert gerador.round_coords("texto") == "texto"


def test_saida_cobre_os_399_municipios(tmp_path: Path) -> None:
    gerador = _modulo()
    gerador.OUT = tmp_path
    assert gerador.main() == 0

    malha = json.loads((tmp_path / "municipios.geojson").read_text("utf-8"))
    esperados = {
        str(m["CD_MUN"])
        for m in load_population_panel_bundle(REPO).panel["municipalities"]
    }
    codigos = {f["properties"]["cd"] for f in malha["features"]}
    assert codigos == esperados and len(malha["features"]) == 399

    resumo = json.loads((tmp_path / "resumo.json").read_text("utf-8"))
    assert {k["id"] for k in resumo["kpis"]} >= {"municipios", "populacao"}
    # Toda camada publicada declara fonte e classe científica.
    assert all(c["fonte"] and c["classe"] in {"A", "B", "C"} for c in resumo["camadas"])
    assert all(c["disponivel"] for c in resumo["camadas"])
    assert resumo["ndvi"]["publicados"] == 0

    fichas = json.loads((tmp_path / "fichas.json").read_text("utf-8"))
    assert set(fichas) == esperados
    maringa = fichas["4115200"]
    assert maringa["nome"] == "Maringá" and maringa["habitantes"] > 0


def test_ausencia_de_dado_nao_vira_zero(tmp_path: Path) -> None:
    gerador = _modulo()
    gerador.OUT = tmp_path
    gerador.main()
    malha = json.loads((tmp_path / "municipios.geojson").read_text("utf-8"))
    valores = [
        f["properties"]["mmgd_kw_hab"]
        for f in malha["features"]
        if f["properties"]["mmgd_mw"] is None
    ]
    assert all(v is None for v in valores)
    for feature in malha["features"]:
        props = feature["properties"]
        if props["habitantes"] is None:
            pytest.fail("população ausente não deveria ocorrer no painel validado")
