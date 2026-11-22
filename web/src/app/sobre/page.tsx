"use client";

import Link from "next/link";
import { CabecalhoPagina, Pagina, SecaoTitulo } from "@/components/pagina";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const ETAPAS = [
  "Conhecer o território",
  "Explorar indicadores",
  "Comparar regiões",
  "Identificar sinais",
  "Investigar restrições",
  "Formular hipóteses",
  "Apoiar estudos de viabilidade",
];

export default function Sobre() {
  return (
    <Pagina largura="max-w-[980px]">
      <CabecalhoPagina
        secao="Transparência"
        titulo="Sobre o projeto"
        descricao="O NAPI GeoAI reúne dados públicos que ficam espalhados em vários órgãos e os apresenta por município, para ajudar quem precisa decidir onde investigar."
      >
        <div className="flex flex-wrap gap-2">
          <Badge variant="escuro">NAPI Energia Zero-Carbono</Badge>
          <Badge variant="escuro">UEM</Badge>
          <Badge variant="escuro">Fundação Araucária</Badge>
        </div>
      </CabecalhoPagina>

      <section>
        <SecaoTitulo titulo="Para que serve" />
        <Card className="px-6 py-5">
          <p className="text-[1.02rem] leading-relaxed text-ink">
            A plataforma reúne território, população, energia, agropecuária e
            cobertura da terra dos 399 municípios do Paraná. O objetivo é ajudar
            pesquisadores, empreendedores, cooperativas e gestores públicos a
            conhecer o território e a escolher o que merece um estudo mais
            profundo.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {ETAPAS.map((etapa, i) => (
              <span
                key={etapa}
                className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm font-semibold text-forest"
              >
                <span className="grid h-5 w-5 place-items-center rounded-full bg-sun text-[11px] text-[#3a2f00]">
                  {i + 1}
                </span>
                {etapa}
              </span>
            ))}
          </div>
        </Card>
      </section>

      <section>
        <SecaoTitulo titulo="O que a plataforma não faz" />
        <Card className="border-sun/40 bg-sun/5 px-6 py-5">
          <ul className="space-y-2 text-sm leading-relaxed text-ink">
            <li>Não declara viabilidade econômica de nenhum empreendimento.</li>
            <li>Não recomenda onde investir nem classifica municípios por aptidão.</li>
            <li>
              Não substitui projeto, licenciamento, parecer de acesso ou estudo
              técnico.
            </li>
            <li>
              Não funciona em tempo real: todos os números são retratos datados.
            </li>
          </ul>
        </Card>
      </section>

      <section>
        <SecaoTitulo titulo="Como tratamos os dados" />
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            {
              titulo: "Só fontes oficiais",
              texto:
                "IBGE, ANEEL, MapBiomas e Copernicus, com a fonte e a data ao lado de cada número.",
            },
            {
              titulo: "Ausência continua ausência",
              texto:
                "Quando um dado não existe, a página diz que não existe. Nada é preenchido.",
            },
            {
              titulo: "Cada número tem classe",
              texto:
                "Dado oficial, indicador calculado ou simulação, sempre identificados.",
            },
            {
              titulo: "Conferência antes de publicar",
              texto:
                "Cada arquivo preparado guarda proveniência, data de coleta e impressão digital.",
            },
          ].map((item) => (
            <Card key={item.titulo} className="px-5 py-4">
              <p className="font-display text-base font-bold text-forest">
                {item.titulo}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted">
                {item.texto}
              </p>
            </Card>
          ))}
        </div>
        <Button asChild variant="outline" className="mt-4">
          <Link href="/fontes">Ver fontes e qualidade</Link>
        </Button>
      </section>

      <section>
        <SecaoTitulo titulo="Quem faz" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Equipe e instituições</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm leading-relaxed text-muted">
              <p>
                Iniciativa de pesquisa e desenvolvimento no contexto do{" "}
                <strong className="text-forest">
                  NAPI Energia Zero-Carbono
                </strong>
                , com a Universidade Estadual de Maringá (UEM) e a Fundação
                Araucária.
              </p>
              <p>Idealização e liderança técnica: Anuar José Mincache.</p>
            </CardContent>
            <CardFooter>
              A vinculação institucional depende de definição e autorização
              apropriadas.
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Código aberto</CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-relaxed text-muted">
              O código, os testes e a documentação de cada etapa ficam no
              repositório do projeto. Esta interface é um protótipo: o portal em
              uso continua sendo o Streamlit.
            </CardContent>
            <CardFooter>
              <Button asChild size="sm" variant="outline">
                <a
                  href="https://github.com/anuarmincache/napi-geoai"
                  target="_blank"
                  rel="noreferrer"
                >
                  Abrir o repositório ↗
                </a>
              </Button>
            </CardFooter>
          </Card>
        </div>
      </section>
    </Pagina>
  );
}
