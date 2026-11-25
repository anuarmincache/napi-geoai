"""Formatação de valores para a tela, compartilhada entre as páginas.

Os artefatos guardam datas em ISO 8601 e identificadores técnicos porque é
assim que se audita. A tela é outro público: aqui ficam as conversões que
transformam esses valores em texto legível, em um lugar só, para não serem
reescritas em cada página.
"""

from __future__ import annotations

#: Identificadores de edição da malha, como gravados nos artefatos.
EDICOES_DA_MALHA: dict[str, str] = {
    "municipio_2025": "Malha Municipal 2025",
    "municipio_2024": "Malha Municipal 2024",
    "municipio_2023": "Malha Municipal 2023",
}


def data_br(valor: object, *, ausente: str = "data não registrada") -> str:
    """Converte 2026-11-11T22:28:18.980415+00:00 em 11/11/2026.

    Devolve ``ausente`` quando não houver data. Texto que não comece por uma
    data ISO volta como está, para não inventar formato sobre valor estranho.
    """
    texto = str(valor or "").strip()
    if not texto:
        return ausente
    cabeca = texto[:10]
    if len(cabeca) == 10 and cabeca[4] == "-" and cabeca[7] == "-":
        ano, mes, dia = cabeca[:4], cabeca[5:7], cabeca[8:10]
        if ano.isdigit() and mes.isdigit() and dia.isdigit():
            return f"{dia}/{mes}/{ano}"
    return texto


def edicao_da_malha(valor: object, *, ausente: str = "edição não registrada") -> str:
    """Troca o identificador da malha pelo nome que o IBGE publica."""
    bruto = str(valor or "").strip()
    if not bruto:
        return ausente
    return EDICOES_DA_MALHA.get(bruto, bruto.replace("_", " ").title())


def numero_br(valor: object, casas: int = 0, *, ausente: str = "n/d") -> str:
    """Formata no padrão brasileiro: ponto nos milhares, vírgula nos decimais.

    Escrever 71.736 para setenta e um vírgula sete é um erro de três ordens de
    grandeza para quem lê em português, porque o ponto separa milhar.
    """
    if valor is None:
        return ausente
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ausente
    texto = f"{numero:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


#: Siglas de tecnologia do cadastro da ANEEL, em forma curta para filtro.
#: A sigla fica entre parênteses porque é como a fonte nomeia a tecnologia e é
#: o que alguém do setor procura; o nome vem antes porque é o que permite
#: escolher a quem não conhece a sigla.
TECNOLOGIAS: dict[str, str] = {
    "UFV": "Solar fotovoltaica",
    "EOL": "Eólica",
    "UHE": "Hidrelétrica",
    "PCH": "Pequena central hidrelétrica",
    "CGH": "Central geradora hidrelétrica",
    "UTE": "Termelétrica",
    "CGU": "Central geradora undi-elétrica",
    "UTN": "Termonuclear",
}

#: Classes de consumo da geração distribuída, como a ANEEL as escreve.
#: REBR aparece no arquivo oficial sem definição no dicionário publicado, então
#: fica como está: inventar o significado seria pior que admitir que falta.
CLASSES_DE_CONSUMO: dict[str, str] = {
    "REBR": "REBR (código da ANEEL, sem definição publicada)",
}

#: Faixas de potência definidas pela ANEEL para a geração distribuída.
PORTES: dict[str, str] = {
    "Microgeracao": "Microgeração (até 75 kW)",
    "Minigeracao": "Minigeração (acima de 75 kW)",
}

#: Valor que o cadastro traz em branco.
SEM_INFORMACAO = "Não informada no cadastro"


def rotulo_tecnologia(sigla: object) -> str:
    """«UFV» vira «Solar fotovoltaica (UFV)», para o filtro ser escolhível.

    Sigla sozinha em uma lista suspensa não deixa escolher quem não é do
    setor, e era o que a página mostrava.
    """
    bruto = str(sigla or "").strip()
    if not bruto or bruto == "(vazio)":
        return SEM_INFORMACAO
    nome = TECNOLOGIAS.get(bruto.upper())
    return f"{nome} ({bruto.upper()})" if nome else bruto


def rotulo_classe_consumo(valor: object) -> str:
    """Classe de consumo como a tela deve mostrar."""
    bruto = str(valor or "").strip()
    if not bruto or bruto == "(vazio)":
        return SEM_INFORMACAO
    return CLASSES_DE_CONSUMO.get(bruto, bruto)


def rotulo_porte(valor: object) -> str:
    """Faixa de potência com o limite explícito."""
    bruto = str(valor or "").strip()
    if not bruto or bruto == "(vazio)":
        return SEM_INFORMACAO
    return PORTES.get(bruto, bruto)
