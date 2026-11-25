"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import {
  CabecalhoPagina,
  Carregando,
  Indisponivel,
  Pagina,
  SecaoTitulo,
} from "@/components/pagina";
import { BuscaMunicipio } from "@/components/busca-municipio";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge, ClasseBadge } from "@/components/ui/badge";
import { Ficha, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

const PADRAO = "4115200"; // Maringá

export default function FichaPagina() {
  const fichas = useDados<Record<string, Ficha>>("fichas.json");
  const [cd, setCd] = useState(PADRAO);

  const opcoes = useMemo(
    () =>
      Object.values(fichas.dados ?? {})
        .map((f) => ({ cd: f.cd, nome: f.nome }))
        .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")),
    [fichas.dados],
  );

  const ficha = fichas.dados?.[cd] ?? null;

  if (fichas.erro) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Comece aqui"
          titulo="Ficha do município"
          descricao="Território, população, energia e agropecuária em um só lugar."
        />
        <Indisponivel detalhe="As fichas municipais não estão disponíveis." />
      </Pagina>
    );
  }

  const kwPorHab =
    ficha?.mmgd?.mw && ficha.habitantes
      ? (ficha.mmgd.mw * 1000) / ficha.habitantes
      : null;

  return (
    <Pagina largura="max-w-[1100px]">
      <CabecalhoPagina
        secao="Comece aqui"
        titulo="Ficha do município"
        descricao="Território, população, energia e agropecuária de um município, cada número com a sua fonte e o seu ano."
      >
        <div className="max-w-md">
          <BuscaMunicipio opcoes={opcoes} valor={cd} onEscolher={setCd} />
        </div>
      </CabecalhoPagina>

      {!ficha ? (
        <Carregando altura="h-64" />
      ) : (
        <motion.div
          key={ficha.cd}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="space-y-6"
        >
          <div>
            <h2 className="font-display text-3xl font-bold tracking-tight text-forest">
              {ficha.nome}
            </h2>
            <p className="text-sm text-muted">
              Código IBGE {ficha.cd} · Paraná
            </p>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex items-start justify-between gap-3">
                <CardTitle>Território e população</CardTitle>
                <ClasseBadge classe="A" />
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-3">
                <Dado
                  rotulo="População estimada"
                  valor={num(ficha.habitantes)}
                  unidade="hab"
                />
                <Dado
                  rotulo="Área"
                  valor={num(ficha.area_km2, 1)}
                  unidade="km²"
                />
                <Dado
                  rotulo="Densidade"
                  valor={num(ficha.densidade, 1)}
                  unidade="hab/km²"
                  classe="B"
                />
              </CardContent>
              <CardFooter>
                IBGE, estimativa de 01/07/2026 (não é Censo) e Malha Municipal
                2025. A densidade combina população de 2026 com área de 2025.
              </CardFooter>
            </Card>

            <Card>
              <CardHeader className="flex items-start justify-between gap-3">
                <CardTitle>Geração centralizada</CardTitle>
                <ClasseBadge classe="A" />
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3">
                <Dado
                  rotulo="Usinas em operação"
                  valor={num(ficha.siga?.usinas ?? 0)}
                  unidade=""
                />
                <Dado
                  rotulo="Potência fiscalizada"
                  valor={num(ficha.siga?.mw ?? 0, 1)}
                  unidade="MW"
                />
              </CardContent>
              <CardFooter>
                ANEEL SIGA, coleta de 11/11/2026. Zero aqui significa nenhuma
                usina georreferenciada associada ao município, não ausência
                comprovada.
              </CardFooter>
            </Card>

            <Card>
              <CardHeader className="flex items-start justify-between gap-3">
                <CardTitle>Geração distribuída</CardTitle>
                <ClasseBadge classe="A" />
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-3">
                <Dado
                  rotulo="Instalações"
                  valor={num(ficha.mmgd?.n ?? null)}
                  unidade=""
                />
                <Dado
                  rotulo="Potência instalada"
                  valor={num(ficha.mmgd?.mw ?? null, 1)}
                  unidade="MW"
                />
                <Dado
                  rotulo="Por habitante"
                  valor={num(kwPorHab, 2)}
                  unidade="kW/hab"
                  classe="B"
                />
              </CardContent>
              <CardFooter>
                ANEEL MMGD, retrato de 11/2026. Não se soma à geração
                centralizada. Muitas instalações não provam saturação de
                mercado.
              </CardFooter>
            </Card>

            <Card>
              <CardHeader className="flex items-start justify-between gap-3">
                <CardTitle>Pecuária</CardTitle>
                <ClasseBadge classe="A" />
              </CardHeader>
              <CardContent>
                {ficha.pecuaria?.length ? (
                  <ul className="space-y-2">
                    {ficha.pecuaria.map((p) => (
                      <li
                        key={p.nome}
                        className="flex items-center justify-between border-b border-line/60 pb-1.5 text-sm last:border-0"
                      >
                        <span className="text-ink">{p.nome}</span>
                        <span className="font-display font-bold text-forest tabular-nums">
                          {p.valor === null ? (
                            <span className="text-xs font-normal text-muted">
                              sem dado
                            </span>
                          ) : (
                            <>
                              {num(p.valor)}
                              <span className="ml-1 text-xs font-normal lowercase text-muted">
                                {p.unidade}
                              </span>
                            </>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted">
                    Painel agropecuário indisponível.
                  </p>
                )}
              </CardContent>
              <CardFooter>
                IBGE, Pesquisa da Pecuária Municipal 2025. Efetivo de rebanho não
                é resíduo disponível para biogás.
              </CardFooter>
            </Card>
          </div>

          {ficha.cobertura && (
            <section>
              <SecaoTitulo
                titulo="Cobertura e uso da terra"
                descricao="Percentual da área mapeada por satélite em 2025, não da área oficial."
              />
              <Card className="px-5 py-5">
                <div className="flex h-4 overflow-hidden rounded-full">
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
                <ul className="mt-4 grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
                  {[...ficha.cobertura]
                    .sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))
                    .map((c) => (
                      <li
                        key={c.nome}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="flex items-center gap-2 text-ink">
                          <span
                            className="h-2.5 w-2.5 rounded-sm"
                            style={{ background: c.cor }}
                          />
                          {c.nome}
                        </span>
                        <span className="font-semibold tabular-nums text-forest">
                          {num(c.pct, 1)}%
                        </span>
                      </li>
                    ))}
                </ul>
                <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-muted">
                  MapBiomas Coleção 11. Floresta mapeada não é área protegida, e
                  a diferença entre anos não é taxa de desmatamento.
                </p>
              </Card>
            </section>
          )}

          <div className="flex flex-wrap gap-2">
            <Badge>Dados oficiais em retratos datados</Badge>
            <Badge>Não é tempo real</Badge>
            <Badge>Não indica viabilidade</Badge>
          </div>
        </motion.div>
      )}
    </Pagina>
  );
}

function Dado({
  rotulo,
  valor,
  unidade,
  classe,
}: {
  rotulo: string;
  valor: string;
  unidade: string;
  classe?: "A" | "B" | "C";
}) {
  return (
    <div className="rounded-xl border border-line px-3 py-2.5">
      <p className="text-[10px] font-bold tracking-wider text-muted uppercase">
        {rotulo}
      </p>
      <p className="mt-1 font-display text-xl leading-none font-bold text-forest">
        {valor}
        {unidade && (
          <span className="ml-1 text-[11px] font-semibold text-muted">
            {unidade}
          </span>
        )}
      </p>
      {classe === "B" && (
        <p className="mt-1 text-[10px] text-muted">indicador calculado</p>
      )}
    </div>
  );
}
