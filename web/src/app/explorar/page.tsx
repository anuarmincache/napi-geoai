"use client";

import { useMemo, useState } from "react";
import type { FeatureCollection, Geometry } from "geojson";
import Link from "next/link";
import { MapaMunicipios } from "@/components/mapa-municipios";
import { BuscaMunicipio } from "@/components/busca-municipio";
import {
  Avisos,
  CabecalhoPagina,
  Carregando,
  Indisponivel,
  Pagina,
  SecaoTitulo,
} from "@/components/pagina";
import { TabelaMunicipios } from "@/components/tabela-municipios";
import { Card, CardFooter } from "@/components/ui/card";
import { ClasseBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Camada, PropsMunicipio, Resumo, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

export default function Explorar() {
  const malha = useDados<Malha>("municipios.geojson");
  const resumo = useDados<Resumo>("resumo.json");
  const [camadaId, setCamadaId] = useState("habitantes");
  const [a, setA] = useState<string | null>("4115200");
  const [b, setB] = useState<string | null>("4106902");

  const camada: Camada | null =
    resumo.dados?.camadas.find((c) => c.id === camadaId) ?? null;

  const props = useMemo(() => {
    const mapa: Record<string, PropsMunicipio> = {};
    for (const f of malha.dados?.features ?? []) {
      mapa[f.properties.cd] = f.properties;
    }
    return mapa;
  }, [malha.dados]);

  const opcoes = useMemo(
    () =>
      Object.values(props)
        .map((p) => ({ cd: p.cd, nome: p.nome }))
        .sort((x, y) => x.nome.localeCompare(y.nome, "pt-BR")),
    [props],
  );

  const valores = useMemo(() => {
    const saida: Record<string, number | null> = {};
    if (!camada) return saida;
    for (const p of Object.values(props)) {
      const bruto = p[camada.id];
      saida[p.cd] = bruto === null || bruto === undefined ? null : Number(bruto);
    }
    return saida;
  }, [props, camada]);

  if (malha.erro) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Comece aqui"
          titulo="Explorar o mapa do Paraná"
          descricao="Os 399 municípios, com busca e comparação."
        />
        <Indisponivel detalhe="A malha municipal não está disponível." />
      </Pagina>
    );
  }

  const mA = a ? props[a] : null;
  const mB = b ? props[b] : null;

  return (
    <Pagina>
      <CabecalhoPagina
        secao="Comece aqui"
        titulo="Explorar o mapa do Paraná"
        descricao="Os 399 municípios em um mapa, com busca por nome ou código IBGE e comparação lado a lado. Os contornos são simplificados para carregar rápido; a área exibida é a oficial do IBGE."
      />

      <section>
        <SecaoTitulo
          titulo="Mapa dos 399 municípios"
          descricao="Escolha o indicador. Passe o cursor para ver os valores."
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
        <Card className="overflow-hidden p-0">
          {malha.dados && camada ? (
            <MapaMunicipios
              malha={malha.dados}
              valores={valores}
              rotulo={camada.rotulo}
              unidade={camada.unidade}
              cor={camada.cor}
              selecionado={a}
              onSelecionar={(cd) => setA(cd)}
              altura="h-[520px] lg:h-[580px]"
            />
          ) : (
            <Carregando altura="h-[520px]" />
          )}
          {camada && (
            <CardFooter className="flex flex-wrap items-center justify-between gap-2">
              <span>
                {camada.descricao} Fonte: {camada.fonte}. Clicar escolhe o
                município A da comparação.
              </span>
              <ClasseBadge classe={camada.classe} />
            </CardFooter>
          )}
        </Card>
      </section>

      <section>
        <SecaoTitulo
          titulo="Comparar dois municípios"
          descricao="Mesma unidade, mesma data de referência. A comparação é descritiva."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          {[
            { rotulo: "Município A", valor: a, set: setA, m: mA },
            { rotulo: "Município B", valor: b, set: setB, m: mB },
          ].map((lado) => (
            <Card key={lado.rotulo} className="px-5 py-5">
              <p className="font-display text-[11px] font-bold tracking-wider text-muted uppercase">
                {lado.rotulo}
              </p>
              <div className="mt-2">
                <BuscaMunicipio
                  opcoes={opcoes}
                  valor={lado.valor}
                  onEscolher={lado.set}
                />
              </div>
              {lado.m && (
                <>
                  <h3 className="mt-4 font-display text-xl font-bold text-forest">
                    {lado.m.nome}
                  </h3>
                  <dl className="mt-3 grid grid-cols-2 gap-3">
                    <Linha
                      rotulo="População"
                      valor={num(lado.m.habitantes)}
                      unidade="hab"
                    />
                    <Linha
                      rotulo="Área"
                      valor={num(lado.m.area_km2, 1)}
                      unidade="km²"
                    />
                    <Linha
                      rotulo="Geração distribuída"
                      valor={num(lado.m.mmgd_mw, 1)}
                      unidade="MW"
                    />
                    <Linha
                      rotulo="Usinas"
                      valor={num(lado.m.siga_usinas)}
                      unidade=""
                    />
                  </dl>
                  <Link
                    href="/ficha"
                    className="mt-4 inline-block text-sm font-semibold text-moss hover:underline"
                  >
                    Ver a ficha completa →
                  </Link>
                </>
              )}
            </Card>
          ))}
        </div>

        {mA && mB && (
          <Card className="mt-4 px-5 py-4">
            <p className="text-sm leading-relaxed text-ink">
              <strong className="text-forest">{mA.nome}</strong> tem{" "}
              {num(mA.area_km2, 1)} km² e {num(mA.habitantes)} habitantes;{" "}
              <strong className="text-forest">{mB.nome}</strong> tem{" "}
              {num(mB.area_km2, 1)} km² e {num(mB.habitantes)} habitantes. A
              diferença de área é de{" "}
              {num(Math.abs((mA.area_km2 ?? 0) - (mB.area_km2 ?? 0)), 1)} km².
            </p>
            <p className="mt-2 text-[12px] leading-relaxed text-muted">
              Comparação descritiva de valores oficiais. Não indica qual
              município é mais adequado para qualquer finalidade.
            </p>
          </Card>
        )}
      </section>

      <section>
        <SecaoTitulo titulo="Todos os municípios" />
        {malha.dados ? (
          <TabelaMunicipios
            linhas={Object.values(props).map((p) => ({
              cd: p.cd,
              nome: p.nome,
              valores: {
                "População": p.habitantes,
                "Área (km²)": p.area_km2,
                "Densidade (hab/km²)": p.densidade,
                "MMGD (MW)": p.mmgd_mw,
                "Usinas": p.siga_usinas,
              },
            }))}
            colunas={[
              "População",
              "Área (km²)",
              "Densidade (hab/km²)",
              "MMGD (MW)",
              "Usinas",
            ]}
            casas={{
              "Área (km²)": 1,
              "Densidade (hab/km²)": 1,
              "MMGD (MW)": 1,
            }}
            selecionado={a}
            onSelecionar={setA}
            nomeArquivo="napi_geoai_municipios"
          />
        ) : (
          <Carregando altura="h-96" />
        )}
      </section>

      <Avisos
        itens={[
          "Os contornos do mapa são simplificados para carregar rápido; a área exibida é a oficial do IBGE, não uma medida feita sobre o desenho.",
          "População é estimativa do IBGE para 01/07/2026, não resultado de Censo.",
          "A ordenação e a comparação são descritivas e não indicam aptidão.",
        ]}
      />
    </Pagina>
  );
}

function Linha({
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
        {valor}
        {unidade && (
          <span className="ml-1 text-[11px] font-semibold text-muted">
            {unidade}
          </span>
        )}
      </dd>
    </div>
  );
}
