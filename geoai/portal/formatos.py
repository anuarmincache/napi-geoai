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

#: Situação de uma fonte no catálogo. O vocabulário interno é em inglês; na
#: tela ele precisa dizer, sem ambiguidade, se a fonte alimenta o site hoje.
SITUACOES_DA_FONTE: dict[str, str] = {
    "prototype": "Em uso no site",
    "catalogued": "Catalogada, ainda não coletada",
}

#: Como o arquivo da fonte é obtido. Interessa ao revisor saber se o dado vem
#: de portal de dados abertos ou de um arquivo solto em servidor.
MODOS_DE_ACESSO: dict[str, str] = {
    "http_file": "Arquivo publicado pelo órgão",
    "ckan_resource": "Portal de dados abertos do órgão",
    "gee_asset": "Coleção de imagens em nuvem",
    "ftp_or_http_index": "Índice de arquivos do órgão",
}


def situacao_da_fonte(valor: object) -> str:
    """Situação da fonte por extenso."""

    chave = str(valor or "").strip()
    return SITUACOES_DA_FONTE.get(chave, chave or SEM_INFORMACAO)


def modo_de_acesso(valor: object) -> str:
    """Forma de obtenção do arquivo, por extenso."""

    chave = str(valor or "").strip()
    return MODOS_DE_ACESSO.get(chave, chave or SEM_INFORMACAO)

#: Motivos de recusa de registro, gravados no artefato com o nome da coluna da
#: ANEEL. Na tela eles viram a frase que explica o que faltou no registro.
MOTIVOS_DE_RECUSA: dict[str, str] = {
    "CodEmpreendimento ausente": "sem código de empreendimento",
    "UF diferente de PR": "de outro estado",
    "CodMunicipioIbge inválido": "sem código de município válido",
    "CodMunicipioIbge fora do Paraná (prefixo 41)": "com município fora do Paraná",
    "MdaPotenciaInstaladaKW inválida": "sem potência instalada válida",
}


def motivos_de_recusa_pt(reasons: object) -> str:
    """Transforma a contagem por motivo em frase legível.

    O artefato guarda algo como ``{"MdaPotenciaInstaladaKW inválida": 6}``.
    Despejar esse dicionário na tela mostra nome de coluna e chave de
    programação a quem só quer saber o que foi descartado e por quê.
    """

    if not isinstance(reasons, dict) or not reasons:
        return "sem detalhamento por motivo"
    partes = [
        f"{numero_br(quantos)} {MOTIVOS_DE_RECUSA.get(str(chave), str(chave))}"
        for chave, quantos in sorted(
            reasons.items(), key=lambda item: item[1] or 0, reverse=True
        )
    ]
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " e " + partes[-1]


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
