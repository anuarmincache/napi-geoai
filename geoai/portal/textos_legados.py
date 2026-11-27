"""Reescrita de avisos antigos gravados nos artefatos.

Os artefatos em ``data/derived`` guardam os avisos em português com a redação
vigente na data da coleta. Quando a redação melhora, o texto novo só chega ao
artefato na próxima coleta, que depende de rede e de nova validação.

Este módulo faz a ponte: a camada de apresentação troca a redação antiga pela
atual na hora de exibir, sem tocar no artefato e sem reprocessar nada. Cada
entrada aqui é temporária e sai quando o artefato correspondente é refeito.
"""

from __future__ import annotations

import re

#: Trechos que identificam uma redação antiga, com o texto que a substitui.
#: A chave é um pedaço estável do aviso antigo, suficiente para reconhecê-lo.
SUBSTITUICOES: tuple[tuple[str, str], ...] = (
    (
        # Marcador longo de propósito: outras notas do mesmo artefato começam
        # com "Zero vinculado" e falam de outra coisa.
        "Zero vinculado ≠ ausência absoluta",
        "{n} empreendimentos da ANEEL em operação não puderam ser associados "
        "a um município, por coordenada ausente, inválida ou fora da malha do "
        "Paraná. Município sem empreendimento vinculado não é município sem "
        "usina: é município onde nenhuma usina georreferenciada foi associada "
        "ao polígono.",
    ),
    (
        "MMGD excluído; MW ≠ MWh",
        "Recorte: geração centralizada da ANEEL na fase de operação. Não "
        "inclui a geração distribuída. Potência fiscalizada, medida em MW, "
        "não é energia gerada, que se mede em MWh. Onde aparece zero, "
        "significa que nenhuma usina georreferenciada foi associada ao "
        "município.",
    ),
    (
        "Ausência ≠ zero",
        "Capacidade fiscalizada ou outorgada em MW, considerando apenas "
        "valores conhecidos e não negativos. Dado ausente não é zero. Não é "
        "energia gerada, que se mede em MWh, e não inclui a geração "
        "distribuída.",
    ),
    (
        "DthAtualizaCadastralEmpreend",
        "A data de atualização do cadastro não é a data em que a instalação "
        "entrou em operação, e o arquivo é um retrato de um período de "
        "referência. Por isso os anos do cadastro não mostram o crescimento "
        "histórico das conexões.",
    ),
    (
        "CodEmpreendimento",
        "A contagem principal é de instalações cadastradas, uma por "
        "empreendimento registrado.",
    ),
    (
        "QtdUCRecebeCredito",
        "Unidades que recebem crédito são consumidores beneficiados pela "
        "energia, não instalações. Um mesmo sistema pode dividir crédito com "
        "várias unidades.",
    ),
    (
        "Campos pessoais",
        "Dados pessoais do titular (CPF, CNPJ, nome, CEP e coordenadas de "
        "subestação) foram excluídos deste arquivo.",
    ),
    (
        "AREA_KM2",
        "Densidade estimada = população do IBGE em 01/07/2026 dividida pela "
        "área oficial da Malha Municipal do IBGE de 2025. As duas referências "
        "são de anos diferentes, então este número não é a densidade "
        "censitária oficial.",
    ),
    (
        "fase Operação; MMGD excluído",
        "Usinas de grande porte em operação, no cadastro da ANEEL. Não inclui "
        "a geração distribuída. Potência em MW não é energia gerada em MWh, e "
        "zero significa nenhuma usina localizada e vinculada ao município.",
    ),
    (
        "MMGD não é SIGA",
        "Geração distribuída e geração centralizada são dois cadastros "
        "diferentes da ANEEL e não se somam.",
    ),
    (
        "Potência instalada (kW/MW)",
        "Potência instalada (kW e MW) não é energia gerada (MWh).",
    ),
    (
        "join QGIS",
        "{n} usinas da fase não têm município associado, porque a "
        "coordenada do cadastro está ausente, é inválida ou cai fora da malha "
        "municipal. Elas entram no total do estado e ficam de fora do mapa. "
        "Município sem usina no mapa significa nenhuma usina georreferenciada "
        "e vinculada, não ausência comprovada.",
    ),
)


def atualizar(texto: str | None) -> str | None:
    """Devolve a redação atual do aviso, ou o próprio texto se já estiver em dia.

    Quando a redação nova traz ``{n}``, o número que abria o aviso antigo é
    preservado, para não perder a contagem que o texto original carregava.
    """
    if not texto:
        return texto
    for marca, novo in SUBSTITUICOES:
        if marca not in texto:
            continue
        if "{n}" not in novo:
            return novo
        achado = re.match(r"\s*(\d+)", texto)
        return novo.replace("{n}", achado.group(1) if achado else "Algumas")
    return texto


def atualizar_lista(avisos: object) -> list[str]:
    """Aplica :func:`atualizar` a uma lista de avisos, sem repetir resultados."""
    saida: list[str] = []
    for item in list(avisos or []):
        novo = atualizar(str(item))
        if novo and novo not in saida:
            saida.append(novo)
    return saida
