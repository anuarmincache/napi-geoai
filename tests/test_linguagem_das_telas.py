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


def _texto_de_elementos_brutos(at: AppTest) -> list[str]:
    """Texto que não passa por markdown e por isso escapava desta checagem.

    A primeira versão deste teste lia só elementos de texto, então um
    `st.json` com chave em inglês e carimbo de data em formato técnico passava
    sem ser notado. Era o caso de dois blocos em produção. Elemento que exibe
    estrutura de dados na tela é linguagem de tela como qualquer outra.
    """

    partes: list[str] = []
    for tipo in ("dataframe", "table"):
        try:
            elementos = at.get(tipo)
        except (KeyError, AttributeError):  # pragma: no cover - versão sem o tipo
            continue
        for elemento in elementos:
            quadro = getattr(elemento, "value", None)
            colunas = getattr(quadro, "columns", None)
            if colunas is None:
                continue
            partes.extend(str(c) for c in colunas)
            for coluna in colunas:
                # Só os valores de texto: número de tabela não é vocabulário.
                serie = quadro[coluna]
                partes.extend(
                    str(v) for v in serie.unique()[:60] if isinstance(v, str)
                )
    for tipo in ("json", "code"):
        try:
            elementos = at.get(tipo)
        except (KeyError, AttributeError):  # pragma: no cover - versão sem o tipo
            continue
        for elemento in elementos:
            valor = getattr(elemento, "value", None)
            if isinstance(valor, str):
                partes.append(valor)
    return partes


def _texto_visivel(at: AppTest) -> str:
    partes: list[str] = _texto_de_elementos_brutos(at)
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


def _radio_de_nivel(at: AppTest) -> tuple[int, list[str]] | None:
    """Localiza o seletor de nível de leitura pela lista de opções."""

    for indice, radio in enumerate(at.radio):
        brutas = getattr(radio, "options", None)
        if not isinstance(brutas, (list, tuple)):
            continue
        opcoes = [o for o in brutas if isinstance(o, str)]
        if len(opcoes) >= 2 and any("cnic" in o for o in opcoes):
            return indice, opcoes
    return None


def _texto_em_todos_os_niveis(at: AppTest, pagina: Path) -> str:
    """Soma o texto da página em cada nível de leitura que ela oferece.

    Blocos exclusivos do nível técnico não apareciam nesta checagem, porque a
    página era renderizada só no nível padrão. Um deles despejava estrutura de
    dados crua na tela e passou meses sem ser visto.

    O seletor é reencontrado a cada volta: trocar o nível redesenha a página e
    o índice do widget anterior pode já apontar para outro controle.
    """

    partes = [_texto_visivel(at)]
    achado = _radio_de_nivel(at)
    if achado is None:
        return partes[0]
    for opcao in achado[1]:
        atual = _radio_de_nivel(at)
        if atual is None:
            break
        at.radio[atual[0]].set_value(opcao).run()
        assert not at.exception, f"{pagina.name} não subiu no nível {opcao}"
        partes.append(_texto_visivel(at))
    return "\n".join(partes)


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p.name)
def test_pagina_nao_mostra_vocabulario_de_bastidor(pagina: Path) -> None:
    sys.path.insert(0, str(REPO / "app"))
    at = AppTest.from_file(str(pagina), default_timeout=240)
    at.run()
    assert not at.exception, f"{pagina.name} não subiu"

    texto = _sem_permitidos(_texto_em_todos_os_niveis(at, pagina))
    achados: list[str] = []
    for nome, expressao, conserto in PROIBIDOS:
        for encontrado in set(expressao.findall(texto)):
            trecho = encontrado if isinstance(encontrado, str) else encontrado[0]
            achados.append(f"{nome}: «{trecho}» → {conserto}")
    assert not achados, f"{pagina.name} mostra vocabulário de bastidor:\n" + "\n".join(
        sorted(achados)
    )


SELETORES_COM_CODIGO = (
    ("app/pages/6_Energia_SIGA.py", "Tecnologia de geração"),
    ("app/pages/8_Energia_MMGD.py", "Tecnologia de geração"),
)


@pytest.mark.parametrize(("pagina", "rotulo"), SELETORES_COM_CODIGO)
def test_filtro_de_tecnologia_nao_oferece_so_a_sigla(pagina: str, rotulo: str) -> None:
    """Sigla sozinha em lista suspensa não deixa escolher quem não é do setor.

    O filtro mostrava CGH, EOL, PCH, UFV, UHE e UTE, sem nada que dissesse o
    que cada uma é. A sigla continua, entre parênteses, porque é como a ANEEL
    nomeia a tecnologia.
    """
    sys.path.insert(0, str(REPO / "app"))
    at = AppTest.from_file(str(REPO / pagina), default_timeout=240)
    at.run()
    assert not at.exception

    caixa = next((c for c in at.selectbox if str(c.label) == rotulo), None)
    assert caixa is not None, f"{pagina} não tem o filtro «{rotulo}»"

    soltas = [
        str(o) for o in caixa.options if re.fullmatch(r"[A-Z]{3,4}", str(o).strip())
    ]
    assert not soltas, (
        f"{pagina}: {soltas} aparecem só como sigla. Use "
        "geoai.portal.formatos.rotulo_tecnologia para pôr o nome junto."
    )
