"use client";

import { useMemo, useState } from "react";
import {
  Avisos,
  CabecalhoPagina,
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
import { num } from "@/lib/dados";
import {
  Equipamento,
  consumoMensalKwh,
  custoMensalBrl,
  dimensionamentoFotovoltaico,
  totalMensalKwh,
} from "@/lib/calculos";

const INICIAIS: Equipamento[] = [
  {
    id: "1",
    nome: "Motor de irrigação",
    potencia_w: 1500,
    horas_por_dia: 4,
    dias_por_mes: 22,
    quantidade: 1,
  },
  {
    id: "2",
    nome: "Iluminação",
    potencia_w: 40,
    horas_por_dia: 8,
    dias_por_mes: 30,
    quantidade: 10,
  },
];

export default function Calculadoras() {
  const [itens, setItens] = useState<Equipamento[]>(INICIAIS);
  const [tarifa, setTarifa] = useState("");
  const [hsp, setHsp] = useState("");
  const [pr, setPr] = useState("0.75");
  const [moduloWp, setModuloWp] = useState("550");
  const [consumoPv, setConsumoPv] = useState("");

  const total = useMemo(() => totalMensalKwh(itens), [itens]);
  const custo = useMemo(() => {
    const t = Number(tarifa.replace(",", "."));
    if (!tarifa.trim() || !Number.isFinite(t)) return null;
    return custoMensalBrl(total, t);
  }, [total, tarifa]);

  const dimensionamento = useMemo(() => {
    const consumo = Number(consumoPv.replace(",", ".")) || total;
    const irradiacao = Number(hsp.replace(",", "."));
    const desempenho = Number(pr.replace(",", "."));
    const modulo = Number(moduloWp.replace(",", "."));
    if (!hsp.trim() || !Number.isFinite(irradiacao)) return null;
    return dimensionamentoFotovoltaico(
      consumo,
      irradiacao,
      desempenho,
      Number.isFinite(modulo) && modulo > 0 ? modulo : null,
    );
  }, [consumoPv, total, hsp, pr, moduloWp]);

  function atualizar(id: string, campo: keyof Equipamento, valor: string) {
    setItens((atual) =>
      atual.map((item) =>
        item.id === id
          ? {
              ...item,
              [campo]:
                campo === "nome" ? valor : Number(valor.replace(",", ".")),
            }
          : item,
      ),
    );
  }

  return (
    <Pagina largura="max-w-[1100px]">
      <CabecalhoPagina
        secao="Energia"
        titulo="Calculadoras"
        descricao="Quanto os equipamentos consomem por mês e que potência solar compensaria esse consumo. Todos os valores de entrada são seus; o resultado é uma simulação, não um projeto."
      >
        <div className="flex flex-wrap gap-2">
          <Badge variant="escuro">Simulação, classe C</Badge>
          <Badge variant="escuro">Sem valor padrão de tarifa ou irradiação</Badge>
        </div>
      </CabecalhoPagina>

      <section>
        <SecaoTitulo
          titulo="Consumo de equipamentos"
          descricao="E = potência × horas por dia × dias por mês × quantidade ÷ 1000."
        />
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-paper/60 text-left">
                  {[
                    "Equipamento",
                    "Potência (W)",
                    "Horas/dia",
                    "Dias/mês",
                    "Quantidade",
                    "kWh por mês",
                    "",
                  ].map((c) => (
                    <th
                      key={c}
                      className="px-4 py-2.5 font-display text-[11px] font-bold tracking-wider text-muted uppercase"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {itens.map((item) => {
                  const kwh = consumoMensalKwh(item);
                  return (
                    <tr key={item.id} className="border-b border-line/60 last:border-0">
                      <td className="px-4 py-2">
                        <input
                          value={item.nome}
                          onChange={(e) =>
                            atualizar(item.id, "nome", e.target.value)
                          }
                          className="w-40 rounded-lg border border-line px-2 py-1.5 text-sm outline-none focus:border-moss"
                        />
                      </td>
                      {(
                        [
                          "potencia_w",
                          "horas_por_dia",
                          "dias_por_mes",
                          "quantidade",
                        ] as const
                      ).map((campo) => (
                        <td key={campo} className="px-4 py-2">
                          <input
                            type="number"
                            value={item[campo]}
                            onChange={(e) =>
                              atualizar(item.id, campo, e.target.value)
                            }
                            className="w-24 rounded-lg border border-line px-2 py-1.5 text-right text-sm outline-none focus:border-moss"
                          />
                        </td>
                      ))}
                      <td className="px-4 py-2 text-right font-display font-bold text-forest tabular-nums">
                        {kwh === null ? (
                          <span className="text-xs font-normal text-muted">
                            valor inválido
                          </span>
                        ) : (
                          num(kwh, 1)
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() =>
                            setItens((a) => a.filter((i) => i.id !== item.id))
                          }
                          className="text-xs font-semibold text-muted hover:text-[#8a2b2b]"
                        >
                          remover
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3">
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                setItens((a) => [
                  ...a,
                  {
                    id: String(Date.now()),
                    nome: "Novo equipamento",
                    potencia_w: 100,
                    horas_por_dia: 1,
                    dias_por_mes: 30,
                    quantidade: 1,
                  },
                ])
              }
            >
              + Adicionar equipamento
            </Button>
            <p className="font-display text-lg font-bold text-forest">
              Total: {num(total, 1)}{" "}
              <span className="text-sm font-semibold text-muted">
                kWh por mês
              </span>
            </p>
          </div>
        </Card>

        <Card className="mt-4 px-5 py-5">
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex-1">
              <span className="text-[11px] font-bold tracking-wider text-muted uppercase">
                Tarifa (R$/kWh)
              </span>
              <input
                value={tarifa}
                onChange={(e) => setTarifa(e.target.value)}
                placeholder="informe a sua tarifa"
                className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-moss"
              />
            </label>
            <div className="flex-1">
              <p className="text-[11px] font-bold tracking-wider text-muted uppercase">
                Custo estimado por mês
              </p>
              <p className="mt-1 font-display text-2xl font-bold text-forest">
                {custo === null ? (
                  <span className="text-sm font-semibold text-muted">
                    informe a tarifa para ver o custo
                  </span>
                ) : (
                  `R$ ${num(custo, 2)}`
                )}
              </p>
            </div>
          </div>
          <p className="mt-3 text-[12px] leading-relaxed text-muted">
            A tarifa não tem valor padrão: ela varia por distribuidora, bandeira,
            tributos e classe de consumo. O cálculo multiplica energia por
            tarifa e não inclui taxa mínima, bandeiras nem tributos.
          </p>
        </Card>
      </section>

      <section>
        <SecaoTitulo
          titulo="Dimensionamento fotovoltaico preliminar"
          descricao="P = consumo ÷ (irradiação × dias × taxa de desempenho)."
        />
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <Card className="px-5 py-5">
            <div className="space-y-3">
              <Campo
                rotulo="Consumo mensal (kWh)"
                valor={consumoPv}
                aoMudar={setConsumoPv}
                dica={`em branco usa o total acima: ${num(total, 1)} kWh`}
              />
              <Campo
                rotulo="Irradiação, HSP (kWh/m²/dia)"
                valor={hsp}
                aoMudar={setHsp}
                dica="sem valor padrão: use dado de uma fonte de irradiação para o local"
              />
              <Campo
                rotulo="Taxa de desempenho (0 a 1)"
                valor={pr}
                aoMudar={setPr}
                dica="relação entre energia gerada e energia teórica"
              />
              <Campo
                rotulo="Potência do módulo (Wp)"
                valor={moduloWp}
                aoMudar={setModuloWp}
                dica="opcional, para estimar o número de módulos"
              />
            </div>
          </Card>

          <Card>
            <CardHeader className="flex items-start justify-between gap-3">
              <CardTitle>Resultado</CardTitle>
              <ClasseBadge classe="C" />
            </CardHeader>
            <CardContent>
              {dimensionamento === null ? (
                <p className="text-sm text-muted">
                  Informe a irradiação (HSP) do local para ver o resultado.
                  Nenhum valor é assumido no lugar dele.
                </p>
              ) : "erro" in dimensionamento ? (
                <p className="rounded-xl bg-[#fbecec] px-4 py-3 text-sm text-[#8a2b2b]">
                  {dimensionamento.erro}
                </p>
              ) : (
                <dl className="space-y-3">
                  <Resultado
                    rotulo="Potência necessária"
                    valor={`${num(dimensionamento.potencia_kwp, 2)} kWp`}
                  />
                  {dimensionamento.modulos !== null && (
                    <>
                      <Resultado
                        rotulo="Módulos"
                        valor={`${num(dimensionamento.modulos)} unidades`}
                      />
                      <Resultado
                        rotulo="Potência instalada"
                        valor={`${num(dimensionamento.instalada_kwp, 2)} kWp`}
                      />
                      <Resultado
                        rotulo="Geração esperada"
                        valor={`${num(dimensionamento.geracao_esperada_kwh, 0)} kWh por mês`}
                      />
                    </>
                  )}
                </dl>
              )}
            </CardContent>
            <CardFooter>
              Estimativa preliminar. Não considera custo de disponibilidade,
              sombreamento, orientação, degradação, limites de conexão nem
              aspectos econômicos.
            </CardFooter>
          </Card>
        </div>
      </section>

      <Avisos
        itens={[
          "Resultado de simulação (classe C), com as hipóteses que você informou.",
          "Não substitui projeto elétrico, estudo de viabilidade, parecer de acesso nem orçamento.",
          "A irradiação e a tarifa variam por local e por distribuidora: use valores de fonte confiável para o seu caso.",
          "As fórmulas são as mesmas do motor do projeto, em geoai/tools/energy_calc.py.",
        ]}
      />
    </Pagina>
  );
}

function Campo({
  rotulo,
  valor,
  aoMudar,
  dica,
}: {
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  dica: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-bold tracking-wider text-muted uppercase">
        {rotulo}
      </span>
      <input
        value={valor}
        onChange={(e) => aoMudar(e.target.value)}
        className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-moss"
      />
      <span className="mt-1 block text-[11px] leading-snug text-muted">
        {dica}
      </span>
    </label>
  );
}

function Resultado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-xl bg-paper px-4 py-3">
      <dt className="text-[10px] font-bold tracking-wider text-muted uppercase">
        {rotulo}
      </dt>
      <dd className="mt-0.5 font-display text-xl font-bold text-forest">
        {valor}
      </dd>
    </div>
  );
}
