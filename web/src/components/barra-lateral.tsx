"use client";

import { MarcaNapi } from "@/components/marca";
import { cn } from "@/lib/utils";

const GRUPOS: { titulo: string; itens: { rotulo: string; ativo?: boolean }[] }[] =
  [
    {
      titulo: "Comece aqui",
      itens: [
        { rotulo: "Painel geral", ativo: true },
        { rotulo: "Ficha do município" },
        { rotulo: "Explorar o mapa" },
      ],
    },
    {
      titulo: "Energia",
      itens: [
        { rotulo: "Solar e geração distribuída" },
        { rotulo: "Usinas e geração centralizada" },
        { rotulo: "Calculadoras" },
      ],
    },
    {
      titulo: "Território",
      itens: [
        { rotulo: "Agricultura e pecuária" },
        { rotulo: "Cobertura da terra" },
        { rotulo: "Vegetação por satélite" },
      ],
    },
    {
      titulo: "Transparência",
      itens: [{ rotulo: "Fontes e qualidade" }, { rotulo: "Sobre o projeto" }],
    },
  ];

export function BarraLateral() {
  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-forest-deep text-white lg:flex">
      <div className="flex items-center gap-3 px-5 pt-6 pb-5">
        <MarcaNapi className="h-10 w-10" />
        <div>
          <p className="font-display text-lg leading-none font-bold">
            NAPI Geo<span className="text-lime">AI</span>
          </p>
          <p className="mt-1 text-[11px] leading-tight text-white/55">
            Energia Zero-Carbono · Paraná
          </p>
        </div>
      </div>

      <nav className="scrollbar-slim flex-1 overflow-y-auto px-3 pb-4">
        {GRUPOS.map((grupo) => (
          <div key={grupo.titulo} className="mb-5">
            <p className="px-2 pb-1.5 font-display text-[10px] font-bold tracking-[0.16em] text-lime/80 uppercase">
              {grupo.titulo}
            </p>
            <ul className="space-y-0.5">
              {grupo.itens.map((item) => (
                <li key={item.rotulo}>
                  <span
                    className={cn(
                      "flex cursor-default items-center gap-2 rounded-lg px-2.5 py-2 text-sm",
                      item.ativo
                        ? "bg-white/12 font-semibold text-white"
                        : "text-white/65",
                    )}
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        item.ativo ? "bg-sun" : "bg-white/25",
                      )}
                    />
                    {item.rotulo}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 px-5 py-4 text-[11px] leading-relaxed text-white/45">
        Protótipo de interface. A navegação ainda não está ligada às demais
        páginas.
      </div>
    </aside>
  );
}
