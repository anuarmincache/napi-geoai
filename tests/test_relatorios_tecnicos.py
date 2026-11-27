"""Os relatórios técnicos precisam sair legíveis, não como estrutura crua.

A página de fontes exibia um retrato montado para demonstração, despejado como
JSON. Estes testes fixam o formato que entrou no lugar: rótulo em português,
número no padrão brasileiro e nenhuma chave de programação na tela.
"""

from __future__ import annotations

import re

import pytest
from geoai.portal.relatorios import (
    relatorio_da_malha,
    relatorio_do_cruzamento,
    relatorios_tecnicos,
)

# As mesmas formas que o teste de linguagem das telas recusa.
SNAKE_CASE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
CARIMBO_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
NOTACAO = re.compile(r"[≠≈±∆Δ÷×]")


def test_os_dois_relatorios_estao_disponiveis() -> None:
    titulos = [r.titulo for r in relatorios_tecnicos()]
    assert titulos == [
        "Validação da malha municipal",
        "Cruzamento espacial das usinas",
    ]


@pytest.mark.parametrize(
    "construtor", [relatorio_da_malha, relatorio_do_cruzamento]
)
def test_relatorio_nao_mostra_vocabulario_de_bastidor(construtor) -> None:
    relatorio = construtor()
    assert relatorio is not None

    texto = "\n".join(
        [relatorio.titulo, relatorio.resumo, relatorio.motor, relatorio.gerado_em]
        + [f"{rotulo} {valor}" for rotulo, valor in relatorio.linhas]
    )
    # Códigos EPSG são identificadores padronizados que o revisor precisa ver.
    texto = re.sub(r"EPSG:\d+", " ", texto)

    assert not SNAKE_CASE.search(texto), f"identificador cru em {relatorio.titulo}"
    assert not CARIMBO_ISO.search(texto), f"carimbo técnico em {relatorio.titulo}"
    assert not NOTACAO.search(texto), f"notação matemática em {relatorio.titulo}"


def test_data_de_geracao_sai_no_formato_brasileiro() -> None:
    for relatorio in relatorios_tecnicos():
        assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", relatorio.gerado_em), (
            f"{relatorio.titulo} não mostra a data como dd/mm/aaaa"
        )


def test_versoes_do_motor_ficam_registradas() -> None:
    """Mudança de biblioteca pode alterar resultado de reprojeção."""

    for relatorio in relatorios_tecnicos():
        assert "QGIS" in relatorio.motor
        assert "GDAL" in relatorio.motor
        assert "PROJ" in relatorio.motor


def test_a_conta_das_usinas_fecha_na_tela() -> None:
    """310 na fase = 276 associadas + 34 sem município definido."""

    relatorio = relatorio_do_cruzamento()
    assert relatorio is not None
    valores = dict(relatorio.linhas)

    assert valores["Associados a um município"] == "276"
    assert valores["Empreendimentos sem município definido no painel"] == "34"
    assert valores["Registros na fase considerada"].startswith("310")


def test_tolerancia_sai_em_metros_e_nao_em_notacao_de_biblioteca() -> None:
    relatorio = relatorio_do_cruzamento()
    assert relatorio is not None
    regra = dict(relatorio.linhas)["Regra de contenção usada"]

    assert "metros" in regra
    assert "within" not in regra


def test_diferenca_de_area_sai_como_percentual_legivel() -> None:
    """5.426e-05 não é número de tela; 0,0054% é."""

    relatorio = relatorio_da_malha()
    assert relatorio is not None
    maior = dict(relatorio.linhas)[
        "Maior diferença entre a área do IBGE e a medida elipsoidal"
    ]

    assert maior.endswith("%")
    assert "e-" not in maior
    assert "," in maior


def test_o_arquivo_original_continua_disponivel() -> None:
    """JSON é para baixar e conferir, não para ler na tela."""

    for relatorio in relatorios_tecnicos():
        assert relatorio.arquivo is not None
        assert relatorio.arquivo.exists()
        assert relatorio.nome_do_arquivo.endswith(".json")
