"use client";

import { useMemo, useState } from "react";
import type { FeatureCollection, Geometry } from "geojson";
import { MapaMunicipios } from "@/components/mapa-municipios";
import {
  Avisos,
  CabecalhoPagina,
  Carregando,
  Indisponivel,
  Pagina,
  SecaoTitulo,
} from "@/components/pagina";
import { TabelaMunicipios } from "@/components/tabela-municipios";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge, ClasseBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Agricultura, PropsMunicipio, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

type IndicadorLavoura = "area" | "colhida" | "producao" | "rendimento";

const INDICADORES: Record<
  IndicadorLavoura,
  { rotulo: string; curto: string; cor: string; casas: number; nota: string }
> = {
  area: {
    rotulo: "Área plantada",
    curto: "área plantada",
    cor: "#fcc817",
    casas: 0,
    nota: "Área plantada ou destinada à colheita, em hectares. Não é área mapeada por satélite.",
  },
  colhida: {
    rotulo: "Área colhida",
    curto: "área colhida",
    cor: "#e09f1c",
    casas: 0,
    nota: "Área efetivamente colhida, em hectares. A diferença em relação à área plantada indica perda de safra.",
  },
  producao: {
    rotulo: "Quantidade produzida",
    curto: "produção",
    cor: "#5b8a3a",
    casas: 0,
    nota: "Quantidade produzida no ano de referência, em toneladas.",
  },
  rendimento: {
    rotulo: "Rendimento médio",
    curto: "rendimento",
    cor: "#2f6b4f",
    casas: 0,
    nota: "Produção dividida pela área colhida, em quilogramas por hectare. É o indicador que separa município grande de município produtivo. Não se soma entre municípios.",
  },
};

const ROTULO_STATUS: Record<string, string> = {
  valor: "valor publicado",
  zero: "zero publicado",
  sigilo: "sigilo estatístico",
  nao_disponivel: "não disponível",
  sem_registro: "sem registro",
};

