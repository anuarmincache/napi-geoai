"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { FeatureCollection, Geometry } from "geojson";
import { PropsMunicipio, num } from "@/lib/dados";
import { cn } from "@/lib/utils";
import "maplibre-gl/dist/maplibre-gl.css";

/**
 * Mapa dos 399 municípios do Paraná.
 *
 * A geometria é a malha oficial do IBGE servida pelo próprio projeto. O
 * mapa-base é opcional e só entra se NEXT_PUBLIC_BASEMAP estiver definido,
 * para a página não depender de serviço externo.
 *
 * Município sem valor fica cinza e o tooltip diz "sem dado". Ausência nunca
 * vira zero.
 */

const BASEMAP = process.env.NEXT_PUBLIC_BASEMAP;

// O worker é servido de public/ (ver scripts/preparar-maplibre.mjs): o
// bundler não resolve o caminho interno da biblioteca.
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

const ESTILO_SEM_BASE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    { id: "fundo", type: "background", paint: { "background-color": "#0c1d15" } },
  ],
};

function hexParaRgb(hex: string): [number, number, number] {
  const limpo = hex.replace("#", "");
  return [
    parseInt(limpo.slice(0, 2), 16),
    parseInt(limpo.slice(2, 4), 16),
    parseInt(limpo.slice(4, 6), 16),
  ];
}

function mistura(
  base: [number, number, number],
  alvo: [number, number, number],
  t: number,
): [number, number, number] {
  return [
    Math.round(base[0] + (alvo[0] - base[0]) * t),
    Math.round(base[1] + (alvo[1] - base[1]) * t),
    Math.round(base[2] + (alvo[2] - base[2]) * t),
  ];
}

export interface MapaProps {
  malha: FeatureCollection<Geometry, PropsMunicipio> | null;
  /** Valor por código IBGE. Ausente ou null = sem dado. */
  valores: Record<string, number | null | undefined>;
  rotulo: string;
  unidade: string;
  cor: string;
  casas?: number;
  /** Modo categórico: cor explícita por município e legenda de categorias. */
  corPorMunicipio?: Record<string, string>;
  legenda?: { cor: string; rotulo: string }[];
  /** Texto do tooltip quando o modo é categórico. */
  textoPorMunicipio?: Record<string, string>;
  selecionado?: string | null;
  onSelecionar?: (cd: string | null) => void;
  altura?: string;
}

