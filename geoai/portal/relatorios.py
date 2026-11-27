"""Relatórios técnicos em linguagem de tela.

A página de fontes mostrava um retrato de qualidade montado para demonstração,
despejado como JSON cru. Esse formato contradiz o resto do portal: chave em
inglês, carimbo de data em formato técnico e nome com sublinhado são justamente
o que as outras telas deixaram de exibir.

Aqui os dois relatórios que um revisor realmente quer conferir, a validação da
malha municipal e o cruzamento espacial das usinas, viram pares de rótulo e
valor em português. O arquivo original continua disponível para download, que é
a forma certa de entregar JSON: a pessoa copia, não lê na tela.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from geoai.portal.formatos import data_br, numero_br
from geoai.portal.paths import (
    energy_qgis_report_path,
    municipalities_qgis_report_path,
)

AUSENTE = "não registrado"


@dataclass(frozen=True)
class Relatorio:
    """Um relatório técnico pronto para a tela."""

    titulo: str
    resumo: str
    linhas: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    motor: str = ""
    gerado_em: str = ""
    arquivo: Path | None = None
    conteudo: str = ""
    nome_do_arquivo: str = ""


def _ler(caminho: Path) -> dict[str, Any] | None:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _motor(dados: dict[str, Any]) -> str:
    """Versões usadas, que mudam resultado de reprojeção entre lançamentos."""

    motor = dados.get("engine") or {}
    qgis = str(motor.get("qgis_version") or "").split("-")[0]
    partes = [
        f"QGIS {qgis}" if qgis else "",
        f"GDAL {motor.get('gdal_version')}" if motor.get("gdal_version") else "",
        f"PROJ {motor.get('proj_version')}" if motor.get("proj_version") else "",
    ]
    return " · ".join(p for p in partes if p)


def _percentual(valor: object) -> str:
    """Fração relativa vira percentual legível, sem notação científica."""

    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return AUSENTE
    return f"{numero_br(numero * 100, 4)}%"


def relatorio_da_malha(repo_root: Path | None = None) -> Relatorio | None:
    """Validação geométrica dos 399 polígonos municipais."""

    caminho = municipalities_qgis_report_path(repo_root)
    dados = _ler(caminho)
    if dados is None:
        return None

    entrada = dados.get("input") or {}
    resultados = dados.get("results") or {}
    parametros = dados.get("parameters") or {}

    piores = resultados.get("worst_rel_diff_top5") or []
    pior = piores[0] if isinstance(piores, list) and piores else {}

    linhas: list[tuple[str, str]] = [
        ("Polígonos no arquivo", numero_br(entrada.get("feature_count"))),
        ("Polígonos válidos", numero_br(resultados.get("valid_count"))),
        (
            "Polígonos inválidos, vazios ou de tipo errado",
            numero_br(resultados.get("invalid_count")),
        ),
        (
            "Códigos de município sem repetição",
            numero_br(resultados.get("unique_cd_mun")),
        ),
        (
            "Sistema de coordenadas da fonte",
            str(entrada.get("crs_authid") or AUSENTE),
        ),
        (
            "Elipsoide usado na medição de área",
            str(parametros.get("ellipsoid") or AUSENTE),
        ),
        (
            "Maior diferença entre a área do IBGE e a medida elipsoidal",
            _percentual(resultados.get("area_rel_diff_max")),
        ),
        (
            "Diferença mediana entre as duas medidas",
            _percentual(resultados.get("area_rel_diff_median")),
        ),
    ]
    if pior.get("NM_MUN"):
        linhas.append(
            (
                "Município com a maior diferença",
                f"{pior.get('NM_MUN')} "
                f"({numero_br(pior.get('AREA_KM2_IBGE'), 1)} km² na malha do IBGE)",
            )
        )

    return Relatorio(
        titulo="Validação da malha municipal",
        resumo=(
            "Cada polígono municipal é conferido um a um, e a área é medida de "
            "forma independente apenas para checar a base. O valor publicado "
            "continua sendo o oficial do IBGE: o Paraná atravessa duas zonas "
            "UTM, então medir o estado inteiro em uma só zona distorceria o "
            "oeste."
        ),
        linhas=tuple(linhas),
        motor=_motor(dados),
        gerado_em=data_br(dados.get("generated_at")),
        arquivo=caminho,
        nome_do_arquivo=caminho.name,
    )


def relatorio_do_cruzamento(repo_root: Path | None = None) -> Relatorio | None:
    """Associação de cada usina ao polígono municipal que a contém."""

    caminho = energy_qgis_report_path(repo_root)
    dados = _ler(caminho)
    if dados is None:
        return None

    motor = dados.get("engine") or {}
    parametros = dados.get("parameters") or {}
    resultados = dados.get("results") or {}
    totais = resultados.get("panel_totals_official") or {}

    linhas: tuple[tuple[str, str], ...] = (
        ("Registros do Paraná no cadastro", numero_br(resultados.get("rows_pr"))),
        (
            "Registros na fase considerada",
            f"{numero_br(resultados.get('operacao'))} "
            f"(fase {parametros.get('phase') or AUSENTE})",
        ),
        ("Com coordenada válida", numero_br(resultados.get("points_created"))),
        (
            "Descartados por coordenada ausente ou fora de faixa",
            numero_br(resultados.get("skipped_invalid_coords")),
        ),
        ("Associados a um município", numero_br(resultados.get("matched"))),
        (
            "Válidos que caem fora de qualquer polígono do Paraná",
            numero_br(resultados.get("unmatched")),
        ),
        (
            "Empreendimentos sem município definido no painel",
            numero_br(totais.get("n_empreendimentos_nao_associados")),
        ),
        (
            "Capacidade fiscalizada com município definido",
            f"{numero_br(totais.get('potencia_fiscalizada_mw_municipios'), 1)} MW",
        ),
        (
            "Capacidade fiscalizada sem município definido",
            f"{numero_br(totais.get('potencia_fiscalizada_mw_nao_associados'), 1)} MW",
        ),
        (
            "Regra de contenção usada",
            f"ponto dentro do polígono, com tolerância de "
            f"{_tolerancia(motor.get('predicate'))}",
        ),
    )

    return Relatorio(
        titulo="Cruzamento espacial das usinas",
        resumo=(
            "Cada usina é associada ao município cujo polígono contém o seu "
            "ponto. O mesmo cruzamento é refeito por um segundo motor, em "
            "outra biblioteca, e os dois resultados são comparados usina por "
            "usina pelo código do empreendimento. Divergência em um único "
            "registro interrompe a publicação."
        ),
        linhas=linhas,
        motor=_motor(dados),
        gerado_em=data_br(dados.get("generated_at")),
        arquivo=caminho,
        nome_do_arquivo=caminho.name,
    )


def _tolerancia(predicado: object) -> str:
    """`within(5)` é notação de biblioteca; na tela vira distância em metros."""

    texto = str(predicado or "")
    if "(" in texto and texto.rstrip().endswith(")"):
        dentro = texto[texto.index("(") + 1 : -1].strip()
        if dentro:
            return f"{numero_br(dentro)} metros"
    return AUSENTE


def relatorios_tecnicos(repo_root: Path | None = None) -> tuple[Relatorio, ...]:
    """Os relatórios disponíveis, na ordem em que a página os apresenta."""

    encontrados = (
        relatorio_da_malha(repo_root),
        relatorio_do_cruzamento(repo_root),
    )
    return tuple(r for r in encontrados if r is not None)
