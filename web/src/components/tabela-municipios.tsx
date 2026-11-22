"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { num } from "@/lib/dados";
import { cn } from "@/lib/utils";

export interface LinhaMunicipio {
  cd: string;
  nome: string;
  /** Valor por coluna. null significa sem dado e nunca é exibido como zero. */
  valores: Record<string, number | string | null | undefined>;
}

/** Tabela com busca, ordenação e exportação em CSV. */
export function TabelaMunicipios({
  linhas,
  colunas,
  casas = {},
  selecionado = null,
  onSelecionar,
  nomeArquivo = "napi_geoai",
  porPagina = 15,
}: {
  linhas: LinhaMunicipio[];
  colunas: string[];
  casas?: Record<string, number>;
  selecionado?: string | null;
  onSelecionar?: (cd: string | null) => void;
  nomeArquivo?: string;
  porPagina?: number;
}) {
  const [busca, setBusca] = useState("");
  const [ordem, setOrdem] = useState<{ coluna: string; desc: boolean }>({
    coluna: colunas[0],
    desc: true,
  });
  const [limite, setLimite] = useState(porPagina);

  const filtradas = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    const base = termo
      ? linhas.filter(
          (l) =>
            l.nome.toLowerCase().includes(termo) || l.cd.includes(termo),
        )
      : linhas;
    const copia = [...base];
    copia.sort((a, b) => {
      if (ordem.coluna === "Município") {
        return ordem.desc
          ? b.nome.localeCompare(a.nome, "pt-BR")
          : a.nome.localeCompare(b.nome, "pt-BR");
      }
      const va = a.valores[ordem.coluna];
      const vb = b.valores[ordem.coluna];
      const na = typeof va === "number" ? va : Number.NEGATIVE_INFINITY;
      const nb = typeof vb === "number" ? vb : Number.NEGATIVE_INFINITY;
      return ordem.desc ? nb - na : na - nb;
    });
    return copia;
  }, [linhas, busca, ordem]);

  function baixarCsv() {
    const cabecalho = ["CD_MUN", "NM_MUN", ...colunas];
    const corpo = filtradas.map((l) => [
      l.cd,
      l.nome,
      ...colunas.map((c) => {
        const v = l.valores[c];
        return v === null || v === undefined ? "" : String(v);
      }),
    ]);
    const csv = [cabecalho, ...corpo]
      .map((linha) => linha.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${nomeArquivo}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function alternar(coluna: string) {
    setOrdem((atual) =>
      atual.coluna === coluna
        ? { coluna, desc: !atual.desc }
        : { coluna, desc: true },
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
        <input
          value={busca}
          onChange={(e) => {
            setBusca(e.target.value);
            setLimite(porPagina);
          }}
          placeholder="Buscar por nome ou código IBGE"
          aria-label="Buscar município na tabela por nome ou código IBGE"
          className="min-w-[14rem] flex-1 rounded-xl border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-moss"
        />
        <span className="text-xs text-muted">
          {num(filtradas.length)} de {num(linhas.length)} municípios
        </span>
        <Button size="sm" variant="outline" onClick={baixarCsv}>
          Baixar CSV
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-paper/60 text-left">
              <Th
                rotulo="Município"
                ativo={ordem.coluna === "Município"}
                desc={ordem.desc}
                onClick={() => alternar("Município")}
              />
              {colunas.map((c) => (
                <Th
                  key={c}
                  rotulo={c}
                  numerico
                  ativo={ordem.coluna === c}
                  desc={ordem.desc}
                  onClick={() => alternar(c)}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {filtradas.slice(0, limite).map((l) => (
              <tr
                key={l.cd}
                onClick={() => onSelecionar?.(l.cd === selecionado ? null : l.cd)}
                className={cn(
                  "border-b border-line/60 last:border-0",
                  onSelecionar && "cursor-pointer hover:bg-paper",
                  selecionado === l.cd && "bg-sun/10",
                )}
              >
                <td className="px-5 py-2.5">
                  <span className="font-medium text-ink">{l.nome}</span>
                  <span className="ml-2 text-[11px] text-muted">{l.cd}</span>
                </td>
                {colunas.map((c) => {
                  const v = l.valores[c];
                  return (
                    <td
                      key={c}
                      className="px-4 py-2.5 text-right font-medium text-ink tabular-nums"
                    >
                      {v === null || v === undefined ? (
                        <span className="text-muted">sem dado</span>
                      ) : typeof v === "number" ? (
                        num(v, casas[c] ?? 0)
                      ) : (
                        v
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {limite < filtradas.length && (
        <div className="border-t border-line px-5 py-3 text-center">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setLimite((l) => l + 25)}
          >
            Mostrar mais ({num(filtradas.length - limite)} restantes)
          </Button>
        </div>
      )}
    </Card>
  );
}

function Th({
  rotulo,
  ativo,
  desc,
  onClick,
  numerico = false,
}: {
  rotulo: string;
  ativo: boolean;
  desc: boolean;
  onClick: () => void;
  numerico?: boolean;
}) {
  return (
    <th
      className={cn(
        "px-4 py-2.5 font-display text-[11px] font-bold tracking-wider text-muted uppercase",
        numerico ? "text-right" : "px-5 text-left",
      )}
    >
      <button
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 hover:text-forest",
          ativo && "text-forest",
        )}
      >
        {rotulo}
        <span className="text-[9px]">{ativo ? (desc ? "▼" : "▲") : "⇅"}</span>
      </button>
    </th>
  );
}
