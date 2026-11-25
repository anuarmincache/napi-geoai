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
import { Energia, PropsMunicipio, nomeTecnologia, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

export default function Usinas() {
  const energia = useDados<Energia>("energia.json");
  const malha = useDados<Malha>("municipios.geojson");
  const [tipo, setTipo] = useState<string | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const siga = energia.dados?.siga ?? null;

  const escopo = useMemo(() => {
    if (!siga)
      return {
        mw: 0,
        usinas: 0,
        valores: {} as Record<string, number | null>,
      };
    const valores: Record<string, number | null> = {};
    let mw = 0;
    let usinas = 0;
    for (const m of siga.municipios) {
      const valor = tipo ? (m.por_tipo[tipo] ?? 0) : m.mw_fiscalizada;
      valores[m.cd] = valor;
      mw += valor;
      usinas += m.n;
    }
    return { mw, usinas, valores };
  }, [siga, tipo]);

  const tecnologias = useMemo(
    () =>
      Object.entries(siga?.totais.por_tipo ?? {}).sort((a, b) => b[1] - a[1]),
    [siga],
  );

  if (energia.erro || (!energia.carregando && !siga)) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Energia"
          titulo="Usinas e geração centralizada"
          descricao="Usinas em operação no Paraná, segundo a ANEEL."
        />
        <Indisponivel detalhe="O painel de usinas não está disponível." />
      </Pagina>
    );
  }

  return (
    <Pagina>
      <CabecalhoPagina
        secao="Energia"
        titulo="Usinas e geração centralizada"
        descricao="Usinas em operação por município e tecnologia. Potência fiscalizada, potência outorgada e energia gerada são coisas diferentes."
      >
        {siga && (
          <div className="flex flex-wrap gap-2">
            <Badge variant="escuro">Fase: {siga.fase}</Badge>
            <Badge variant="escuro">Coleta de {siga.coleta}</Badge>
            <Badge variant="escuro">Fonte: ANEEL SIGA</Badge>
          </div>
        )}
      </CabecalhoPagina>

      {siga ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Numero
              rotulo={tipo ? `Potência · ${nomeTecnologia(tipo)}` : "Potência fiscalizada"}
              valor={`${num((tipo ? escopo.mw : siga.totais.mw) / 1000, 2)} GW`}
              detalhe={
                tipo
                  ? `${num(escopo.mw, 1)} MW somados nos municípios`
                  : `${num(siga.totais.mw, 1)} MW no estado, dos quais ${num(escopo.mw, 1)} MW aparecem no mapa`
              }
            />
            <Numero
              rotulo="Usinas em operação"
              valor={num(tipo ? (siga.totais.usinas_por_tipo[tipo] ?? 0) : siga.totais.usinas)}
              detalhe={
                tipo
                  ? "desta tecnologia, vinculadas a um município"
                  : "no estado, em todas as tecnologias"
              }
            />
            <Numero
              rotulo="Usinas sem município"
              valor={num(siga.totais.nao_associados)}
              detalhe={`${num(siga.totais.mw_nao_associados, 1)} MW não aparecem no mapa`}
            />
          </div>

          {siga.limitacao && (
            <p className="rounded-2xl border border-sun/40 bg-sun/10 px-5 py-3 text-sm leading-relaxed text-[#5c4500]">
              {siga.limitacao}
            </p>
          )}
        </>
      ) : (
        <Carregando altura="h-28" />
      )}

      <section>
        <SecaoTitulo
          titulo="Onde estão as usinas"
          descricao="Filtre por tecnologia. Cinza claro significa nenhuma usina associada ao município, não ausência comprovada."
        />
        <div className="mb-3 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={tipo === null ? "default" : "outline"}
            onClick={() => setTipo(null)}
          >
            Todas as tecnologias
          </Button>
          {tecnologias.map(([sigla, mw]) => (
            <Button
              key={sigla}
              size="sm"
              variant={tipo === sigla ? "default" : "outline"}
              onClick={() => setTipo(sigla)}
            >
              {nomeTecnologia(sigla)}
              <span className="text-[11px] font-normal opacity-70">
                {num(mw, 0)} MW
              </span>
            </Button>
          ))}
        </div>

        <Card className="overflow-hidden p-0">
          {malha.dados && siga ? (
            <MapaMunicipios
              malha={malha.dados}
              valores={escopo.valores}
              rotulo={tipo ? nomeTecnologia(tipo) : "Potência fiscalizada"}
              unidade="MW"
              cor="#73a535"
              casas={1}
              selecionado={selecionado}
              onSelecionar={setSelecionado}
            />
          ) : (
            <Carregando altura="h-[520px]" />
          )}
          <CardFooter className="flex flex-wrap items-center justify-between gap-2">
            <span>
              Potência fiscalizada das usinas associadas ao
              município, em MW. Não inclui geração distribuída e não é energia
              gerada (MWh). Cinza significa nenhuma usina associada, não
              ausência comprovada.
            </span>
            <ClasseBadge classe="A" />
          </CardFooter>
        </Card>
      </section>

      <Card>
        <CardHeader className="flex items-start justify-between gap-3">
          <CardTitle>Potência por tecnologia</CardTitle>
          <ClasseBadge classe="A" />
        </CardHeader>
        <CardContent>
          <ul className="space-y-2.5">
            {tecnologias.map(([sigla, mw]) => (
              <li key={sigla} className="flex items-center gap-3">
                <span className="w-52 shrink-0 truncate text-sm text-ink">
                  {nomeTecnologia(sigla)}
                </span>
                <div className="h-3 flex-1 overflow-hidden rounded-full bg-paper">
                  <div
                    className="h-full rounded-full bg-leaf"
                    style={{
                      width: `${(mw / (tecnologias[0]?.[1] || 1)) * 100}%`,
                    }}
                  />
                </div>
                <span className="w-24 shrink-0 text-right font-display text-sm font-bold text-forest tabular-nums">
                  {num(mw, 1)} MW
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
        <CardFooter>
          Potência fiscalizada, somada a partir dos municípios. Não é
          energia gerada (MWh).
        </CardFooter>
      </Card>

      <section>
        <SecaoTitulo
          titulo="Todos os municípios"
          descricao="Município sem usina associada aparece com zero. Isso significa nenhuma usina georreferenciada e vinculada no cadastro, não ausência comprovada."
        />
        {siga ? (
          <TabelaMunicipios
            linhas={siga.municipios.map((m) => ({
              cd: m.cd,
              nome: m.nome,
              valores: {
                Usinas: m.n,
                "Fiscalizada (MW)": m.mw_fiscalizada,
                "Outorgada (MW)": m.mw_outorgada,
              },
            }))}
            colunas={["Usinas", "Fiscalizada (MW)", "Outorgada (MW)"]}
            casas={{ "Fiscalizada (MW)": 1, "Outorgada (MW)": 1 }}
            selecionado={selecionado}
            onSelecionar={setSelecionado}
            nomeArquivo="napi_geoai_usinas"
          />
        ) : (
          <Carregando altura="h-96" />
        )}
      </section>

      <Avisos
        itens={[
          "Potência fiscalizada não é potência outorgada nem energia gerada (MWh).",
          "Geração centralizada (SIGA) e geração distribuída (MMGD) são cadastros diferentes e não se somam sem critério.",
          "Cada usina é associada ao município pelas coordenadas do cadastro; usinas sem coordenada ficam fora do mapa.",
          "A ordenação da tabela é descritiva e não indica aptidão para novos empreendimentos.",
        ]}
      />
    </Pagina>
  );
}

function Numero({
  rotulo,
  valor,
  detalhe,
}: {
  rotulo: string;
  valor: string;
  detalhe: string;
}) {
  return (
    <Card className="px-5 py-4">
      <p className="font-display text-[11px] font-bold tracking-[0.12em] text-muted uppercase">
        {rotulo}
      </p>
      <p className="mt-1.5 font-display text-[1.9rem] leading-none font-bold text-forest">
        {valor}
      </p>
      <p className="mt-2 text-sm text-muted">{detalhe}</p>
    </Card>
  );
}
