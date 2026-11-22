"use client";

import { motion } from "motion/react";
import { BarraLateral } from "@/components/barra-lateral";
import { MarcaNapi } from "@/components/marca";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Moldura de todas as páginas: menu, conteúdo e rodapé institucional. */
export function Pagina({
  children,
  largura = "max-w-[1340px]",
}: {
  children: React.ReactNode;
  largura?: string;
}) {
  return (
    <div className="flex min-h-screen bg-paper">
      <BarraLateral />
      <main className="min-w-0 flex-1 px-4 py-6 pt-16 lg:px-8 lg:py-8">
        <div className={cn("mx-auto space-y-8", largura)}>
          {children}
          <RodapeInstitucional />
        </div>
      </main>
    </div>
  );
}

export function CabecalhoPagina({
  secao,
  titulo,
  descricao,
  children,
}: {
  secao: string;
  titulo: string;
  descricao: string;
  children?: React.ReactNode;
}) {
  return (
    <motion.header
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      /* Sem overflow-hidden aqui: as sugestões de busca precisam poder sair
         da faixa. O recorte fica na arte de fundo, logo abaixo. */
      className="relative rounded-3xl bg-[linear-gradient(118deg,#1a2e20_0%,#2f4a33_48%,#456b38_100%)] px-7 py-8 text-white lg:px-9"
    >
      <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
        <svg
          aria-hidden
          className="h-full w-full"
          viewBox="0 0 1200 220"
          preserveAspectRatio="xMidYMid slice"
        >
          <circle cx="1080" cy="24" r="130" fill="#fcc817" fillOpacity="0.1" />
          {Array.from({ length: 7 }).map((_, i) => (
            <path
              key={i}
              d={`M-40 ${150 + i * 18} Q 500 ${96 + i * 15} 1240 ${130 + i * 17}`}
              fill="none"
              stroke="#a8cf5f"
              strokeOpacity={0.11}
              strokeWidth="1.5"
            />
          ))}
        </svg>
      </div>
      <div className="relative z-10">
        <p className="font-display text-[11px] font-bold tracking-[0.18em] text-sun uppercase">
          {secao}
        </p>
        <h1 className="mt-2 font-display text-[clamp(1.6rem,2.8vw,2.3rem)] leading-tight font-extrabold tracking-[-0.02em]">
          {titulo}
        </h1>
        <p className="mt-2.5 max-w-3xl text-[1.01rem] leading-relaxed text-white/80">
          {descricao}
        </p>
        {children && <div className="mt-4">{children}</div>}
      </div>
    </motion.header>
  );
}

export function SecaoTitulo({
  titulo,
  descricao,
}: {
  titulo: string;
  descricao?: string;
}) {
  return (
    <div className="mb-4">
      <h2 className="font-display text-2xl font-bold tracking-tight text-forest">
        {titulo}
      </h2>
      {descricao && <p className="mt-1 text-sm text-muted">{descricao}</p>}
    </div>
  );
}

/** Mensagem única para dado ausente. Nunca substituída por número. */
export function Indisponivel({
  titulo = "Dado indisponível",
  detalhe,
}: {
  titulo?: string;
  detalhe: string;
}) {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>{titulo}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm leading-relaxed text-muted">
        {detalhe} Nenhum número é exibido no lugar dele.
      </CardContent>
    </Card>
  );
}

export function Carregando({ altura = "h-64" }: { altura?: string }) {
  return (
    <div className={cn("w-full animate-pulse rounded-2xl bg-line/60", altura)} />
  );
}

export function Avisos({ itens }: { itens: string[] }) {
  if (!itens.length) return null;
  return (
    <ul className="space-y-1 rounded-2xl border border-line bg-white px-5 py-4 text-[12px] leading-relaxed text-muted">
      {itens.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-sun" />
          {item}
        </li>
      ))}
    </ul>
  );
}

function RodapeInstitucional() {
  return (
    <footer className="rounded-2xl border border-line bg-white px-6 py-6">
      <div className="flex flex-wrap items-center gap-5">
        <MarcaNapi className="h-12 w-12 shrink-0" />
        <div className="min-w-[18rem] flex-1 text-sm leading-relaxed text-muted">
          <strong className="text-forest">NAPI GeoAI</strong> é uma iniciativa do
          NAPI Energia Zero-Carbono. Os indicadores apoiam a investigação e não
          substituem estudos de viabilidade técnica, ambiental ou econômica.
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge>Universidade Estadual de Maringá (UEM)</Badge>
            <Badge>Fundação Araucária</Badge>
          </div>
        </div>
      </div>
    </footer>
  );
}