export default function AgriculturaPagina() {
  const agro = useDados<Agricultura>("agricultura.json");
  const malha = useDados<Malha>("municipios.geojson");
  const [aba, setAba] = useState<"lavoura" | "pecuaria">("lavoura");
  const [culturaId, setCulturaId] = useState<string | null>(null);
  const [indicador, setIndicador] = useState<IndicadorLavoura>("area");
  const [rebanhoKey, setRebanhoKey] = useState<string | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const dados = agro.dados;
  const cultura =
    dados?.culturas.find((c) => c.id === culturaId) ?? dados?.culturas[0] ?? null;
  const rebanho =
    dados?.rebanhos.find((r) => r.chave === rebanhoKey) ??
    dados?.rebanhos[0] ??
    null;

  const valores = useMemo(() => {
    const saida: Record<string, number | null> = {};
    if (aba === "lavoura" && cultura) {
      for (const [cd, v] of Object.entries(cultura.municipios)) {
        saida[cd] = v[indicador];
      }
    } else if (rebanho) {
      for (const [cd, v] of Object.entries(rebanho.municipios)) {
        saida[cd] = v.v;
      }
    }
    return saida;
  }, [aba, cultura, rebanho, indicador]);

  const rendimentoEstadual = useMemo(() => {
    const prod = cultura?.estado_producao.soma_publicada ?? null;
    const colhida = cultura?.estado_colhida.soma_publicada ?? null;
    if (prod === null || colhida === null || colhida <= 0) return null;
    return Math.round((prod / colhida) * 1000);
  }, [cultura]);

  const statusAtual =
    aba === "lavoura"
      ? cultura?.estado_area.contagem_por_status
      : rebanho?.estado.contagem_por_status;

  if (agro.erro || (!agro.carregando && !dados)) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Território"
          titulo="Agricultura e pecuária"
          descricao="Lavouras, rebanhos e leite por município, segundo o IBGE."
        />
        <Indisponivel detalhe="O painel agropecuário não está disponível." />
      </Pagina>
    );
  }

  return (
    <Pagina>
      <CabecalhoPagina
        secao="Território"
        titulo="Agricultura e pecuária"
        descricao="Lavouras, rebanhos e leite nos 399 municípios. Área plantada não é cobertura do solo, e efetivo de rebanho não é resíduo disponível para biogás."
      >
        {dados && (
          <div className="flex flex-wrap gap-2">
            <Badge variant="escuro">PAM {dados.ano_pam}</Badge>
            <Badge variant="escuro">PPM {dados.ano_ppm}</Badge>
            <Badge variant="escuro">Fonte: IBGE / SIDRA</Badge>
          </div>
        )}
      </CabecalhoPagina>

      <div className="flex flex-wrap gap-2">
        <Button
          variant={aba === "lavoura" ? "default" : "outline"}
          onClick={() => setAba("lavoura")}
        >
          Lavouras
        </Button>
        <Button
          variant={aba === "pecuaria" ? "default" : "outline"}
          onClick={() => setAba("pecuaria")}
        >
          Pecuária
        </Button>
      </div>

      {aba === "lavoura" ? (
        <>
          <section>
            <SecaoTitulo
              titulo={`${INDICADORES[indicador].rotulo} por município`}
              descricao="Escolha a cultura e o indicador. O rendimento mostra quanto cada hectare produziu, e não depende do tamanho do município."
            />
            <div className="mb-3 flex flex-wrap gap-2">
              {dados?.culturas.map((c) => (
                <Button
                  key={c.id}
                  size="sm"
                  variant={c.id === cultura?.id ? "default" : "outline"}
                  onClick={() => setCulturaId(c.id)}
                >
                  {c.nome.split(" (")[0]}
                </Button>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-paper px-3 py-2">
              <span className="text-[10px] font-bold tracking-wider text-muted uppercase">
                Indicador
              </span>
              {(Object.keys(INDICADORES) as IndicadorLavoura[]).map((k) => (
                <Button
                  key={k}
                  size="sm"
                  variant={k === indicador ? "default" : "outline"}
                  onClick={() => setIndicador(k)}
                >
                  {INDICADORES[k].rotulo}
                </Button>
              ))}
            </div>

            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
              <Card className="overflow-hidden p-0">
                {malha.dados && cultura ? (
                  <MapaMunicipios
                    malha={malha.dados}
                    valores={valores}
                    rotulo={`${cultura.nome.split(" (")[0]} · ${INDICADORES[indicador].curto}`}
                    unidade={
                      indicador === "producao"
                        ? "t"
                        : indicador === "rendimento"
                          ? "kg/ha"
                          : "ha"
                    }
                    cor={INDICADORES[indicador].cor}
                    escala={indicador === "rendimento" ? "faixa" : "zero"}
                    casas={INDICADORES[indicador].casas}
                    selecionado={selecionado}
                    onSelecionar={setSelecionado}
                  />
                ) : (
                  <Carregando altura="h-[520px]" />
                )}
                <CardFooter className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    IBGE, Produção Agrícola Municipal {dados?.ano_pam}.{" "}
                    {INDICADORES[indicador].nota}
                  </span>
                  <ClasseBadge classe="A" />
                </CardFooter>
              </Card>

              {cultura && (
                <Card className="px-5 py-5">
                  <p className="font-display text-sm font-bold text-forest">
                    {cultura.nome}
                  </p>
                  <dl className="mt-3 space-y-3">
                    <div>
                      <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
                        Área plantada no Paraná
                      </dt>
                      <dd className="font-display text-xl font-bold text-forest">
                        {num(cultura.estado_area.soma_publicada)}{" "}
                        <span className="text-xs font-semibold text-muted">
                          {cultura.unidade_area.toLowerCase()}
                        </span>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
                        Área colhida no Paraná
                      </dt>
                      <dd className="font-display text-xl font-bold text-forest">
                        {num(cultura.estado_colhida.soma_publicada)}{" "}
                        <span className="text-xs font-semibold text-muted">
                          {cultura.unidade_area.toLowerCase()}
                        </span>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
                        Quantidade produzida
                      </dt>
                      <dd className="font-display text-xl font-bold text-forest">
                        {num(cultura.estado_producao.soma_publicada)}{" "}
                        <span className="text-xs font-semibold text-muted">
                          {cultura.unidade_producao.toLowerCase()}
                        </span>
                      </dd>
                    </div>
                    {rendimentoEstadual !== null && (
                      <div>
                        <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
                          Rendimento médio no estado
                        </dt>
                        <dd className="font-display text-xl font-bold text-forest">
                          {num(rendimentoEstadual)}{" "}
                          <span className="text-xs font-semibold text-muted">
                            kg/ha
                          </span>
                        </dd>
                        <p className="mt-1 text-[11px] leading-snug text-muted">
                          Produção dividida pela área colhida do estado. É uma
                          média ponderada calculada aqui, não um número
                          publicado pelo IBGE.
                        </p>
                      </div>
                    )}
                  </dl>
                  <Situacoes contagem={statusAtual} />
                </Card>
              )}
            </div>
          </section>

          <section>
            <SecaoTitulo titulo="Todos os municípios" />
            {cultura && (
              <TabelaMunicipios
                key={cultura.id}
                linhas={Object.entries(cultura.municipios).map(([cd, v]) => ({
                  cd,
                  nome:
                    malha.dados?.features.find((f) => f.properties.cd === cd)
                      ?.properties.nome ?? cd,
                  valores: {
                    "Área plantada (ha)": v.area,
                    "Área colhida (ha)": v.colhida,
                    "Produção (t)": v.producao,
                    "Rendimento (kg/ha)": v.rendimento,
                    "Situação": ROTULO_STATUS[v.status] ?? v.status,
                  },
                }))}
                colunas={[
                  "Área plantada (ha)",
                  "Área colhida (ha)",
                  "Produção (t)",
                  "Rendimento (kg/ha)",
                  "Situação",
                ]}
                selecionado={selecionado}
                onSelecionar={setSelecionado}
                nomeArquivo={`napi_geoai_${cultura.nome.split(" (")[0].toLowerCase()}`}
              />
            )}
          </section>
        </>
      ) : (
        <>
          <section>
            <SecaoTitulo
              titulo="Rebanhos e leite por município"
              descricao="Efetivo de rebanho em 31/12 do ano de referência."
            />
            <div className="mb-3 flex flex-wrap gap-2">
              {dados?.rebanhos.map((r) => (
                <Button
                  key={r.chave}
                  size="sm"
                  variant={r.chave === rebanho?.chave ? "default" : "outline"}
                  onClick={() => setRebanhoKey(r.chave)}
                >
                  {r.nome}
                </Button>
              ))}
            </div>

            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
              <Card className="overflow-hidden p-0">
                {malha.dados && rebanho ? (
                  <MapaMunicipios
                    malha={malha.dados}
                    valores={valores}
                    rotulo={rebanho.nome}
                    unidade={rebanho.unidade.toLowerCase()}
                    cor="#5b8a3a"
                    casas={0}
                    selecionado={selecionado}
                    onSelecionar={setSelecionado}
                  />
                ) : (
                  <Carregando altura="h-[520px]" />
                )}
                <CardFooter className="flex flex-wrap items-center justify-between gap-2">
                  <span>{rebanho?.fonte}</span>
                  <ClasseBadge classe="A" />
                </CardFooter>
              </Card>

              {rebanho && (
                <Card className="px-5 py-5">
                  <p className="font-display text-sm font-bold text-forest">
                    {rebanho.nome}
                  </p>
                  <dt className="mt-3 text-[10px] font-bold tracking-wider text-muted uppercase">
                    Soma dos municípios
                  </dt>
                  <dd className="font-display text-2xl font-bold text-forest">
                    {num(rebanho.estado.soma_publicada)}{" "}
                    <span className="text-xs font-semibold text-muted">
                      {rebanho.unidade.toLowerCase()}
                    </span>
                  </dd>
                  <Situacoes contagem={statusAtual} />
                </Card>
              )}
            </div>
          </section>

          <section>
            <SecaoTitulo titulo="Todos os municípios" />
            {rebanho && (
              <TabelaMunicipios
                key={rebanho.chave}
                linhas={Object.entries(rebanho.municipios).map(([cd, v]) => ({
                  cd,
                  nome:
                    malha.dados?.features.find((f) => f.properties.cd === cd)
                      ?.properties.nome ?? cd,
                  valores: {
                    [rebanho.nome]: v.v,
                    "Situação": ROTULO_STATUS[v.s] ?? v.s,
                  },
                }))}
                colunas={[rebanho.nome, "Situação"]}
                selecionado={selecionado}
                onSelecionar={setSelecionado}
                nomeArquivo={`napi_geoai_${rebanho.chave}`}
              />
            )}
          </section>
        </>
      )}

      {dados && (
        <Card>
          <CardHeader>
            <CardTitle>De onde vêm estes números</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm leading-relaxed text-muted">
            {dados.fontes.map((linha, i) => (
              <p key={`${i}-${linha.slice(0, 24)}`}>{linha}</p>
            ))}
          </CardContent>
        </Card>
      )}

      {dados && <Avisos itens={dados.avisos} />}
    </Pagina>
  );
}

function Situacoes({ contagem }: { contagem?: Record<string, number> }) {
  if (!contagem) return null;
  const itens = Object.entries(contagem).filter(([, v]) => v > 0);
  if (!itens.length) return null;
  return (
    <div className="mt-4 border-t border-line pt-3">
      <p className="text-[10px] font-bold tracking-wider text-muted uppercase">
        Municípios por situação
      </p>
      <ul className="mt-1.5 space-y-1">
        {itens.map(([chave, qtd]) => (
          <li
            key={chave}
            className="flex items-center justify-between text-xs text-ink"
          >
            <span>{ROTULO_STATUS[chave] ?? chave}</span>
            <span className="font-semibold">{num(qtd)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] leading-snug text-muted">
        Zero publicado, sigilo e ausência de registro são coisas diferentes e
        aparecem separadas.
      </p>
    </div>
  );
}
