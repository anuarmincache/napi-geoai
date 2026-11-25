"""Municípios parecidos: vizinhos mais próximos em um espaço declarado.

O que isto é
------------
Uma conta determinística. Cada município vira um ponto em um espaço de poucas
variáveis oficiais, todas padronizadas, e a semelhança é a distância euclidiana
entre dois pontos. Mesmo arquivo de entrada, mesmo resultado, sempre.

O que isto não é
----------------
Não é ranking de aptidão, não é recomendação e não diz que um município deveria
imitar o outro. Dois municípios parecidos nestas variáveis podem ser muito
diferentes em tudo o que não está aqui.

Por que estas variáveis
-----------------------
Entram apenas variáveis publicadas para os 399 municípios e em que o valor zero
significa zero de verdade. A potência de usinas da ANEEL SIGA fica de fora de
propósito: 276 municípios aparecem como «sem empreendimento», que no cadastro
significa nenhuma usina georreferenciada e vinculada, não ausência comprovada.
Tratar isso como zero seria inventar informação para fechar a conta.

Transformação
-------------
População, área e densidade variam por ordens de grandeza, então entram em
log10(x + 1); sem isso Curitiba sozinha domina a distância. Os percentuais de
cobertura e a potência por habitante entram como estão. Depois disso toda
variável é padronizada (z = (x - média) / desvio padrão), para que nenhuma pese
mais que outra por causa da unidade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

#: Limiar de |Δz| abaixo do qual a variável conta como ponto de semelhança.
LIMIAR_PARECIDO = 0.5
#: Limiar de |Δz| acima do qual a variável conta como ponto de diferença.
LIMIAR_DIFERENTE = 1.5


@dataclass(frozen=True, slots=True)
class Variavel:
    """Uma dimensão do espaço de comparação, com origem e tratamento declarados."""

    chave: str
    rotulo_pt: str
    unidade: str
    fonte_pt: str
    logaritmica: bool = False


#: Ordem fixa. Mudar esta tupla muda o resultado, então ela é parte do método.
VARIAVEIS: tuple[Variavel, ...] = (
    Variavel("populacao", "População", "hab", "IBGE, estimativa 2026", True),
    Variavel("area_km2", "Área", "km²", "IBGE, Malha Municipal 2025", True),
    Variavel("densidade", "Densidade", "hab/km²", "IBGE, cálculo", True),
    Variavel("agricultura", "Agricultura", "% da área mapeada", "MapBiomas Coleção 11"),
    Variavel("floresta", "Floresta", "% da área mapeada", "MapBiomas Coleção 11"),
    Variavel("pastagem", "Pastagem", "% da área mapeada", "MapBiomas Coleção 11"),
    Variavel(
        "mmgd_kw_hab",
        "Geração distribuída por habitante",
        "kW/hab",
        "ANEEL MMGD ÷ IBGE",
    ),
)

FORMULA_PT = (
    "distância = raiz da soma dos quadrados das diferenças padronizadas "
    "das sete variáveis"
)


@dataclass(frozen=True, slots=True)
class Vizinho:
    """Um município parecido, com a conta aberta variável por variável."""

    cd_mun: str
    nome: str
    distancia: float
    parecido_em: tuple[str, ...] = field(default=())
    diferente_em: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class IndiceSimilaridade:
    """Espaço padronizado pronto para consulta."""

    z: dict[str, tuple[float, ...]]
    nomes: dict[str, str]
    brutos: dict[str, dict[str, float]]
    variaveis: tuple[Variavel, ...] = VARIAVEIS

    @property
    def total(self) -> int:
        return len(self.z)


class DadosInsuficientes(ValueError):
    """Levantada quando falta variável para montar o índice. Falha fechada."""


def construir_indice(
    linhas: dict[str, dict[str, Any]],
    *,
    variaveis: tuple[Variavel, ...] = VARIAVEIS,
) -> IndiceSimilaridade:
    """Monta o espaço padronizado.

    ``linhas`` é ``{código IBGE: {"nome": str, <chave da variável>: número}}``.
    Município com qualquer variável ausente fica de fora do índice, em vez de
    receber zero no lugar do dado que falta.
    """
    if not linhas:
        raise DadosInsuficientes("nenhum município recebido")

    completos: dict[str, dict[str, float]] = {}
    nomes: dict[str, str] = {}
    for cd, linha in linhas.items():
        valores: dict[str, float] = {}
        for var in variaveis:
            valor = linha.get(var.chave)
            if valor is None or not isinstance(valor, int | float):
                break
            valor = float(valor)
            if not math.isfinite(valor):
                break
            valores[var.chave] = valor
        else:
            completos[str(cd)] = valores
            nomes[str(cd)] = str(linha.get("nome") or cd)

    if len(completos) < 2:
        raise DadosInsuficientes(
            f"são necessários ao menos 2 municípios completos, há {len(completos)}"
        )

    def tratada(var: Variavel, valor: float) -> float:
        if not var.logaritmica:
            return valor
        if valor < 0:
            raise DadosInsuficientes(
                f"valor negativo em {var.chave}, incompatível com log10"
            )
        return math.log10(valor + 1.0)

    brutos_tratados = {
        cd: {v.chave: tratada(v, valores[v.chave]) for v in variaveis}
        for cd, valores in completos.items()
    }
    n = len(brutos_tratados)
    media = {
        v.chave: sum(b[v.chave] for b in brutos_tratados.values()) / n
        for v in variaveis
    }
    desvio = {}
    for v in variaveis:
        soma = sum((b[v.chave] - media[v.chave]) ** 2 for b in brutos_tratados.values())
        desvio[v.chave] = max(math.sqrt(soma / n), 1e-9)

    z = {
        cd: tuple((b[v.chave] - media[v.chave]) / desvio[v.chave] for v in variaveis)
        for cd, b in brutos_tratados.items()
    }
    return IndiceSimilaridade(z=z, nomes=nomes, brutos=completos, variaveis=variaveis)


def municipios_parecidos(
    indice: IndiceSimilaridade, cd_mun: str, *, quantidade: int = 5
) -> list[Vizinho]:
    """Os ``quantidade`` municípios mais próximos, do mais parecido para o menos.

    O empate é desfeito pelo código IBGE, para que a ordem seja reproduzível.
    """
    cd_mun = str(cd_mun)
    base = indice.z.get(cd_mun)
    if base is None:
        return []

    candidatos: list[tuple[float, str]] = []
    for outro, vetor in indice.z.items():
        if outro == cd_mun:
            continue
        soma = sum((a - b) ** 2 for a, b in zip(base, vetor, strict=True))
        candidatos.append((math.sqrt(soma), outro))
    candidatos.sort(key=lambda item: (item[0], item[1]))

    saida: list[Vizinho] = []
    for distancia, outro in candidatos[: max(0, quantidade)]:
        delta = [
            (abs(a - b), var)
            for a, b, var in zip(base, indice.z[outro], indice.variaveis, strict=True)
        ]
        saida.append(
            Vizinho(
                cd_mun=outro,
                nome=indice.nomes[outro],
                distancia=round(distancia, 3),
                parecido_em=tuple(v.rotulo_pt for d, v in delta if d < LIMIAR_PARECIDO),
                diferente_em=tuple(
                    v.rotulo_pt for d, v in delta if d > LIMIAR_DIFERENTE
                ),
            )
        )
    return saida


def nota_isolamento_pt(vizinhos: list[Vizinho]) -> str | None:
    """Avisa quando nem o vizinho mais próximo está perto.

    A distância é informação: se o município mais parecido ainda está longe, o
    método está dizendo que não há semelhante no estado, e a tela precisa dizer
    isso em vez de apresentar o primeiro da lista como se fosse um par.
    """
    if not vizinhos:
        return None
    if vizinhos[0].distancia <= 2.5:
        return None
    return (
        "Nenhum município do Paraná fica próximo neste conjunto de variáveis. "
        "A lista traz os menos distantes, não equivalentes."
    )


def linhas_dos_paineis(
    *,
    populacao: Any,
    cobertura: Any,
    mmgd: Any,
    ano_cobertura: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Monta a entrada de :func:`construir_indice` a partir dos painéis do portal.

    Lê apenas artefatos já preparados e conferidos. Município sem alguma das
    variáveis entra com ``None`` e é descartado por ``construir_indice``, que
    falha fechada em vez de completar o que falta.
    """
    from geoai.portal.landcover_panel import landcover_share

    ano = ano_cobertura or (cobertura.panel["years"][-1] if cobertura.available else 0)
    mmgd_por_cd = (
        {str(r["cd_mun"]): r for r in mmgd.panel["municipalities"]}
        if getattr(mmgd, "available", False)
        else {}
    )

    linhas: dict[str, dict[str, Any]] = {}
    for registro in populacao.panel["municipalities"]:
        cd = str(registro["CD_MUN"])
        habitantes = registro.get("populacao_estimada_2026_hab")
        area = registro.get("area_km2_ibge_2025")
        densidade = registro.get("densidade_demografica_estimada_2026_hab_km2")
        registro_mmgd = mmgd_por_cd.get(cd)
        kw = (
            registro_mmgd.get("potencia_instalada_kw_conhecida")
            if registro_mmgd
            else None
        )
        linhas[cd] = {
            "nome": registro.get("NM_MUN") or cd,
            "populacao": habitantes,
            "area_km2": area,
            "densidade": densidade,
            "agricultura": landcover_share(cobertura, cd, "agricultura", ano),
            "floresta": landcover_share(cobertura, cd, "formacao_florestal", ano),
            "pastagem": landcover_share(cobertura, cd, "pastagem", ano),
            "mmgd_kw_hab": (
                float(kw) / float(habitantes) if kw is not None and habitantes else None
            ),
        }
    return linhas
