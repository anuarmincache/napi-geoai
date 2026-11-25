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
