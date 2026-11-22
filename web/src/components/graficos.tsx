"use client";

import type { EChartsOption } from "echarts";
import { Grafico, BASE_ECHARTS } from "@/components/grafico";
import { Series, nomeTecnologia, num } from "@/lib/dados";

const EIXO = {
  axisLine: { lineStyle: { color: "#e3eadd" } },
  axisTick: { show: false },
  axisLabel: { color: "#5b6b60", fontSize: 11 },
  splitLine: { lineStyle: { color: "#eef3ea" } },
};

export function CoberturaNoTempo({ series }: { series: Series }) {
  const dados = series.cobertura;
  if (!dados) return <SemDado texto="Cobertura da terra indisponível." />;
  const option: EChartsOption = {
    ...BASE_ECHARTS,
    tooltip: {
      ...BASE_ECHARTS.tooltip,
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: "#a8cf5f" } },
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
    xAxis: { type: "category", data: dados.anos.map(String), ...EIXO },
    yAxis: {
      type: "value",
      ...EIXO,
      axisLabel: {
        ...EIXO.axisLabel,
        formatter: (v: number) => `${num(v / 1_000_000, 1)} mi ha`,
      },
    },
    series: dados.series.map((s) => ({
      name: s.nome,
      type: "line",
      stack: "total",
      areaStyle: { opacity: 0.85 },
      lineStyle: { width: 0 },
      showSymbol: false,
      emphasis: { focus: "series" },
      itemStyle: { color: s.cor },
      data: s.ha,
    })),
  };
  return <Grafico option={option} className="h-72 w-full" />;
}

export function ClassesMmgd({ series }: { series: Series }) {
  const bruto = series.mmgd_classes;
  if (!bruto) return <SemDado texto="Geração distribuída indisponível." />;
  // Cinco maiores classes, o restante somado em "Outras classes".
  const principais = bruto.slice(0, 5);
  const resto = bruto.slice(5).reduce((soma, d) => soma + d.valor, 0);
  const dados = resto
    ? [...principais, { nome: "Outras classes", valor: resto }]
    : principais;
  const cores = ["#2f4a33", "#5b8a3a", "#a8cf5f", "#fcc817", "#73a535", "#c9d6c1"];
  const option: EChartsOption = {
    ...BASE_ECHARTS,
    tooltip: {
      ...BASE_ECHARTS.tooltip,
      trigger: "item",
      valueFormatter: (v) => `${num(Number(v))} instalações`,
    },
    legend: {
      bottom: 0,
      icon: "circle",
      itemWidth: 9,
      itemHeight: 9,
      textStyle: { color: "#5b6b60", fontSize: 11 },
    },
    series: [
      {
        type: "pie",
        radius: ["52%", "76%"],
        center: ["50%", "44%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "#fff", borderWidth: 2 },
        label: { show: false },
        data: dados.map((d, i) => ({
          name: d.nome,
          value: d.valor,
          itemStyle: { color: cores[i % cores.length] },
        })),
      },
    ],
  };
  return <Grafico option={option} className="h-64 w-full" />;
}

export function TecnologiaSiga({ series }: { series: Series }) {
  const dados = series.siga_tecnologia;
  if (!dados) return <SemDado texto="Usinas em operação indisponíveis." />;
  const ordenado = [...dados].reverse();
  const option: EChartsOption = {
    ...BASE_ECHARTS,
    tooltip: {
      ...BASE_ECHARTS.tooltip,
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v) => `${num(Number(v), 1)} MW`,
    },
    grid: { left: 8, right: 44, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: "value",
      ...EIXO,
      axisLabel: {
        ...EIXO.axisLabel,
        formatter: (v: number) => (v >= 1000 ? `${num(v / 1000, 0)} mil` : num(v)),
      },
    },
    yAxis: {
      type: "category",
      data: ordenado.map((d) => nomeTecnologia(d.nome)),
      ...EIXO,
      splitLine: { show: false },
    },
    series: [
      {
        type: "bar",
        data: ordenado.map((d) => d.mw),
        barWidth: 14,
        itemStyle: { color: "#73a535", borderRadius: [0, 6, 6, 0] },
        label: {
          show: true,
          position: "right",
          color: "#5b6b60",
          fontSize: 11,
          formatter: ({ value }) => `${num(Number(value), 1)} MW`,
        },
      },
    ],
  };
  return <Grafico option={option} className="h-64 w-full" />;
}

export function Lavouras({ series }: { series: Series }) {
  const dados = series.lavouras;
  if (!dados) return <SemDado texto="Dados de lavoura indisponíveis." />;
  const ordenado = [...dados].slice(0, 6).reverse();
  const option: EChartsOption = {
    ...BASE_ECHARTS,
    tooltip: {
      ...BASE_ECHARTS.tooltip,
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v) => `${num(Number(v))} ha plantados`,
    },
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: "value",
      ...EIXO,
      axisLabel: {
        ...EIXO.axisLabel,
        formatter: (v: number) => `${num(v / 1_000_000, 1)} mi`,
      },
    },
    yAxis: {
      type: "category",
      data: ordenado.map((d) => d.nome.split(" (")[0]),
      ...EIXO,
      splitLine: { show: false },
    },
    series: [
      {
        type: "bar",
        data: ordenado.map((d) => d.area_ha),
        barWidth: 14,
        itemStyle: { color: "#fcc817", borderRadius: [0, 6, 6, 0] },
        label: {
          show: true,
          position: "right",
          color: "#5b6b60",
          fontSize: 11,
          formatter: ({ value }) => `${num(Number(value) / 1_000_000, 2)} mi ha`,
        },
      },
    ],
  };
  return <Grafico option={option} className="h-64 w-full" />;
}

function SemDado({ texto }: { texto: string }) {
  return (
    <div className="grid h-64 place-items-center rounded-xl border border-dashed border-line text-sm text-muted">
      {texto}
    </div>
  );
}
