"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

/** Wrapper mínimo do Apache ECharts, com redimensionamento automático. */
export function Grafico({
  option,
  className = "h-64 w-full",
}: {
  option: EChartsOption;
  className?: string;
}) {
  const elemento = useRef<HTMLDivElement>(null);
  const instancia = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!elemento.current) return;
    const grafico = echarts.init(elemento.current, undefined, {
      renderer: "canvas",
    });
    instancia.current = grafico;
    const observador = new ResizeObserver(() => grafico.resize());
    observador.observe(elemento.current);
    return () => {
      observador.disconnect();
      grafico.dispose();
      instancia.current = null;
    };
  }, []);

  useEffect(() => {
    instancia.current?.setOption(option, true);
  }, [option]);

  return <div ref={elemento} className={className} />;
}

export const BASE_ECHARTS: EChartsOption = {
  textStyle: { fontFamily: "Inter, Segoe UI, system-ui, sans-serif" },
  grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
  tooltip: {
    backgroundColor: "#16231b",
    borderWidth: 0,
    textStyle: { color: "#f4f8ef", fontSize: 12 },
    padding: [8, 10],
  },
};
