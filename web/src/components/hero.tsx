"use client";

import { motion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { Resumo } from "@/lib/dados";

/** Faixa de abertura. A arte é vetorial e original, sem fotografia. */
export function Hero({ resumo }: { resumo: Resumo }) {
  return (
    <section className="relative overflow-hidden rounded-3xl bg-[linear-gradient(118deg,#1a2e20_0%,#2f4a33_44%,#456b38_100%)] text-white">
      <ArteFundo />
      <div className="relative z-10 grid gap-8 px-7 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:px-10 lg:py-12">
        <div>
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="font-display text-[11px] font-bold tracking-[0.18em] text-sun uppercase"
          >
            NAPI Energia Zero-Carbono · Paraná
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="mt-3 font-display text-[clamp(1.9rem,3.4vw,2.9rem)] leading-[1.07] font-extrabold tracking-[-0.025em]"
          >
            Onde investigar{" "}
            <span className="text-sun">energia sustentável</span> no Paraná
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.16 }}
            className="mt-4 max-w-xl text-[1.02rem] leading-relaxed text-white/80"
          >
            Território, população, energia, lavouras e cobertura da terra dos
            399 municípios, reunidos em um só lugar. Cada número traz a fonte, a
            data e o que ele não diz.
          </motion.p>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.26 }}
            className="mt-6 flex flex-wrap gap-2"
          >
            <Badge variant="escuro">Dados oficiais em retratos datados</Badge>
            <Badge variant="escuro">Não é tempo real</Badge>
            <Badge variant="escuro">Não indica viabilidade</Badge>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, x: 18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col justify-center gap-3"
        >
          {resumo.fontes.map((fonte) => (
            <div
              key={fonte.nome}
              className="rounded-xl border border-white/12 bg-white/8 px-4 py-3 backdrop-blur-sm"
            >
              <p className="font-display text-sm font-bold text-white">
                {fonte.nome}
              </p>
              <p className="mt-0.5 text-[12px] leading-snug text-white/65">
                {fonte.detalhe}
              </p>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function ArteFundo() {
  return (
    <svg
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 1200 420"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <radialGradient id="sol" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#fcc817" stopOpacity="0.4" />
          <stop offset="1" stopColor="#fcc817" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="1010" cy="90" r="190" fill="url(#sol)" />
      <circle cx="1010" cy="90" r="46" fill="#fcc817" fillOpacity="0.75" />
      {Array.from({ length: 14 }).map((_, i) => (
        <path
          key={i}
          d={`M-60 ${300 + i * 16} Q 420 ${232 + i * 13} 1260 ${268 + i * 15}`}
          fill="none"
          stroke="#a8cf5f"
          strokeOpacity={0.12}
          strokeWidth="1.5"
        />
      ))}
      <g stroke="#ffffff" strokeOpacity="0.14" fill="none" strokeWidth="1.5">
        <path d="M60 60 q50 -26 100 0 t100 0" />
        <path d="M110 92 q42 -20 84 0 t84 0" />
      </g>
    </svg>
  );
}
