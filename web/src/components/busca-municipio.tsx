"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";

export interface OpcaoMunicipio {
  cd: string;
  nome: string;
}

/** Busca por nome ou código IBGE, com sugestões. */
export function BuscaMunicipio({
  opcoes,
  valor,
  onEscolher,
  placeholder = "Busque por nome ou código IBGE",
}: {
  opcoes: OpcaoMunicipio[];
  valor: string | null;
  onEscolher: (cd: string) => void;
  placeholder?: string;
}) {
  const [termo, setTermo] = useState("");
  const [aberto, setAberto] = useState(false);
  const [focado, setFocado] = useState(false);

  const sugestoes = useMemo(() => {
    const t = termo
      .trim()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
    if (!t) return opcoes.slice(0, 8);
    return opcoes
      .filter((o) => {
        const nome = o.nome
          .toLowerCase()
          .normalize("NFD")
          .replace(/[̀-ͯ]/g, "");
        return nome.includes(t) || o.cd.includes(t);
      })
      .slice(0, 8);
  }, [opcoes, termo]);

  const escolhido = opcoes.find((o) => o.cd === valor);

  return (
    <div className="relative">
      <input
        // Fora do foco, mostra o município escolhido; ao focar, fica livre
        // para digitar.
        value={focado ? termo : (escolhido?.nome ?? termo)}
        onChange={(e) => {
          setTermo(e.target.value);
          setAberto(true);
        }}
        onFocus={() => {
          setFocado(true);
          setAberto(true);
        }}
        onBlur={() =>
          window.setTimeout(() => {
            setAberto(false);
            setFocado(false);
            setTermo("");
          }, 150)
        }
        placeholder={placeholder}
        aria-label="Buscar município"
        className="w-full rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-medium text-ink outline-none placeholder:font-normal placeholder:text-muted/80 focus:border-moss"
      />
      {aberto && sugestoes.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-line bg-white py-1 shadow-2xl">
          {sugestoes.map((o) => (
            <li key={o.cd}>
              <button
                onMouseDown={() => {
                  onEscolher(o.cd);
                  setTermo("");
                  setAberto(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-paper",
                  o.cd === valor && "bg-paper font-semibold",
                )}
              >
                <span className="text-ink">{o.nome}</span>
                <span className="text-[11px] text-muted">{o.cd}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
