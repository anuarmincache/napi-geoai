"use client";

import { useEffect, useRef, useState } from "react";
import { animate, motion, useInView } from "motion/react";
import { Card } from "@/components/ui/card";
import { ClasseBadge } from "@/components/ui/badge";
import { Kpi, num } from "@/lib/dados";

const CORES: Record<string, string> = {
  municipios: "#455b40",
  populacao: "#5b8a3a",
  mmgd: "#fcc817",
  siga: "#73a535",
};

/** Conta até o valor quando o cartão entra na tela. */
function Contador({ valor, casas }: { valor: number; casas: number }) {
  const alvo = useRef<HTMLSpanElement>(null);
  const visivel = useInView(alvo, { once: true, margin: "-40px" });
  const [texto, setTexto] = useState(num(0, casas));

  useEffect(() => {
    if (!visivel) return;
    const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const controles = animate(0, valor, {
      // Sem animação quando o sistema pede movimento reduzido.
      duration: reduzir ? 0 : 1.1,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setTexto(num(v, casas)),
    });
    return () => controles.stop();
  }, [visivel, valor, casas]);

  return <span ref={alvo}>{texto}</span>;
}

function formatar(kpi: Kpi) {
  if (kpi.unidade === "MW" && kpi.valor >= 1000) {
    return { valor: kpi.valor / 1000, unidade: "GW", casas: 2 };
  }
  if (kpi.unidade === "hab" && kpi.valor >= 1_000_000) {
    return { valor: kpi.valor / 1_000_000, unidade: "mi hab", casas: 2 };
  }
  return { valor: kpi.valor, unidade: kpi.unidade, casas: 0 };
}

export function Kpis({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi, i) => {
        const f = formatar(kpi);
        return (
          <motion.div
            key={kpi.id}
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.45, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
          >
            <Card className="h-full overflow-hidden">
              <div
                className="h-1.5 w-full"
                style={{ background: CORES[kpi.id] ?? "#73a535" }}
              />
              <div className="px-5 pt-4 pb-4">
                <p className="font-display text-[11px] font-bold uppercase tracking-[0.12em] text-muted">
                  {kpi.rotulo}
                </p>
                <p className="mt-1.5 font-display text-[2rem] leading-none font-bold tracking-tight text-forest">
                  <Contador valor={f.valor} casas={f.casas} />
                  {f.unidade && (
                    <span className="ml-1.5 text-base font-semibold text-muted">
                      {f.unidade}
                    </span>
                  )}
                </p>
                <p className="mt-2 text-sm text-ink">{kpi.detalhe}</p>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <p className="text-[11px] leading-tight text-muted">
                    {kpi.fonte} · {kpi.data}
                  </p>
                  <ClasseBadge classe={kpi.classe} />
                </div>
              </div>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
