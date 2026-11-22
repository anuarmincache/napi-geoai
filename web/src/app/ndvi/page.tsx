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
import { Ndvi, PropsMunicipio, num } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

type Malha = FeatureCollection<Geometry, PropsMunicipio>;

export default function NdviPagina() {
  const ndvi = useDados<Ndvi>("ndvi.json");
  const malha = useDados<Malha>("municipios.geojson");
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const dados = ndvi.dados;

  // O mapa é categórico: cada situação tem a sua cor, igual à legenda.
  const { cores, textos } = useMemo(() => {
    const porCodigo = Object.fromEntries(
      (dados?.situacoes ?? []).map((s) => [s.codigo, s]),
    );
    const cores: Record<string, string> = {};
    const textos: Record<string, string> = {};
    for (const m of dados?.municipios ?? []) {
      const situacao = porCodigo[m.situacao];
      if (situacao) cores[m.cd] = situacao.cor;
      textos[m.cd] = m.rotulo;
    }
    return { cores, textos };
  }, [dados]);

  const publicados =
    dados?.situacoes.find((s) => s.codigo === "publicado")?.quantidade ?? 0;
  const medidos =
    dados?.situacoes.find((s) => s.codigo === "medido")?.quantidade ?? 0;

  if (ndvi.erro || (!ndvi.carregando && !dados)) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Território"
          titulo="Vegetação por satélite"
          descricao="Índice de vegetação (NDVI) a partir de imagens Sentinel-2."
        />
        <Indisponivel detalhe="A lista de municípios-alvo não está disponível." />
      </Pagina>
    );
  }

  return (
    <Pagina>
      <CabecalhoPagina
        secao="Território"
        titulo="Vegetação por satélite"
        descricao="O índice de vegetação (NDVI) virá de imagens Sentinel-2 do programa Copernicus. NDVI é um índice espectral: não é biomassa, produtividade, potencial de biogás nem viabilidade."
      >
        <div className="flex flex-wrap gap-2">
          <Badge variant="escuro">Em andamento</Badge>
          <Badge variant="escuro">Sentinel-2 L2A, 10 m</Badge>
          <Badge variant="escuro">Nenhum mapa publicado</Badge>
        </div>
      </CabecalhoPagina>

      {publicados === 0 && dados && (
        <div className="rounded-2xl border border-sun/40 bg-sun/10 px-5 py-4 text-sm leading-relaxed text-[#5c4500]">
          <strong>Nenhum mapa de NDVI está publicado ainda.</strong> Dos{" "}
          {num(dados.total)} municípios da lista, {num(medidos)} tem cena real
          medida e o restante aguarda processamento. Esta página mostra o
          andamento, sem preencher o que falta.
        </div>
      )}

      {dados ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Numero rotulo="Municípios na lista" valor={num(dados.total)} />
          <Numero rotulo="Área somada" valor={`${num(dados.area_km2)} km²`} />
          <Numero rotulo="Com cena medida" valor={num(medidos + publicados)} />
          <Numero rotulo="Com NDVI publicado" valor={num(publicados)} alerta />
        </div>
      ) : (
        <Carregando altura="h-28" />
      )}

      <section>
        <SecaoTitulo
          titulo="Situação de cada município"
          descricao={dados?.regra}
        />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <Card className="overflow-hidden p-0">
            {malha.dados && dados ? (
              <MapaMunicipios
                malha={malha.dados}
                valores={{}}
                rotulo="Andamento do NDVI"
                unidade=""
                cor="#73a535"
                corPorMunicipio={cores}
                textoPorMunicipio={textos}
                legenda={dados.situacoes.map((s) => ({
                  cor: s.cor,
                  rotulo: `${s.rotulo} (${num(s.quantidade)})`,
                }))}
                selecionado={selecionado}
                onSelecionar={setSelecionado}
              />
            ) : (
              <Carregando altura="h-[520px]" />
            )}
            <CardFooter className="flex flex-wrap items-center justify-between gap-2">
              <span>
                Municípios fora da lista (até 20 mil habitantes) aparecem como
                sem dado. {dados?.nota_aoi}
              </span>
              <ClasseBadge classe="B" />
            </CardFooter>
          </Card>

          <div className="space-y-4">
            <Card className="px-5 py-5">
              <p className="font-display text-sm font-bold text-forest">
                Situação
              </p>
              <ul className="mt-3 space-y-2">
                {dados?.situacoes.map((s) => (
                  <li
                    key={s.codigo}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="flex items-center gap-2 text-ink">
                      <span
                        className="h-2.5 w-2.5 rounded-sm"
                        style={{ background: s.cor }}
                      />
                      {s.rotulo}
                    </span>
                    <span className="font-display font-bold text-forest">
                      {num(s.quantidade)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="px-5 py-5">
              <p className="font-display text-sm font-bold text-forest">
                Grade do satélite
              </p>
              <ul className="mt-2 space-y-1 text-sm text-ink">
                {Object.entries(dados?.por_zona_utm ?? {}).map(([zona, qtd]) => (
                  <li key={zona} className="flex justify-between">
                    <span>Zona UTM EPSG:{zona}</span>
                    <span className="font-semibold">{num(qtd)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] leading-snug text-muted">
                O motor de cálculo só foi exercitado na zona 22 Sul.
              </p>
            </Card>
          </div>
        </div>
      </section>

      {dados?.plano && (
        <section>
          <SecaoTitulo
            titulo="Plano do ciclo"
            descricao="Consulta ao catálogo oficial do Copernicus, sem baixar imagem."
          />
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Numero
              rotulo="Com passagem útil"
              valor={`${num(dados.plano.com_passagem)}/${num(dados.total)}`}
            />
            <Numero rotulo="Cenas distintas" valor={num(dados.plano.cenas)} />
            <Numero
              rotulo="Etapa 1 · só máscara"
              valor={`${num(dados.plano.bytes_mascara / 1e6)} MB`}
            />
            <Numero
              rotulo="Etapa 2 · bandas, no máximo"
              valor={`${num(dados.plano.bytes_bandas / 1e9, 1)} GB`}
            />
          </div>
          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Como as cenas são escolhidas</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm leading-relaxed text-muted">
              <p>{dados.plano.regra_selecao}</p>
              {dados.plano.anterior && (
                <p>
                  A regra anterior, que pegava a passagem mais recente sem olhar
                  nuvem, exigiria{" "}
                  {num(dados.plano.anterior / 1e9, 2)} GB e baixaria cenas que
                  seriam reprovadas depois.
                </p>
              )}
              {dados.plano.sem_passagem.length > 0 && (
                <p>
                  <strong className="text-forest">
                    Sem passagem aproveitável na janela:
                  </strong>{" "}
                  {dados.plano.sem_passagem.join(", ")}.
                </p>
              )}
            </CardContent>
            <CardFooter>
              Janela de {dados.plano.janela_dias} dias. Nuvem máxima aceita:{" "}
              {num(dados.plano.nuvem_maxima)}%.{" "}
              {dados.plano.limites.join(" ")}
            </CardFooter>
          </Card>
        </section>
      )}

      <section>
        <SecaoTitulo titulo="Municípios da lista" />
        {dados ? (
          <TabelaMunicipios
            linhas={dados.municipios.map((m) => ({
              cd: m.cd,
              nome: m.nome,
              valores: {
                "População": m.populacao,
                "Área (km²)": m.area_km2,
                "Zona UTM": `EPSG:${m.zona_utm}`,
                "Situação": m.rotulo,
                "Pixels válidos (%)":
                  m.fracao_valida === null
                    ? null
                    : Number((m.fracao_valida * 100).toFixed(1)),
              },
            }))}
            colunas={[
              "População",
              "Área (km²)",
              "Zona UTM",
              "Situação",
              "Pixels válidos (%)",
            ]}
            casas={{ "Área (km²)": 1, "Pixels válidos (%)": 1 }}
            selecionado={selecionado}
            onSelecionar={setSelecionado}
            nomeArquivo="napi_geoai_ndvi"
          />
        ) : (
          <Carregando altura="h-96" />
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Como o NDVI é calculado e o que ele não diz</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm leading-relaxed text-muted">
          <p className="rounded-xl bg-paper px-4 py-3 text-center font-display text-base text-forest">
            NDVI = (B08 − B04) ÷ (B08 + B04)
          </p>
          <p>
            B08 é o infravermelho próximo e B04 é o vermelho, em reflectância de
            superfície (Sentinel-2 L2A, 10 m).
          </p>
          <p>
            Pixels com nuvem, sombra ou sem dado são retirados pela camada de
            classificação e ficam sem valor. Não viram zero.
          </p>
          <p>
            Cada município usa uma única passagem do satélite. Datas não são
            misturadas, então em períodos nublados pode não haver imagem válida.
          </p>
          <p>
            NDVI indica vigor de vegetação. Não mede produção, biomassa
            disponível nem aptidão para qualquer empreendimento.
          </p>
        </CardContent>
      </Card>

      <Avisos
        itens={[
          "Nenhum mapa de NDVI foi publicado: a página mostra o andamento real.",
          "A área analisada é o município inteiro, incluindo a zona rural.",
          "Cobertura do catálogo não é fração de pixels válidos; a fração só existe depois da leitura das bandas.",
        ]}
      />
    </Pagina>
  );
}

function Numero({
  rotulo,
  valor,
  alerta = false,
}: {
  rotulo: string;
  valor: string;
  alerta?: boolean;
}) {
  return (
    <Card className={`px-5 py-4 ${alerta ? "border-sun/50 bg-sun/5" : ""}`}>
      <p className="font-display text-[11px] font-bold tracking-[0.12em] text-muted uppercase">
        {rotulo}
      </p>
      <p
        className={`mt-1.5 font-display text-[1.8rem] leading-none font-bold ${
          alerta ? "text-[#8a6a00]" : "text-forest"
        }`}
      >
        {valor}
      </p>
    </Card>
  );
}
