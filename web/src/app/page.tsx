"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import type { FeatureCollection, Geometry } from "geojson";
import { BarraLateral } from "@/components/barra-lateral";
import { Hero } from "@/components/hero";
import { Kpis } from "@/components/kpis";
import { MapaParana } from "@/components/mapa-parana";
import { FichaMunicipio } from "@/components/ficha-municipio";
import {
  ClassesMmgd,
  CoberturaNoTempo,
  Lavouras,
  TecnologiaSiga,
} from "@/components/graficos";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, ClasseBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MarcaNapi } from "@/components/marca";
import {
  Camada,
  Ficha,
  PropsMunicipio,
  Resumo,
  Series,
  carregar,
  num,
} from "@/lib/dados";
import { cn } from "@/lib/utils";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

export default function Painel() {
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [malha, setMalha] = useState<Malha | null>(null);
  const [series, setSeries] = useState<Series | null>(null);
  const [fichas, setFichas] = useState<Record<string, Ficha> | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [camadaId, setCamadaId] = useState("mmgd_mw");
  const [selecionado, setSelecionado] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      carregar<Resumo>("resumo.json"),
      carregar<Malha>("municipios.geojson"),
      carregar<Series>("series.json"),
      carregar<Record<string, Ficha>>("fichas.json"),
    ])
      .then(([r, m, s, f]) => {
        setResumo(r);
        setMalha(m);
        setSeries(s);
        setFichas(f);
      })
      .catch((e: Error) => setErro(e.message));
  }, []);

  const camada: Camada | null = useMemo(
    () => resumo?.camadas.find((c) => c.id === camadaId) ?? null,
    [resumo, camadaId],
  );

  const ranking = useMemo(() => {
    if (!malha || !camada) return [];
    return [...malha.features]
      .map((f) => ({
        cd: f.properties.cd,
        nome: f.properties.nome,
        valor: Number(f.properties[camada.id] ?? 0),
      }))
      .filter((r) => Number.isFinite(r.valor))
      .sort((a, b) => b.valor - a.valor)
      .slice(0, 8);
  }, [malha, camada]);

  if (erro) {
    return (
      <main className="grid min-h-screen place-items-center p-8">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Dados indisponíveis</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted">
            {erro}. Gere os arquivos com{" "}
            <code className="rounded bg-paper px-1">
              python scripts/build_web_data.py
            </code>
            . Nenhum número é exibido no lugar deles.
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <BarraLateral />

      <main className="min-w-0 flex-1 px-4 py-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-[1340px] space-y-8">
          {resumo ? <Hero resumo={resumo} /> : <Esqueleto altura="h-72" />}

          {resumo ? <Kpis kpis={resumo.kpis} /> : <Esqueleto altura="h-32" />}

          {resumo && (
            <p className="text-xs leading-relaxed text-muted">
              {resumo.avisos[0]} {resumo.avisos[1]}
            </p>
          )}

          {/* ---------------------------------------------------- mapa */}
          <section>
            <Cabecalho
              titulo="O Paraná município a município"
              descricao="Escolha o indicador e clique em um município para abrir a ficha dele."
            />

            {resumo && (
              <div className="mb-3 flex flex-wrap gap-2">
                {resumo.camadas.map((c) => (
                  <Button
                    key={c.id}
                    size="sm"
                    variant={c.id === camadaId ? "default" : "outline"}
                    onClick={() => setCamadaId(c.id)}
                    className={cn(c.id === camadaId && "shadow-sm")}
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
              <Card className="flex flex-col overflow-hidden p-0">
                <div className="h-[460px] w-full lg:h-[560px]">
                  {camada && malha ? (
                    <MapaParana
                      dados={malha}
                      camada={camada}
                      selecionado={selecionado}
                      onSelecionar={setSelecionado}
                    />
                  ) : (
                    <div className="grid h-full place-items-center bg-[#0c1d15] text-sm text-white/60">
                      Carregando os 399 municípios…
                    </div>
                  )}
                </div>
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
                    ficha={selecionado && fichas ? fichas[selecionado] : null}
                    onFechar={() => setSelecionado(null)}
                  />
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>
                      Maiores valores · {camada?.rotulo ?? ""}
                    </CardTitle>
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

          {/* -------------------------------------------------- gráficos */}
          <section>
            <Cabecalho
              titulo="Energia e território em números"
              descricao="Os mesmos artefatos que alimentam o mapa, vistos por tema."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <Painelzinho
                titulo="Cobertura e uso da terra, 1985 a 2025"
                rodape="MapBiomas Coleção 11. Diferença de estoque entre anos, não é taxa de desmatamento."
                classe="A"
              >
                {series ? <CoberturaNoTempo series={series} /> : <Esqueleto altura="h-72" />}
              </Painelzinho>

              <Painelzinho
                titulo="Geração distribuída por classe de consumo"
                rodape="ANEEL MMGD, retrato de 11/2026. Contagem de instalações."
                classe="A"
              >
                {series ? <ClassesMmgd series={series} /> : <Esqueleto altura="h-64" />}
              </Painelzinho>

              <Painelzinho
                titulo="Usinas em operação por tecnologia"
                rodape="ANEEL SIGA, 11/11/2026. Potência fiscalizada conhecida, não é energia gerada."
                classe="A"
              >
                {series ? <TecnologiaSiga series={series} /> : <Esqueleto altura="h-64" />}
              </Painelzinho>

              <Painelzinho
                titulo="Maiores áreas plantadas"
                rodape="IBGE PAM 2025. Área plantada não é cobertura do solo."
                classe="A"
              >
                {series ? <Lavouras series={series} /> : <Esqueleto altura="h-64" />}
              </Painelzinho>
            </div>
          </section>

          {/* ------------------------------------------------------ NDVI */}
          {resumo && (
            <motion.section
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5 }}
            >
              <Card className="overflow-hidden border-0 bg-[linear-gradient(120deg,#16231b,#2f4a33_60%,#3f6a2f)] text-white">
                <div className="grid gap-6 p-7 lg:grid-cols-[1.2fr_1fr] lg:items-center">
                  <div>
                    <Badge variant="escuro">Em andamento</Badge>
                    <h3 className="mt-3 font-display text-2xl font-bold">
                      Vegetação por satélite
                    </h3>
                    <p className="mt-2 max-w-xl text-sm leading-relaxed text-white/75">
                      O índice de vegetação (NDVI) virá de imagens Sentinel-2
                      para os municípios acima de 20 mil habitantes. Hoje o
                      portal mostra o andamento real: nenhum mapa foi publicado
                      ainda, e a página não preenche o que falta.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Metrica
                      rotulo="Municípios na lista"
                      valor={num(resumo.ndvi.municipios)}
                    />
                    <Metrica
                      rotulo="Com passagem útil"
                      valor={num(resumo.ndvi.com_passagem)}
                    />
                    <Metrica
                      rotulo="Cenas por ciclo"
                      valor={num(resumo.ndvi.cenas)}
                    />
                    <Metrica
                      rotulo="NDVI publicado"
                      valor={num(resumo.ndvi.publicados)}
                      alerta
                    />
                  </div>
                </div>
              </Card>
            </motion.section>
          )}

          {/* --------------------------------------------------- rodapé */}
          <footer className="rounded-2xl border border-line bg-white px-6 py-6">
            <div className="flex flex-wrap items-center gap-5">
              <MarcaNapi className="h-14 w-14" />
              <div className="min-w-[18rem] flex-1 text-sm leading-relaxed text-muted">
                <strong className="text-forest">NAPI GeoAI</strong> é uma
                iniciativa do NAPI Energia Zero-Carbono. Os indicadores apoiam a
                investigação e não substituem estudos de viabilidade técnica,
                ambiental ou econômica.
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge>Universidade Estadual de Maringá (UEM)</Badge>
                  <Badge>Fundação Araucária</Badge>
                </div>
              </div>
            </div>
            {resumo && (
              <ul className="mt-5 space-y-1 border-t border-line pt-4 text-[11px] leading-relaxed text-muted">
                {resumo.avisos.map((aviso) => (
                  <li key={aviso}>{aviso}</li>
                ))}
                <li>Dados gerados em {resumo.gerado_em}.</li>
              </ul>
            )}
          </footer>
        </div>
      </main>
    </div>
  );
}

function Cabecalho({
  titulo,
  descricao,
}: {
  titulo: string;
  descricao: string;
}) {
  return (
    <div className="mb-4">
      <h2 className="font-display text-2xl font-bold tracking-tight text-forest">
        {titulo}
      </h2>
      <p className="mt-1 text-sm text-muted">{descricao}</p>
    </div>
  );
}

function Painelzinho({
  titulo,
  rodape,
  classe,
  children,
}: {
  titulo: string;
  rodape: string;
  classe: "A" | "B" | "C";
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
          <ClasseBadge classe={classe} />
        </CardHeader>
        <CardContent>{children}</CardContent>
        <CardFooter>{rodape}</CardFooter>
      </Card>
    </motion.div>
  );
}

function Metrica({
  rotulo,
  valor,
  alerta = false,
}: {
  rotulo: string;
  valor: string;
  alerta?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-white/12 bg-white/8 px-4 py-3",
        alerta && "border-sun/40 bg-sun/10",
      )}
    >
      <p className="text-[10px] font-bold tracking-[0.14em] text-white/55 uppercase">
        {rotulo}
      </p>
      <p
        className={cn(
          "mt-1 font-display text-2xl font-bold",
          alerta ? "text-sun" : "text-white",
        )}
      >
        {valor}
      </p>
    </div>
  );
}

function Esqueleto({ altura }: { altura: string }) {
  return (
    <div className={cn("w-full animate-pulse rounded-2xl bg-line/60", altura)} />
  );
}
