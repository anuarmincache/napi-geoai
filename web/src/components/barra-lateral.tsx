"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { MarcaNapi } from "@/components/marca";
import { cn } from "@/lib/utils";

export const NAVEGACAO: {
  titulo: string;
  itens: { rotulo: string; href: string }[];
}[] = [
  {
    titulo: "Comece aqui",
    itens: [
      { rotulo: "Painel geral", href: "/" },
      { rotulo: "Ficha do município", href: "/ficha" },
      { rotulo: "Explorar o mapa", href: "/explorar" },
    ],
  },
  {
    titulo: "Energia",
    itens: [
      { rotulo: "Solar e geração distribuída", href: "/geracao-distribuida" },
      { rotulo: "Usinas e geração centralizada", href: "/usinas" },
      { rotulo: "Calculadoras", href: "/calculadoras" },
    ],
  },
  {
    titulo: "Território",
    itens: [
      { rotulo: "Agricultura e pecuária", href: "/agricultura" },
      { rotulo: "Cobertura da terra", href: "/cobertura" },
    ],
  },
  {
    titulo: "Transparência",
    itens: [
      { rotulo: "Fontes e qualidade", href: "/fontes" },
      { rotulo: "Sobre o projeto", href: "/sobre" },
    ],
  },
];

function Itens({ aoNavegar }: { aoNavegar?: () => void }) {
  const caminho = usePathname();
  return (
    <>
      {NAVEGACAO.map((grupo) => (
        <div key={grupo.titulo} className="mb-5">
          <p className="px-2 pb-1.5 font-display text-[10px] font-bold tracking-[0.16em] text-lime/80 uppercase">
            {grupo.titulo}
          </p>
          <ul className="space-y-0.5">
            {grupo.itens.map((item) => {
              const ativo = caminho === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={aoNavegar}
                    aria-current={ativo ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors",
                      ativo
                        ? "bg-white/12 font-semibold text-white"
                        : "text-white/65 hover:bg-white/8 hover:text-white",
                    )}
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 shrink-0 rounded-full",
                        ativo ? "bg-sun" : "bg-white/25",
                      )}
                    />
                    {item.rotulo}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </>
  );
}

function Cabecalho() {
  return (
    <div className="flex items-center gap-3 px-5 pt-6 pb-5">
      <MarcaNapi className="h-10 w-10 shrink-0" />
      <div>
        <p className="font-display text-lg leading-none font-bold">
          NAPI Geo<span className="text-lime">AI</span>
        </p>
        <p className="mt-1 text-[11px] leading-tight text-white/55">
          Energia Zero-Carbono · Paraná
        </p>
      </div>
    </div>
  );
}

export function BarraLateral() {
  const [aberto, setAberto] = useState(false);

  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-forest-deep text-white lg:flex">
        <Cabecalho />
        <nav className="scrollbar-slim flex-1 overflow-y-auto px-3 pb-4">
          <Itens />
        </nav>
        <p className="border-t border-white/10 px-5 py-4 text-[11px] leading-relaxed text-white/45">
          Versão em desenvolvimento desta interface.
        </p>
      </aside>

      {/* Telas estreitas */}
      <button
        onClick={() => setAberto(true)}
        className="fixed top-3 left-3 z-40 rounded-xl bg-forest-deep px-3 py-2 text-sm font-semibold text-white shadow-lg lg:hidden"
      >
        ☰ Menu
      </button>
      {aberto && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setAberto(false)}
          />
          <aside className="relative flex h-full w-72 flex-col bg-forest-deep text-white">
            <Cabecalho />
            <nav className="scrollbar-slim flex-1 overflow-y-auto px-3 pb-4">
              <Itens aoNavegar={() => setAberto(false)} />
            </nav>
            <button
              onClick={() => setAberto(false)}
              className="border-t border-white/10 px-5 py-3 text-left text-sm text-white/70"
            >
              fechar
            </button>
          </aside>
        </div>
      )}
    </>
  );
}
