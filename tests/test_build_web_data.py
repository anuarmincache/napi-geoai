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


def test_pecuaria_da_ficha_carrega_a_unidade(tmp_path: Path) -> None:
    """Leite é «Mil litros» e rebanho é «Cabeças». Sem unidade, 2.960 engana."""
    gerador = _modulo()
    gerador.OUT = tmp_path
    gerador.main()
    fichas = json.loads((tmp_path / "fichas.json").read_text("utf-8"))
    pecuaria = {p["nome"]: p for p in fichas["4115200"]["pecuaria"]}
    assert pecuaria["Leite"]["unidade"] == "Mil litros"
    assert pecuaria["Bovinos"]["unidade"] == "Cabeças"
    assert all(p["unidade"] for p in fichas["4115200"]["pecuaria"])


def test_lavoura_publica_rendimento_e_area_colhida(tmp_path: Path) -> None:
    """Rendimento e área colhida já eram coletados; precisam chegar à tela."""
    gerador = _modulo()
    gerador.OUT = tmp_path
    gerador.main()
    agro = json.loads((tmp_path / "agricultura.json").read_text("utf-8"))
    soja = next(c for c in agro["culturas"] if c["nome"].startswith("Soja"))
    assert soja["unidade_rendimento"] == "Quilogramas por Hectare"
    assert soja["estado_colhida"]["soma_publicada"] > 0
    celula = soja["municipios"]["4115200"]
    assert celula["rendimento"] is not None and celula["colhida"] is not None
    # Rendimento é razão: nunca some entre municípios.
    assert any(
        "não se soma entre" in aviso for aviso in agro["avisos"]
    ), "falta o aviso de que rendimento não é somável"


def test_totais_de_usinas_fecham_entre_as_telas(tmp_path: Path) -> None:
    """A home e a aba Usinas mostravam totais diferentes sem explicação."""
    gerador = _modulo()
    gerador.OUT = tmp_path
    gerador.main()
    energia = json.loads((tmp_path / "energia.json").read_text("utf-8"))
    resumo = json.loads((tmp_path / "resumo.json").read_text("utf-8"))
    siga = energia["siga"]["totais"]
    kpi = next(k for k in resumo["kpis"] if k["id"] == "siga")
    assert round(float(kpi["valor"]), 1) == siga["mw"]
    soma_municipios = sum(m["mw_fiscalizada"] for m in energia["siga"]["municipios"])
    assert round(soma_municipios + siga["mw_nao_associados"], 1) == siga["mw"]
    assert sum(siga["usinas_por_tipo"].values()) + siga["nao_associados"] == (
        siga["usinas"]
    )


def test_perfil_municipal_da_geracao_distribuida(tmp_path: Path) -> None:
    gerador = _modulo()
    gerador.OUT = tmp_path
    gerador.main()
    energia = json.loads((tmp_path / "energia.json").read_text("utf-8"))
    maringa = next(m for m in energia["mmgd"]["municipios"] if m["cd"] == "4115200")
    assert sum(maringa["por_porte"].values()) == maringa["n"]
    assert sum(maringa["por_classe"].values()) == maringa["n"]
    assert energia["mmgd"]["totais"]["sem_potencia"] >= 0


def test_ndvi_saiu_do_site_mas_o_motor_continua() -> None:
    """A aba foi retirada; o motor e o piloto medido ficam no repositório."""
    gerador = _modulo()
    assert "ndvi" not in gerador.__file__.lower()
    fonte = (REPO / "scripts" / "build_web_data.py").read_text("utf-8")
    assert "ndvi" not in fonte.lower()
    assert not (REPO / "web" / "src" / "app" / "ndvi").exists()
    assert (REPO / "geoai" / "sentinel" / "targets.py").exists()
    assert (REPO / "data" / "derived" / "sentinel_maringa_pilot.json").exists()
    assert (REPO / "research" / "ndvi_congelado" / "LEIA-ME.md").exists()
