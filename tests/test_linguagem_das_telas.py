"""Nenhuma página deve mostrar vocabulário de bastidor para quem visita.

Este teste nasceu de uma falha repetida: a varredura por «NDVI» não achou
«Vegetação por satélite», e a varredura do protótipo web não achou as legendas
do portal Streamlit, que é o que está publicado. Buscar o termo técnico só
encontra o que já se sabe procurar. Aqui a direção é a inversa: renderiza cada
página e recusa o que tem cara de bastidor, qualquer que seja a palavra.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO = Path(__file__).resolve().parents[1]
PAGINAS = [REPO / "app" / "Home.py", *sorted((REPO / "app" / "pages").glob("*.py"))]

#: Cada regra é (nome, expressão, explicação do que fazer no lugar).
PROIBIDOS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "notação matemática",
        re.compile(r"[≠≈±∑∆Δ]"),
        "escreva «não é», «aproximadamente» ou «diferença» por extenso",
    ),
    (
        "carimbo de data ISO",
        re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"),
        "use geoai.portal.formatos.data_br para mostrar dd/mm/aaaa",
    ),
    (
        "dicionário ou lista em JSON",
        re.compile(r'\{\s*"[a-z_]+"\s*:'),
        "monte uma tabela ou frase; o JSON cabe no botão de download",
    ),
    (
        "identificador em snake_case",
        re.compile(r"(?<![\w/.-])[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}(?![\w/.-])"),
        "troque pelo nome que a pessoa usaria ao falar do dado",
    ),
    (
        "nome de coluna em maiúsculas",
        re.compile(r"(?<![\w])(AREA_KM2|CD_MUN|NM_MUN|SG_UF)(?![\w])"),
        "escreva «área oficial», «código do município», «nome do município»",
    ),
    (
        "termo em inglês",
        re.compile(
            r"(?i)(?<![\w])(snapshot|prototype|catalogued|dataframe|payload)(?![\w])"
        ),
        "use o termo equivalente em português",
    ),
)

#: Trechos legítimos que casariam com as regras acima. Cada um precisa de
#: motivo: são nomes de arquivo e de aba que a página de transparência exibe
#: de propósito, para que a pessoa reencontre a origem do número.
PERMITIDOS: tuple[str, ...] = (
    "MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx",
    "COVERAGE_11",
    "READ_ME",
    "napi_geoai",
    "requirements.txt",
    "pyproject.toml",
    "build_web_data",
    "energy_calc",
)


def _texto_visivel(at: AppTest) -> str:
    partes: list[str] = []
    for grupo in (
        at.markdown,
        at.caption,
        at.info,
        at.warning,
        at.error,
        at.success,
        at.subheader,
        at.header,
        at.title,
    ):
        for elemento in grupo:
            valor = getattr(elemento, "value", None)
            if isinstance(valor, str):
                partes.append(valor)
    for metrica in at.metric:
        for campo in ("label", "value", "delta"):
            valor = getattr(metrica, campo, None)
            if isinstance(valor, str):
                partes.append(valor)
    return "\n".join(partes)


def _sem_permitidos(texto: str) -> str:
    for trecho in PERMITIDOS:
        texto = texto.replace(trecho, " ")
    # URLs e hashes não são linguagem de tela: a pessoa os copia, não os lê.
    texto = re.sub(r"https?://\S+", " ", texto)
    texto = re.sub(r"\b[0-9a-f]{8,}\b", " ", texto)
    return texto


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p.name)
def test_pagina_nao_mostra_vocabulario_de_bastidor(pagina: Path) -> None:
    sys.path.insert(0, str(REPO / "app"))
    at = AppTest.from_file(str(pagina), default_timeout=240)
    at.run()
    assert not at.exception, f"{pagina.name} não subiu"

    texto = _sem_permitidos(_texto_visivel(at))
    achados: list[str] = []
    for nome, expressao, conserto in PROIBIDOS:
        for encontrado in set(expressao.findall(texto)):
            trecho = encontrado if isinstance(encontrado, str) else encontrado[0]
            achados.append(f"{nome}: «{trecho}» → {conserto}")
    assert not achados, f"{pagina.name} mostra vocabulário de bastidor:\n" + "\n".join(
        sorted(achados)
    )
