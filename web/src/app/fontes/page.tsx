"use client";

import { useState } from "react";
import {
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
import { Badge, ClasseBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Fontes } from "@/lib/dados";
import { useDados } from "@/lib/usar-dados";

export default function FontesPagina() {
  const fontes = useDados<Fontes>("fontes.json");
  const [aberta, setAberta] = useState<string | null>(null);
  const dados = fontes.dados;

  if (fontes.erro) {
    return (
      <Pagina>
        <CabecalhoPagina
          secao="Transparência"
          titulo="Fontes e qualidade dos dados"
          descricao="De onde vem cada dado e como ele foi conferido."
        />
        <Indisponivel detalhe="O catálogo de fontes não está disponível." />
      </Pagina>
    );
  }

  return (
    <Pagina largura="max-w-[1100px]">
      <CabecalhoPagina
        secao="Transparência"
        titulo="Fontes e qualidade dos dados"
        descricao="De onde vem cada dado, quando foi coletado e como foi conferido. Esta página não baixa nada: ela descreve o que já está no projeto."
      />

      <section>
        <SecaoTitulo
          titulo="Como classificamos cada número"
          descricao="A classe aparece ao lado de todo indicador no portal."
        />
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            {
              classe: "A" as const,
              titulo: "Dado oficial",
              texto: "Registrado diretamente na fonte, sem transformação.",
            },
            {
              classe: "B" as const,
              titulo: "Indicador calculado",
              texto:
                "Conta determinística sobre dados oficiais, com fórmula e unidade declaradas.",
            },
            {
              classe: "C" as const,
              titulo: "Simulação",
              texto: "Estimativa a partir de hipóteses que você informa.",
            },
          ].map((item) => (
            <Card key={item.classe} className="px-5 py-4">
              <ClasseBadge classe={item.classe} />
              <p className="mt-2 font-display text-base font-bold text-forest">
                {item.titulo}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-muted">
                {item.texto}
              </p>
            </Card>
          ))}
        </div>
        {dados && (
          <Card className="mt-4 px-5 py-4">
            <ul className="space-y-1.5 text-sm leading-relaxed text-muted">
              {dados.regras.slice(3).map((regra, i) => (
                <li key={`${i}-${regra.slice(0, 24)}`} className="flex gap-2">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-sun" />
                  {regra}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      <section>
        <SecaoTitulo
          titulo="Arquivos preparados"
          descricao="Cada painel do portal vem de um arquivo conferido, com data de preparo e impressão digital."
        />
        {dados ? (
          <div className="space-y-3">
            {dados.artefatos.map((a) => (
              <Card key={a.arquivo} className="px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-display text-base font-bold text-forest">
                      {a.rotulo}
                    </p>
                    <p className="mt-0.5 text-sm text-muted">
                      {a.organizacao} · {a.produto}
                    </p>
                  </div>
                  <Badge variant="oficial">Preparado em {a.preparado_em}</Badge>
                </div>
                {a.sha256 && (
                  <p className="mt-2 font-mono text-[11px] break-all text-muted">
                    SHA-256 {a.sha256}
                  </p>
                )}
                {a.licenca && (
                  <p className="mt-2 text-[12px] leading-relaxed text-muted">
                    {a.licenca}
                  </p>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <Carregando altura="h-64" />
        )}
      </section>

      <section>
        <SecaoTitulo
          titulo="Catálogo de fontes"
          descricao="Fontes oficiais usadas ou previstas, com licença, periodicidade e situação."
        />
        {dados ? (
          <div className="space-y-2">
            {dados.catalogo.map((f) => (
              <Card key={f.id} className="overflow-hidden">
                <button
                  onClick={() => setAberta(aberta === f.id ? null : f.id)}
                  className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left hover:bg-paper"
                >
                  <span className="min-w-0">
                    <span className="font-display text-sm font-bold text-forest">
                      {f.organizacao}
                    </span>
                    <span className="ml-2 text-sm text-ink">{f.produto}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <Badge
                      variant={f.status === "active" ? "oficial" : "default"}
                    >
                      {f.status === "active" ? "ativa" : f.status}
                    </Badge>
                    <span className="text-xs text-muted">
                      {aberta === f.id ? "▲" : "▼"}
                    </span>
                  </span>
                </button>
                {aberta === f.id && (
                  <div className="border-t border-line px-5 py-4">
                    <dl className="grid gap-3 sm:grid-cols-2">
                      <Item rotulo="Cobertura" valor={f.cobertura} />
                      <Item rotulo="Granularidade" valor={f.granularidade} />
                      <Item rotulo="Formatos" valor={f.formatos.join(", ")} />
                      <Item rotulo="Sistema de coordenadas" valor={f.crs} />
                      <Item rotulo="Atualização oficial" valor={f.cadencia} />
                      <Item
                        rotulo="Catalogada em"
                        valor={f.catalogado_em}
                      />
                    </dl>
                    <p className="mt-3 text-[12px] leading-relaxed text-muted">
                      <strong className="text-forest">Licença:</strong>{" "}
                      {f.licenca}
                    </p>
                    {f.notas && (
                      <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
                        {f.notas}
                      </p>
                    )}
                    <Button
                      asChild
                      size="sm"
                      variant="outline"
                      className="mt-3"
                    >
                      <a href={f.url} target="_blank" rel="noreferrer">
                        Abrir a fonte oficial ↗
                      </a>
                    </Button>
                  </div>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <Carregando altura="h-96" />
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>O que o portal não faz com os dados</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm leading-relaxed text-muted">
          <p>
            Não preenche lacuna. Quando um município não tem registro, a tela
            diz que não tem, em vez de mostrar zero.
          </p>
          <p>
            Não mistura unidades nem datas de referência sem avisar. Potência
            instalada não vira energia gerada, e cadastros diferentes não são
            somados.
          </p>
          <p>
            Não atualiza sozinho. Os números são retratos datados, e a data está
            ao lado de cada um.
          </p>
        </CardContent>
        <CardFooter>
          Os dados seguem as licenças das fontes: ANEEL (ODbL), IBGE (uso livre
          com citação) e MapBiomas (uso público com citação obrigatória).
        </CardFooter>
      </Card>
    </Pagina>
  );
}

function Item({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
        {rotulo}
      </dt>
      <dd className="mt-0.5 text-sm text-ink">{valor}</dd>
    </div>
  );
}
