"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { FeatureCollection, Geometry } from "geojson";
import { Camada, PropsMunicipio, num } from "@/lib/dados";
import { cn } from "@/lib/utils";
import "maplibre-gl/dist/maplibre-gl.css";

/**
 * Mapa dos 399 municípios. A geometria é a malha oficial do IBGE servida pelo
 * próprio projeto; o mapa-base é opcional e só entra se NEXT_PUBLIC_BASEMAP
 * estiver definido, para a página não depender de serviço externo.
 */

const BASEMAP = process.env.NEXT_PUBLIC_BASEMAP;

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
  dados: FeatureCollection<Geometry, PropsMunicipio> | null;
  camada: Camada;
  selecionado: string | null;
  onSelecionar: (cd: string | null) => void;
  className?: string;
}

export function MapaParana({
  dados,
  camada,
  selecionado,
  onSelecionar,
  className,
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

  // Escala: raiz quadrada, porque a distribuição é muito concentrada.
  const maximo = useMemo(() => {
    if (!dados) return 1;
    let max = 0;
    for (const f of dados.features) {
      const v = Number(f.properties[camada.id] ?? 0);
      if (Number.isFinite(v) && v > max) max = v;
    }
    return max || 1;
  }, [dados, camada.id]);

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
    if (!overlay.current || !dados) return;
    const corAlvo = hexParaRgb(camada.cor);
    const corBase: [number, number, number] = [226, 236, 222];
    const layer = new GeoJsonLayer<PropsMunicipio>({
      id: `municipios-${camada.id}`,
      data: dados,
      pickable: true,
      stroked: true,
      filled: true,
      lineWidthUnits: "pixels",
      getLineWidth: (f) => (f.properties.cd === selecionado ? 2.4 : 0.4),
      getLineColor: (f) =>
        f.properties.cd === selecionado ? [252, 200, 23, 255] : [12, 29, 21, 170],
      getFillColor: (f) => {
        const bruto = f.properties[camada.id];
        if (bruto === null || bruto === undefined) return [90, 102, 94, 120];
        const t = Math.sqrt(Math.max(0, Number(bruto)) / maximo);
        const [r, g, b] = mistura(corBase, corAlvo, t);
        return [r, g, b, 225];
      },
      updateTriggers: {
        getFillColor: [camada.id, maximo],
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
        const props = (info.object as { properties: PropsMunicipio } | null)
          ?.properties;
        onSelecionar(props && props.cd !== selecionado ? props.cd : null);
      },
      transitions: { getFillColor: 320 },
    });
    overlay.current.setProps({ layers: [layer] });
  }, [dados, camada, maximo, selecionado, onSelecionar]);

  const valorHover = hover ? hover.props[camada.id] : null;

  return (
    <div className={cn("relative h-full w-full overflow-hidden", className)}>
      <div ref={container} className="h-full w-full" />

      {!pronto && (
        <div className="absolute inset-0 grid place-items-center bg-[#0c1d15] text-sm text-white/70">
          Carregando o mapa…
        </div>
      )}

      {/* Legenda */}
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-xl bg-[#0c1d15]/85 px-3 py-2.5 text-white backdrop-blur">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-white/60">
          {camada.rotulo}
        </p>
        <div className="mt-1.5 flex items-center gap-2">
          <span className="text-[11px] text-white/70">0</span>
          <div
            className="h-2.5 w-28 rounded-full"
            style={{
              background: `linear-gradient(90deg, #e2ecde, ${camada.cor})`,
            }}
          />
          <span className="text-[11px] text-white/70">
            {num(maximo, maximo < 10 ? 1 : 0)}
          </span>
        </div>
        <p className="mt-1 text-[11px] text-white/60">{camada.unidade}</p>
      </div>

      {/* Tooltip */}
      {hover && (
        <div
          className="pointer-events-none absolute z-10 w-56 rounded-xl border border-white/10 bg-[#0c1d15]/95 p-3 text-white shadow-xl"
          style={{
            left: Math.min(hover.x + 14, 420),
            top: Math.max(hover.y - 10, 8),
          }}
        >
          <p className="font-display text-sm font-semibold">{hover.props.nome}</p>
          <p className="text-[11px] text-white/55">Código IBGE {hover.props.cd}</p>
          <p className="mt-2 text-lg font-semibold text-lime">
            {valorHover === null || valorHover === undefined
              ? "sem dado"
              : `${num(Number(valorHover), Number(valorHover) < 10 ? 2 : 0)} ${camada.unidade}`}
          </p>
          <p className="mt-1 text-[11px] text-white/60">
            {num(hover.props.habitantes)} hab · {num(hover.props.area_km2, 1)} km²
          </p>
        </div>
      )}
    </div>
  );
}
