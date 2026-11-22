"use client";

import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import type { FeatureCollection, Geometry } from "geojson";
import { MapaMunicipios } from "@/components/mapa-municipios";
import { Grafico, BASE_ECHARTS } from "@/components/grafico";
import {
  Avisos,
  CabecalhoPagina,
  Carregando,
  Indisponivel,
  Pagina,
  SecaoTitulo,
} from "@/components/pagina";
import { TabelaMunicipios } from "@/components/tabela-municipios";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge, ClasseBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Cobertura, PropsMunicipio, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

export default function CoberturaPagina() {
  const cob = useDados<Cobertura>("cobertura.json");
  const malha = useDados<Malha>("municipios.geojson");
  const [grupo, setGrupo] = useState("formacao_florestal");
  const [ano, setAno] = useState<number | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const dados = cob.dados;
  const anoAtual = ano ?? dados?.ultimo_ano ?? 2025;
  const meta = dados?.grupos.find((g) => g.chave === grupo) ?? dados?.grupos[0];

  const valores = useMemo(() => {
    const saida: Record<string, number | null> = {};
    if (!dados) return saida;
    for (const [cd, linha] of Object.entries(dados.municipios)) {
      const pct = linha.pct[String(anoAtual)]?.[grupo];
      saida[cd] = pct === undefined ? null : pct;
    }
    return saida;
  }, [dados, grupo, anoAtual]);

  const serieEstado: EChartsOption | null = useMemo(() => {
    if (!dados) return null;
    return {
      ...BASE_ECHARTS,
      tooltip: {
        ...BASE_ECHARTS.tooltip,
        trigger: "axis",
        valueFormatter: (v) => `${num(Number(v) / 1000)} mil ha`,
      },
      legend: {
        bottom: 0,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "#5b6b60", fontSize: 11 },
      },
      grid: { left: 8, right: 16, top: 16, bottom: 56, containLabel: true },
      xAxis: {
        type: "category",
        data: dados.anos.map(String),
        axisLabel: { color: "#5b6b60", fontSize: 11 },
        axisLine: { lineStyle: { color: "#e3eadd" } },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#5b6b60",
          fontSize: 11,
          formatter: (v: number) => `${num(v / 1_000_000, 1)} mi ha`,
        },
        splitLine: { lineStyle: { color: "#eef3ea" } },
      },
      series: dados.grupos.map((g) => ({
        name: g.nome,
        type: "line",
        stack: "total",
        areaStyle: { opacity: 0.85 },
        lineStyle: { width: 0 },
        showSymbol: false,
        emphasis: { focus: "series" },
        itemStyle: { color: g.cor },
        data: dados.anos.map((a) => dados.estado[String(a)]?.[g.chave] ?? 0),
      })),
    };
  }, [dados]);

  const composicao = useMemo(() => {
    if (!dados) return [];
    const fonte = selecionado
      ? dados.municipios[selecionado]?.pct[String(anoAtual)]
      : null;
    if (selecionado && fonte) {
      return dados.grupos.map((g) => ({ ...g, pct: fonte[g.chave] ?? 0 }));
    }
    const totais = dados.estado[String(anoAtual)] ?? {};
    const soma = Object.values(totais).reduce((s, v) => s + v, 0) || 1;
    return dados.grupos.map((g) => ({
      ...g,
      pct: ((totais[g.chave] ?? 0) / soma) * 100,
    }));
  }, [dados, selecionado, anoAtual]);

  if (cob.erro || (!cob.carregando && !dados)) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Território"
          titulo="Cobertura e uso da terra"
          descricao="Floresta, agricultura, pastagem e área urbana nos 399 municípios."
        />
        <Indisponivel detalhe="O painel do MapBiomas não está disponível." />
      </Pagina>
    );
  }

  const nomeEscopo = selecionado
    ? (malha.dados?.features.find((f) => f.properties.cd === selecionado)
        ?.properties.nome ?? selecionado)
    : "Paraná";

  return (
    <Pagina>
      <CabecalhoPagina
        secao="Território"
        titulo="Cobertura e uso da terra"
        descricao="O que cobre o solo de cada município, de 1985 a 2025, mapeado por satélite. A diferença entre dois anos é variação de estoque, não taxa de desmatamento."
      >
        {dados && (
          <div className="flex flex-wrap gap-2">
            <Badge variant="escuro">MapBiomas Coleção {dados.colecao}</Badge>
            <Badge variant="escuro">Landsat, 30 m</Badge>
            <Badge variant="escuro">Floresta mapeada não é área protegida</Badge>
          </div>
        )}
      </CabecalhoPagina>

      <section>
        <SecaoTitulo
          titulo="Mapa por classe e ano"
          descricao="O percentual é sobre a área mapeada do município, não sobre a área oficial do IBGE."
        />
        <div className="mb-3 flex flex-wrap gap-2">
          {dados?.grupos.map((g) => (
            <Button
              key={g.chave}
              size="sm"
              variant={g.chave === grupo ? "default" : "outline"}
              onClick={() => setGrupo(g.chave)}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: g.cor }}
              />
              {g.nome}
            </Button>
          ))}
        </div>
        {dados && (
          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-semibold text-muted">Ano:</span>
            {dados.anos.map((a) => (
              <button
                key={a}
                onClick={() => setAno(a)}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
                  a === anoAtual
                    ? "bg-forest text-white"
                    : "border border-line bg-white text-muted hover:text-forest"
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        )}

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="overflow-hidden p-0">
            {malha.dados && meta ? (
              <MapaMunicipios
                malha={malha.dados}
                valores={valores}
                rotulo={`${meta.nome} · ${anoAtual}`}
                unidade="% da área mapeada"
                cor={meta.cor}
                casas={1}
                selecionado={selecionado}
                onSelecionar={setSelecionado}
              />
            ) : (
              <Carregando altura="h-[520px]" />
            )}
            <CardFooter className="flex flex-wrap items-center justify-between gap-2">
              <span>
                Percentual derivado: hectares da classe ÷ área mapeada do
                município. Fonte: MapBiomas Coleção {dados?.colecao}.
              </span>
              <ClasseBadge classe="B" />
            </CardFooter>
          </Card>

          <Card className="px-5 py-5">
            <p className="font-display text-sm font-bold text-forest">
              Composição em {anoAtual}: {nomeEscopo}
            </p>
            <div className="mt-3 flex h-3 overflow-hidden rounded-full">
              {composicao
                .filter((c) => c.pct > 0)
                .map((c) => (
                  <div
                    key={c.chave}
                    title={`${c.nome}: ${num(c.pct, 1)}%`}
                    style={{ width: `${c.pct}%`, background: c.cor }}
                  />
                ))}
            </div>
            <ul className="mt-3 space-y-1.5">
              {[...composicao]
                .sort((a, b) => b.pct - a.pct)
                .map((c) => (
                  <li
                    key={c.chave}
                    className="flex items-center justify-between text-xs text-ink"
                  >
                    <span className="flex items-center gap-1.5">
                      <span
                        className="h-2 w-2 rounded-sm"
                        style={{ background: c.cor }}
                      />
                      {c.nome}
                    </span>
                    <span className="font-semibold tabular-nums">
                      {num(c.pct, 1)}%
                    </span>
                  </li>
                ))}
            </ul>
            {selecionado && dados?.municipios[selecionado] && (
              <p className="mt-3 border-t border-line pt-3 text-[11px] leading-snug text-muted">
                Área mapeada:{" "}
                {num(dados.municipios[selecionado].ha_mapeada / 100, 1)} km².
                Área oficial IBGE:{" "}
                {num(dados.municipios[selecionado].area_ibge_km2, 1)} km².
                Diferença:{" "}
                {num(dados.municipios[selecionado].delta_ibge * 100, 2)}%. Os
                hectares não foram reescalados.
              </p>
            )}
          </Card>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex items-start justify-between gap-3">
            <CardTitle>O Paraná de {dados?.anos[0]} a {dados?.ultimo_ano}</CardTitle>
            <ClasseBadge classe="A" />
          </CardHeader>
          <CardContent>
            {serieEstado ? (
              <Grafico option={serieEstado} className="h-80 w-full" />
            ) : (
              <Carregando altura="h-80" />
            )}
          </CardContent>
          <CardFooter>{dados?.regra_anos}</CardFooter>
        </Card>

        <Card>
          <CardHeader className="flex items-start justify-between gap-3">
            <CardTitle>O que mudou no estado</CardTitle>
            <ClasseBadge classe="B" />
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {[...(dados?.mudanca_estado ?? [])]
                .sort((a, b) => Math.abs(b.delta_ha) - Math.abs(a.delta_ha))
                .map((m) => (
                  <li
                    key={m.nome}
                    className="flex items-center justify-between gap-3 border-b border-line/60 pb-2 text-sm last:border-0"
                  >
                    <span className="text-ink">{m.nome}</span>
                    <span
                      className={`font-display font-bold tabular-nums ${
                        m.delta_ha >= 0 ? "text-moss" : "text-[#b35309]"
                      }`}
                    >
                      {m.delta_ha >= 0 ? "+" : "−"}
                      {num(Math.abs(m.delta_ha))} ha
                    </span>
                  </li>
                ))}
            </ul>
          </CardContent>
          <CardFooter>
            Diferença de estoque entre {dados?.anos[0]} e {dados?.ultimo_ano}. Não
            mostra onde a mudança ocorreu e não distingue conversão de
            regeneração.
          </CardFooter>
        </Card>
      </div>

      <section>
        <SecaoTitulo
          titulo={`Todos os municípios em ${anoAtual}`}
          descricao="Percentual de cada classe sobre a área mapeada."
        />
        {dados && malha.dados ? (
          <TabelaMunicipios
            key={`${grupo}-${anoAtual}`}
            linhas={Object.entries(dados.municipios).map(([cd, linha]) => {
              const pct = linha.pct[String(anoAtual)] ?? {};
              return {
                cd,
                nome:
                  malha.dados?.features.find((f) => f.properties.cd === cd)
                    ?.properties.nome ?? cd,
                valores: Object.fromEntries(
                  dados.grupos.map((g) => [g.nome, pct[g.chave] ?? null]),
                ),
              };
            })}
            colunas={dados.grupos.map((g) => g.nome)}
            casas={Object.fromEntries(dados.grupos.map((g) => [g.nome, 1]))}
            selecionado={selecionado}
            onSelecionar={setSelecionado}
            nomeArquivo={`napi_geoai_cobertura_${anoAtual}`}
          />
        ) : (
          <Carregando altura="h-96" />
        )}
      </section>

      {dados?.qualidade && (
        <Card>
          <CardHeader>
            <CardTitle>Conferência contra a área oficial</CardTitle>
          </CardHeader>
          <CardContent className="text-sm leading-relaxed text-muted">
            A área mapeada pelo satélite e a área oficial do IBGE não coincidem
            exatamente. A diferença tem mediana de{" "}
            <strong className="text-forest">
              {num(dados.qualidade.median_abs * 100, 2)}%
            </strong>
            , chega a {num(dados.qualidade.max_abs * 100, 2)}% no caso extremo e
            passa de 1% em{" "}
            {num(dados.qualidade.municipalities_above_1_percent)} municípios.
            Nenhum hectare foi reescalado para fechar a conta.
          </CardContent>
          <CardFooter>
            {dados.fontes.map((linha, i) => (
              <p key={`${i}-${linha.slice(0, 24)}`}>{linha}</p>
            ))}
          </CardFooter>
        </Card>
      )}

      {dados && <Avisos itens={dados.avisos} />}
    </Pagina>
  );
}
