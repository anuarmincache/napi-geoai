"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import type { FeatureCollection, Geometry } from "geojson";
import Link from "next/link";
import { Hero } from "@/components/hero";
import { Kpis } from "@/components/kpis";
import { MapaMunicipios } from "@/components/mapa-municipios";
import { FichaMunicipio } from "@/components/ficha-municipio";
import {
  ClassesMmgd,
  CoberturaNoTempo,
  Lavouras,
  TecnologiaSiga,
} from "@/components/graficos";
import {
  Avisos,
  CabecalhoPagina,
  Carregando,
  Indisponivel,
  Pagina,
  SecaoTitulo,
} from "@/components/pagina";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ClasseBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Camada,
  Ficha,
  PropsMunicipio,
  Resumo,
  Series,
  num,
} from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";
import { cn } from "@/lib/utils";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

export default function Painel() {
  const resumo = useDados<Resumo>("resumo.json");
  const malha = useDados<Malha>("municipios.geojson");
  const series = useDados<Series>("series.json");
  const fichas = useDados<Record<string, Ficha>>("fichas.json");

  const [camadaId, setCamadaId] = useState("mmgd_mw");
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const camada: Camada | null = useMemo(
    () => resumo.dados?.camadas.find((c) => c.id === camadaId) ?? null,
    [resumo.dados, camadaId],
  );

  const valores = useMemo(() => {
    const saida: Record<string, number | null> = {};
    if (!malha.dados || !camada) return saida;
    for (const f of malha.dados.features) {
      const bruto = f.properties[camada.id];
      saida[f.properties.cd] =
        bruto === null || bruto === undefined ? null : Number(bruto);
    }
    return saida;
  }, [malha.dados, camada]);

  const ranking = useMemo(() => {
    if (!malha.dados || !camada) return [];
    return malha.dados.features
      .map((f) => ({
        cd: f.properties.cd,
        nome: f.properties.nome,
        valor: valores[f.properties.cd],
      }))
      .filter((r): r is { cd: string; nome: string; valor: number } =>
        Number.isFinite(r.valor as number),
      )
      .sort((a, b) => b.valor - a.valor)
      .slice(0, 8);
  }, [malha.dados, camada, valores]);

  if (resumo.erro) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Comece aqui"
          titulo="Painel geral"
          descricao="Visão do Paraná a partir dos dados oficiais do projeto."
        />
        <Indisponivel
          detalhe={`${resumo.erro}. Gere os arquivos com "python scripts/build_web_data.py".`}
        />
      </Pagina>
    );
  }

  return (
    <Pagina>
      {resumo.dados ? <Hero resumo={resumo.dados} /> : <Carregando altura="h-72" />}

      {resumo.dados ? (
        <Kpis kpis={resumo.dados.kpis} />
      ) : (
        <Carregando altura="h-32" />
      )}

      <section>
        <SecaoTitulo
          titulo="O Paraná município a município"
          descricao="Escolha o indicador e clique em um município para abrir a ficha dele."
        />

        {resumo.dados && (
          <div className="mb-3 flex flex-wrap gap-2">
            {resumo.dados.camadas.map((c) => (
              <Button
                key={c.id}
                size="sm"
                variant={c.id === camadaId ? "default" : "outline"}
                onClick={() => setCamadaId(c.id)}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: c.cor }}
                />
                {c.rotulo}
              </Button>
            ))}
          </div>
        )}

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="overflow-hidden p-0">
            {camada && malha.dados ? (
              <MapaMunicipios
                malha={malha.dados}
                valores={valores}
                rotulo={camada.rotulo}
                unidade={camada.unidade}
                cor={camada.cor}
                escala={camada.escala ?? "zero"}
                selecionado={selecionado}
                onSelecionar={setSelecionado}
                altura="h-[460px] lg:h-[560px]"
              />
            ) : (
              <div className="grid h-[460px] place-items-center bg-[#0c1d15] text-sm text-white/60 lg:h-[560px]">
                Carregando os 399 municípios…
              </div>
            )}
            {camada && (
              <CardFooter className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {camada.descricao} Fonte: {camada.fonte}.
                </span>
                <ClasseBadge classe={camada.classe} />
              </CardFooter>
            )}
          </Card>

          <div className="space-y-4">
            <Card className="p-5 lg:min-h-[348px]">
              <FichaMunicipio
                ficha={
                  selecionado && fichas.dados ? fichas.dados[selecionado] : null
                }
                onFechar={() => setSelecionado(null)}
              />
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Maiores valores · {camada?.rotulo ?? ""}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {ranking.map((r, i) => (
                  <button
                    key={r.cd}
                    onClick={() => setSelecionado(r.cd)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:bg-paper",
                      selecionado === r.cd && "bg-paper",
                    )}
                  >
                    <span className="w-4 shrink-0 text-xs font-bold text-muted">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-ink">
                      {r.nome}
                    </span>
                    <span className="shrink-0 font-display text-sm font-bold text-forest">
                      {num(r.valor, r.valor < 10 ? 2 : 0)}
                    </span>
                  </button>
                ))}
                <p className="pt-1 text-[11px] leading-snug text-muted">
                  Ordenação descritiva, não é ranking de aptidão.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section>
        <SecaoTitulo
          titulo="Energia e território em números"
          descricao="Os mesmos dados do mapa, vistos por tema."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          <PainelGrafico
            titulo="Cobertura e uso da terra, 1985 a 2025"
            rodape="MapBiomas Coleção 11. Diferença de estoque entre anos, não é taxa de desmatamento."
            href="/cobertura"
          >
            {series.dados ? (
              <CoberturaNoTempo series={series.dados} />
            ) : (
              <Carregando altura="h-72" />
            )}
          </PainelGrafico>

          <PainelGrafico
            titulo="Geração distribuída por classe de consumo"
            rodape="ANEEL MMGD, retrato de 11/2026. Contagem de instalações."
            href="/geracao-distribuida"
          >
            {series.dados ? (
              <ClassesMmgd series={series.dados} />
            ) : (
              <Carregando />
            )}
          </PainelGrafico>

          <PainelGrafico
            titulo="Usinas em operação por tecnologia"
            rodape="ANEEL SIGA, 11/11/2026. Potência fiscalizada, não é energia gerada."
            href="/usinas"
          >
            {series.dados ? (
              <TecnologiaSiga series={series.dados} />
            ) : (
              <Carregando />
            )}
          </PainelGrafico>

          <PainelGrafico
            titulo="Maiores áreas plantadas"
            rodape="IBGE PAM 2025. Área plantada não é cobertura do solo."
            href="/agricultura"
          >
            {series.dados ? <Lavouras series={series.dados} /> : <Carregando />}
          </PainelGrafico>
        </div>
      </section>

      {resumo.dados && <Avisos itens={resumo.dados.avisos} />}
    </Pagina>
  );
}

function PainelGrafico({
  titulo,
  rodape,
  href,
  children,
}: {
  titulo: string;
  rodape: string;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
    >
      <Card className="h-full">
        <CardHeader className="flex items-start justify-between gap-3">
          <CardTitle>{titulo}</CardTitle>
          <Link
            href={href}
            className="shrink-0 text-xs font-semibold text-moss hover:underline"
          >
            ver aba →
          </Link>
        </CardHeader>
        <CardContent>{children}</CardContent>
        <CardFooter>{rodape}</CardFooter>
      </Card>
    </motion.div>
  );
}
