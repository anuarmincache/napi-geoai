"""Municípios parecidos: conta determinística, sem rede e sem completar lacuna."""

from __future__ import annotations

import pytest
from geoai.portal import load_mmgd_panel_bundle, load_population_panel_bundle
from geoai.portal.landcover_panel import load_landcover_bundle
from geoai.portal.similaridade import (
    VARIAVEIS,
    DadosInsuficientes,
    construir_indice,
    linhas_dos_paineis,
    municipios_parecidos,
    nota_isolamento_pt,
)


def _linha(nome: str, **kw: float) -> dict[str, object]:
    base = {v.chave: 1.0 for v in VARIAVEIS}
    base.update(kw)
    base["nome"] = nome
    return base


def _conjunto_minimo() -> dict[str, dict[str, object]]:
    return {
        "1": _linha("Alfa", populacao=1_000, area_km2=100, densidade=10),
        "2": _linha("Beta", populacao=1_100, area_km2=110, densidade=10),
        "3": _linha("Gama", populacao=900_000, area_km2=9_000, densidade=100),
    }


def test_vizinho_mais_proximo_e_o_mais_parecido() -> None:
    indice = construir_indice(_conjunto_minimo())
    vizinhos = municipios_parecidos(indice, "1", quantidade=2)
    assert [v.nome for v in vizinhos] == ["Beta", "Gama"]
    assert vizinhos[0].distancia < vizinhos[1].distancia


def test_resultado_e_reproduzivel() -> None:
    """Mesma entrada, mesma saída. Sem isso o indicador não é citável."""
    a = construir_indice(_conjunto_minimo())
    b = construir_indice(_conjunto_minimo())
    assert municipios_parecidos(a, "1") == municipios_parecidos(b, "1")


def test_simetria_da_distancia() -> None:
    indice = construir_indice(_conjunto_minimo())
    ida = next(
        v for v in municipios_parecidos(indice, "1", quantidade=5) if v.cd_mun == "3"
    )
    volta = next(
        v for v in municipios_parecidos(indice, "3", quantidade=5) if v.cd_mun == "1"
    )
    assert ida.distancia == pytest.approx(volta.distancia)


def test_municipio_nao_e_vizinho_de_si_mesmo() -> None:
    indice = construir_indice(_conjunto_minimo())
    assert all(v.cd_mun != "1" for v in municipios_parecidos(indice, "1", quantidade=9))


def test_variavel_ausente_descarta_o_municipio_em_vez_de_virar_zero() -> None:
    """Falha fechada: lacuna não vira zero só para o município entrar na conta."""
    linhas = _conjunto_minimo()
    linhas["4"] = _linha("Delta", populacao=1_000)
    linhas["4"]["floresta"] = None
    indice = construir_indice(linhas)
    assert "4" not in indice.z
    assert municipios_parecidos(indice, "4") == []


def test_indice_recusa_entrada_insuficiente() -> None:
    with pytest.raises(DadosInsuficientes):
        construir_indice({})
    with pytest.raises(DadosInsuficientes):
        construir_indice({"1": _linha("Alfa")})


def test_aviso_de_isolamento_so_aparece_quando_nada_esta_perto() -> None:
    indice = construir_indice(_conjunto_minimo())
    assert nota_isolamento_pt(municipios_parecidos(indice, "1", quantidade=1)) is None
    assert nota_isolamento_pt([]) is None


def test_potencia_de_usinas_fica_fora_do_metodo() -> None:
    """276 municípios são «sem empreendimento», que não é zero comprovado."""
    chaves = {v.chave for v in VARIAVEIS}
    assert "siga_mw" not in chaves and "usinas" not in chaves


def test_indice_real_cobre_os_399_municipios() -> None:
    indice = construir_indice(
        linhas_dos_paineis(
            populacao=load_population_panel_bundle(),
            cobertura=load_landcover_bundle(),
            mmgd=load_mmgd_panel_bundle(),
        )
    )
    assert indice.total == 399
    vizinhos = municipios_parecidos(indice, "4115200", quantidade=5)
    assert len(vizinhos) == 5
    assert "Maringá" not in {v.nome for v in vizinhos}
    assert all(v.distancia > 0 for v in vizinhos)


def test_curitiba_nao_tem_par_no_estado() -> None:
    """A distância é informação: quando ninguém está perto, a tela precisa dizer."""
    indice = construir_indice(
        linhas_dos_paineis(
            populacao=load_population_panel_bundle(),
            cobertura=load_landcover_bundle(),
            mmgd=load_mmgd_panel_bundle(),
        )
    )
    vizinhos = municipios_parecidos(indice, "4106902", quantidade=5)
    assert nota_isolamento_pt(vizinhos) is not None
