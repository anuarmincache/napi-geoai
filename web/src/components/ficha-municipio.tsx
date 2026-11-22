"use client";

import { AnimatePresence, motion } from "motion/react";
import { Ficha, num } from "@/lib/dados";
import { Badge } from "@/components/ui/badge";

/** Painel lateral do município escolhido no mapa. */
export function FichaMunicipio({
  ficha,
  onFechar,
}: {
  ficha: Ficha | null;
  onFechar: () => void;
}) {
  return (
    <AnimatePresence mode="wait">
      {ficha ? (
        <motion.div
          key={ficha.cd}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          className="flex h-full flex-col"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-display text-xl leading-tight font-bold text-forest">
                {ficha.nome}
              </h3>
              <p className="text-[11px] text-muted">Código IBGE {ficha.cd}</p>
            </div>
            <button
              onClick={onFechar}
              className="rounded-lg px-2 py-1 text-xs font-semibold text-muted hover:bg-paper"
            >
              fechar
            </button>
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-3">
            <Dado rotulo="População" valor={num(ficha.habitantes)} unidade="hab" />
            <Dado rotulo="Área" valor={num(ficha.area_km2, 1)} unidade="km²" />
            <Dado
              rotulo="Densidade"
              valor={num(ficha.densidade, 1)}
              unidade="hab/km²"
            />
            <Dado
              rotulo="Usinas"
              valor={num(ficha.siga?.usinas ?? 0)}
              unidade={`· ${num(ficha.siga?.mw ?? 0, 1)} MW`}
            />
          </dl>

          {ficha.mmgd && (
            <div className="mt-4 rounded-xl bg-paper p-3">
              <p className="font-display text-[11px] font-bold tracking-wider text-muted uppercase">
                Geração distribuída
              </p>
              <p className="mt-1 font-display text-2xl font-bold text-forest">
                {num(ficha.mmgd.mw, 1)}{" "}
                <span className="text-sm font-semibold text-muted">MW</span>
              </p>
              <p className="text-xs text-muted">
                {num(ficha.mmgd.n)} instalações · ANEEL MMGD 11/2026
              </p>
            </div>
          )}

          {ficha.cobertura && (
            <div className="mt-4">
              <p className="font-display text-[11px] font-bold tracking-wider text-muted uppercase">
                Cobertura da terra, 2025
              </p>
              <div className="mt-2 flex h-3 overflow-hidden rounded-full">
                {ficha.cobertura
                  .filter((c) => (c.pct ?? 0) > 0)
                  .map((c) => (
                    <div
                      key={c.nome}
                      title={`${c.nome}: ${num(c.pct, 1)}%`}
                      style={{ width: `${c.pct}%`, background: c.cor }}
                    />
                  ))}
              </div>
              <ul className="mt-2 space-y-1">
                {ficha.cobertura
                  .filter((c) => (c.pct ?? 0) >= 3)
                  .sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))
                  .slice(0, 4)
                  .map((c) => (
                    <li
                      key={c.nome}
                      className="flex items-center justify-between text-xs text-ink"
                    >
                      <span className="flex items-center gap-1.5">
                        <span
                          className="h-2 w-2 rounded-sm"
                          style={{ background: c.cor }}
                        />
                        {c.nome}
                      </span>
                      <span className="font-semibold">{num(c.pct, 1)}%</span>
                    </li>
                  ))}
              </ul>
              <p className="mt-2 text-[11px] leading-snug text-muted">
                Percentual da área mapeada pelo MapBiomas, não da área oficial.
              </p>
            </div>
          )}

          {ficha.pecuaria && ficha.pecuaria.some((p) => p.valor) && (
            <div className="mt-4">
              <p className="font-display text-[11px] font-bold tracking-wider text-muted uppercase">
                Pecuária, 2025
              </p>
              <ul className="mt-1.5 space-y-1">
                {ficha.pecuaria.map((p) => (
                  <li
                    key={p.nome}
                    className="flex items-center justify-between text-xs text-ink"
                  >
                    <span>{p.nome}</span>
                    <span className="font-semibold">
                      {p.valor === null ? "sem dado" : num(p.valor)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-auto pt-4 text-[11px] leading-snug text-muted">
            Efetivo de rebanho não é resíduo disponível para biogás. Potência
            instalada não é energia gerada.
          </p>
        </motion.div>
      ) : (
        <motion.div
          key="vazio"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex h-full flex-col items-center justify-center text-center"
        >
          <div className="rounded-2xl bg-paper p-4">
            <svg viewBox="0 0 48 48" className="h-10 w-10" aria-hidden>
              <path
                d="M24 6c-7 0-12 5-12 12 0 9 12 24 12 24s12-15 12-24c0-7-5-12-12-12z"
                fill="#a8cf5f"
              />
              <circle cx="24" cy="18" r="5" fill="#2f4a33" />
            </svg>
          </div>
          <p className="mt-3 max-w-[16rem] text-sm text-muted">
            Clique em um município no mapa para ver a ficha dele aqui.
          </p>
          <Badge className="mt-3">399 municípios disponíveis</Badge>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Dado({
  rotulo,
  valor,
  unidade,
}: {
  rotulo: string;
  valor: string;
  unidade: string;
}) {
  return (
    <div className="rounded-xl border border-line px-3 py-2">
      <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
        {rotulo}
      </dt>
      <dd className="mt-0.5 font-display text-lg leading-none font-bold text-forest">
        {valor}{" "}
        <span className="text-[11px] font-semibold text-muted">{unidade}</span>
      </dd>
    </div>
  );
}