export function MapaMunicipios({
  malha,
  valores,
  rotulo,
  unidade,
  cor,
  casas,
  corPorMunicipio,
  legenda,
  textoPorMunicipio,
  selecionado = null,
  onSelecionar,
  altura = "h-[520px]",
}: MapaProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapLibreMap | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [pronto, setPronto] = useState(false);
  const [hover, setHover] = useState<{
    props: PropsMunicipio;
    x: number;
    y: number;
  } | null>(null);

  // Escala em raiz quadrada: a distribuição municipal é muito concentrada.
  const maximo = useMemo(() => {
    let max = 0;
    for (const valor of Object.values(valores)) {
      const v = Number(valor);
      if (Number.isFinite(v) && v > max) max = v;
    }
    return max || 1;
  }, [valores]);

  const decimais = casas ?? (maximo < 10 ? 2 : 0);

  useEffect(() => {
    if (!container.current || mapa.current) return;
    const instancia = new maplibregl.Map({
      container: container.current,
      style: BASEMAP ?? ESTILO_SEM_BASE,
      center: [-51.5, -24.6],
      zoom: 6.1,
      minZoom: 5,
      maxZoom: 11,
      attributionControl: false,
      dragRotate: false,
    });
    instancia.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    instancia.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "Malha municipal: IBGE 2025",
      }),
      "bottom-right",
    );
    const camadaDeck = new MapboxOverlay({ interleaved: false, layers: [] });
    instancia.addControl(camadaDeck);
    mapa.current = instancia;
    overlay.current = camadaDeck;
    instancia.on("load", () => setPronto(true));
    return () => {
      instancia.remove();
      mapa.current = null;
      overlay.current = null;
    };
  }, []);

  useEffect(() => {
    if (!overlay.current || !malha) return;
    const corAlvo = hexParaRgb(cor);
    const corBase: [number, number, number] = [226, 236, 222];
    const layer = new GeoJsonLayer<PropsMunicipio>({
      id: `municipios-${rotulo}`,
      data: malha,
      pickable: true,
      stroked: true,
      filled: true,
      lineWidthUnits: "pixels",
      getLineWidth: (f) => (f.properties.cd === selecionado ? 2.4 : 0.4),
      getLineColor: (f) =>
        f.properties.cd === selecionado ? [252, 200, 23, 255] : [12, 29, 21, 170],
      getFillColor: (f) => {
        if (corPorMunicipio) {
          const explicita = corPorMunicipio[f.properties.cd];
          if (!explicita) return [90, 102, 94, 110];
          const [r, g, b] = hexParaRgb(explicita);
          return [r, g, b, 225];
        }
        const bruto = valores[f.properties.cd];
        if (bruto === null || bruto === undefined || !Number.isFinite(bruto)) {
          return [90, 102, 94, 120];
        }
        const t = Math.sqrt(Math.max(0, Number(bruto)) / maximo);
        const [r, g, b] = mistura(corBase, corAlvo, t);
        return [r, g, b, 225];
      },
      updateTriggers: {
        getFillColor: [rotulo, maximo, valores, corPorMunicipio],
        getLineColor: [selecionado],
        getLineWidth: [selecionado],
      },
      onHover: (info) => {
        if (info.object && info.x !== undefined) {
          setHover({
            props: (info.object as { properties: PropsMunicipio }).properties,
            x: info.x,
            y: info.y,
          });
        } else {
          setHover(null);
        }
      },
      onClick: (info) => {
        if (!onSelecionar) return;
        const props = (info.object as { properties: PropsMunicipio } | null)
          ?.properties;
        onSelecionar(props && props.cd !== selecionado ? props.cd : null);
      },
      transitions: { getFillColor: 320 },
    });
    overlay.current.setProps({ layers: [layer] });
  }, [
    malha,
    valores,
    rotulo,
    cor,
    maximo,
    corPorMunicipio,
    selecionado,
    onSelecionar,
  ]);

  const valorHover = hover ? valores[hover.props.cd] : null;

  return (
    <div className={cn("relative w-full overflow-hidden", altura)}>
      <div ref={container} className="h-full w-full" />

      {!pronto && (
        <div className="absolute inset-0 grid place-items-center bg-[#0c1d15] text-sm text-white/70">
          Carregando o mapa…
        </div>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 rounded-xl bg-[#0c1d15]/85 px-3 py-2.5 text-white backdrop-blur">
        <p className="text-[11px] font-semibold tracking-wider text-white/60 uppercase">
          {rotulo}
        </p>
        {legenda ? (
          <ul className="mt-1.5 space-y-1">
            {legenda.map((item) => (
              <li
                key={item.rotulo}
                className="flex items-center gap-1.5 text-[11px] text-white/80"
              >
                <span
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ background: item.cor }}
                />
                {item.rotulo}
              </li>
            ))}
          </ul>
        ) : (
          <>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="text-[11px] text-white/70">0</span>
              <div
                className="h-2.5 w-28 rounded-full"
                style={{ background: `linear-gradient(90deg, #e2ecde, ${cor})` }}
              />
              <span className="text-[11px] text-white/70">
                {num(maximo, maximo < 10 ? 1 : 0)}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-white/60">{unidade}</p>
          </>
        )}
        <p className="mt-1 flex items-center gap-1.5 text-[11px] text-white/45">
          <span className="h-2 w-2 rounded-sm bg-[#5a665e]" /> sem dado
        </p>
      </div>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 w-56 rounded-xl border border-white/10 bg-[#0c1d15]/95 p-3 text-white shadow-xl"
          style={{
            left: Math.min(hover.x + 14, 400),
            top: Math.max(hover.y - 10, 8),
          }}
        >
          <p className="font-display text-sm font-semibold">{hover.props.nome}</p>
          <p className="text-[11px] text-white/55">Código IBGE {hover.props.cd}</p>
          <p className="mt-2 text-lg font-semibold text-lime">
            {textoPorMunicipio
              ? (textoPorMunicipio[hover.props.cd] ?? "fora da lista")
              : valorHover === null ||
                  valorHover === undefined ||
                  !Number.isFinite(valorHover)
                ? "sem dado"
                : `${num(Number(valorHover), decimais)} ${unidade}`}
          </p>
          <p className="mt-1 text-[11px] text-white/60">
            {num(hover.props.habitantes)} hab · {num(hover.props.area_km2, 1)} km²
          </p>
        </div>
      )}
    </div>
  );
}
