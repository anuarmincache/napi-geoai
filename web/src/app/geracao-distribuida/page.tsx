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
import { Energia, PropsMunicipio, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

const INDICADORES = [
  { id: "mw", rotulo: "Potência instalada", unidade: "MW", cor: "#fcc817" },
  { id: "n", rotulo: "Instalações", unidade: "instalações", cor: "#5b8a3a" },
  {
    id: "uc_credito",
    rotulo: "Unidades que recebem crédito",
    unidade: "UCs",
    cor: "#73a535",
  },
] as const;

export default function GeracaoDistribuida() {
  const energia = useDados<Energia>("energia.json");
  const malha = useDados<Malha>("municipios.geojson");
  const [indicador, setIndicador] = useState<string>("mw");
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const mmgd = energia.dados?.mmgd ?? null;
  const meta = INDICADORES.find((i) => i.id === indicador) ?? INDICADORES[0];

  const valores = useMemo(() => {
    const saida: Record<string, number | null> = {};
    for (const m of mmgd?.municipios ?? []) {
      const bruto = m[meta.id as "mw" | "n" | "uc_credito"];
      saida[m.cd] = bruto === null || bruto === undefined ? null : Number(bruto);
    }
    return saida;
  }, [mmgd, meta.id]);

  const porClasse: EChartsOption = useMemo(() => {
    const entradas = Object.entries(mmgd?.totais.por_classe ?? {}).sort(
      (a, b) => b[1] - a[1],
    );
    const principais = entradas.slice(0, 6);
    const resto = entradas.slice(6).reduce((s, [, v]) => s + v, 0);
    const dados = resto
      ? [...principais, ["Outras classes", resto] as [string, number]]
      : principais;
    return {
      ...BASE_ECHARTS,
      tooltip: {
        ...BASE_ECHARTS.tooltip,
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (v) => `${num(Number(v))} instalações`,
      },
      grid: { left: 8, right: 70, top: 8, bottom: 8, containLabel: true },
      xAxis: {
        type: "value",
        axisLabel: {
          color: "#5b6b60",
          fontSize: 11,
          formatter: (v: number) => `${num(v / 1000)} mil`,
        },
        splitLine: { lineStyle: { color: "#eef3ea" } },
      },
      yAxis: {
        type: "category",
        data: dados.map(([nome]) => nome).reverse(),
        axisLabel: { color: "#5b6b60", fontSize: 11 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#e3eadd" } },
      },
      series: [
        {
          type: "bar",
          data: dados.map(([, v]) => v).reverse(),
          barWidth: 15,
          itemStyle: { color: "#5b8a3a", borderRadius: [0, 6, 6, 0] },
          label: {
            show: true,
            position: "right",
            color: "#5b6b60",
            fontSize: 11,
            formatter: ({ value }) => num(Number(value)),
          },
        },
      ],
    };
  }, [mmgd]);

  const porTipo = useMemo(
    () =>
      Object.entries(mmgd?.totais.por_tipo ?? {}).sort((a, b) => b[1] - a[1]),
    [mmgd],
  );

  if (energia.erro || (!energia.carregando && !mmgd)) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Energia"
          titulo="Solar e geração distribuída"
          descricao="Micro e minigeração distribuída (MMGD) por município, segundo a ANEEL."
        />
        <Indisponivel detalhe="O painel de geração distribuída não está disponível." />
      </Pagina>
    );
  }

  return (
    <Pagina>
      <CabecalhoPagina
        secao="Energia"
        titulo="Solar e geração distribuída"
        descricao="Sistemas pequenos, quase todos solares, instalados em casas, comércios e propriedades rurais. Os números são de potência instalada, não de energia gerada."
      >
        {mmgd && (
          <div className="flex flex-wrap gap-2">
            <Badge variant="escuro">Retrato de {mmgd.periodo}</Badge>
            <Badge variant="escuro">Fonte: ANEEL MMGD</Badge>
            <Badge variant="escuro">Não se soma às usinas da ANEEL SIGA</Badge>
          </div>
        )}
      </CabecalhoPagina>

      {mmgd ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Numero
            rotulo="Potência instalada conhecida"
            valor={`${num(mmgd.totais.mw / 1000, 2)} GW`}
            detalhe={`${num(mmgd.totais.mw, 1)} MW somados`}
          />
          <Numero
            rotulo="Instalações"
            valor={num(mmgd.totais.instalacoes)}
            detalhe="empreendimentos cadastrados"
          />
          <Numero
            rotulo="Unidades que recebem crédito"
            valor={num(mmgd.totais.uc_credito)}
            detalhe="não substitui a contagem de instalações"
          />
        </div>
      ) : (
        <Carregando altura="h-28" />
      )}

      <section>
        <SecaoTitulo
          titulo="Onde está instalada"
          descricao="Escolha o indicador e clique em um município para destacá-lo na tabela."
        />
        <div className="mb-3 flex flex-wrap gap-2">
          {INDICADORES.map((i) => (
            <Button
              key={i.id}
              size="sm"
              variant={i.id === indicador ? "default" : "outline"}
              onClick={() => setIndicador(i.id)}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: i.cor }}
              />
              {i.rotulo}
            </Button>
          ))}
        </div>
        <Card className="overflow-hidden p-0">
          {malha.dados && mmgd ? (
            <MapaMunicipios
              malha={malha.dados}
              valores={valores}
              rotulo={meta.rotulo}
              unidade={meta.unidade}
              cor={meta.cor}
              selecionado={selecionado}
              onSelecionar={setSelecionado}
            />
          ) : (
            <Carregando altura="h-[520px]" />
          )}
          <CardFooter className="flex flex-wrap items-center justify-between gap-2">
            <span>
              Potência instalada conhecida de MMGD por município. Fonte: ANEEL
              MMGD, {mmgd?.periodo}. Município sem registro aparece em cinza.
            </span>
            <ClasseBadge classe="A" />
          </CardFooter>
        </Card>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex items-start justify-between gap-3">
            <CardTitle>Instalações por classe de consumo</CardTitle>
            <ClasseBadge classe="A" />
          </CardHeader>
          <CardContent>
            {mmgd ? (
              <Grafico option={porClasse} className="h-72 w-full" />
            ) : (
              <Carregando altura="h-72" />
            )}
          </CardContent>
          <CardFooter>
            Contagem de empreendimentos, não de unidades consumidoras.
          </CardFooter>
        </Card>

        <Card>
          <CardHeader className="flex items-start justify-between gap-3">
            <CardTitle>Instalações por tecnologia</CardTitle>
            <ClasseBadge classe="A" />
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {porTipo.map(([sigla, qtd]) => (
                <li key={sigla} className="flex items-center gap-3">
                  <span className="w-12 shrink-0 font-display text-sm font-bold text-forest">
                    {sigla}
                  </span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-paper">
                    <div
                      className="h-full rounded-full bg-sun"
                      style={{
                        width: `${(qtd / (porTipo[0]?.[1] || 1)) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="w-20 shrink-0 text-right text-sm font-semibold text-ink">
                    {num(qtd)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
          <CardFooter>
            UFV é solar fotovoltaica. Siglas conforme o cadastro da ANEEL.
          </CardFooter>
        </Card>
      </div>

      <section>
        <SecaoTitulo
          titulo="Todos os municípios"
          descricao="Busque, ordene e exporte. A ordenação é descritiva, não é ranking de aptidão."
        />
        {mmgd ? (
          <TabelaMunicipios
            linhas={mmgd.municipios.map((m) => ({
              cd: m.cd,
              nome: m.nome,
              valores: {
                "Instalações": m.n,
                "Potência (MW)": m.mw,
                "UCs com crédito": m.uc_credito,
              },
            }))}
            colunas={["Instalações", "Potência (MW)", "UCs com crédito"]}
            casas={{ "Potência (MW)": 1 }}
            selecionado={selecionado}
            onSelecionar={setSelecionado}
            nomeArquivo="napi_geoai_mmgd"
          />
        ) : (
          <Carregando altura="h-96" />
        )}
      </section>

      {mmgd && (
        <Avisos
          itens={[
            ...(mmgd.nota_temporal ? [mmgd.nota_temporal] : []),
            ...mmgd.avisos,
          ]}
        />
      )}
    </Pagina>
  );
}

function Numero({
  rotulo,
  valor,
  detalhe,
}: {
  rotulo: string;
  valor: string;
  detalhe: string;
}) {
  return (
    <Card className="px-5 py-4">
      <p className="font-display text-[11px] font-bold tracking-[0.12em] text-muted uppercase">
        {rotulo}
      </p>
      <p className="mt-1.5 font-display text-[1.9rem] leading-none font-bold text-forest">
        {valor}
      </p>
      <p className="mt-2 text-sm text-muted">{detalhe}</p>
    </Card>
  );
}
