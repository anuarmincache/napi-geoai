/**
 * Cálculos das calculadoras. Mesmas fórmulas de geoai/tools/energy_calc.py.
 *
 * Resultado é simulação (classe C): não considera custo de disponibilidade,
 * sombreamento, orientação, degradação, limites de conexão nem economia.
 */

export const DIAS_POR_MES_PADRAO = 30;

export interface Equipamento {
  id: string;
  nome: string;
  potencia_w: number;
  horas_por_dia: number;
  dias_por_mes: number;
  quantidade: number;
}

/** E = P × h × d × n ÷ 1000. Entrada inválida devolve null, nunca zero. */
export function consumoMensalKwh(item: Equipamento): number | null {
  const { potencia_w, horas_por_dia, dias_por_mes, quantidade } = item;
  const numeros = [potencia_w, horas_por_dia, dias_por_mes, quantidade];
  if (numeros.some((v) => !Number.isFinite(v))) return null;
  if (potencia_w < 0 || quantidade < 0) return null;
  if (horas_por_dia < 0 || horas_por_dia > 24) return null;
  if (dias_por_mes < 0 || dias_por_mes > 31) return null;
  return (potencia_w * horas_por_dia * dias_por_mes * quantidade) / 1000;
}

export function totalMensalKwh(itens: Equipamento[]): number {
  return itens.reduce((soma, item) => soma + (consumoMensalKwh(item) ?? 0), 0);
}

export function custoMensalBrl(
  energiaKwh: number,
  tarifaBrlPorKwh: number,
): number | null {
  if (!Number.isFinite(energiaKwh) || !Number.isFinite(tarifaBrlPorKwh)) {
    return null;
  }
  if (energiaKwh < 0 || tarifaBrlPorKwh < 0) return null;
  return energiaKwh * tarifaBrlPorKwh;
}

export interface Dimensionamento {
  potencia_kwp: number;
  modulos: number | null;
  instalada_kwp: number | null;
  geracao_esperada_kwh: number | null;
}

/** P = E ÷ (HSP × dias × PR). */
export function dimensionamentoFotovoltaico(
  consumoMensalKwh: number,
  hspKwhM2Dia: number,
  taxaDesempenho: number,
  moduloWp: number | null,
  dias = DIAS_POR_MES_PADRAO,
): Dimensionamento | { erro: string } {
  if (!Number.isFinite(consumoMensalKwh) || consumoMensalKwh < 0) {
    return { erro: "O consumo mensal não pode ser negativo." };
  }
  if (!Number.isFinite(hspKwhM2Dia) || hspKwhM2Dia <= 0) {
    return { erro: "A irradiação (HSP) precisa ser maior que zero." };
  }
  if (!Number.isFinite(taxaDesempenho) || taxaDesempenho <= 0 || taxaDesempenho > 1) {
    return { erro: "A taxa de desempenho precisa ficar entre 0 e 1." };
  }
  if (!Number.isFinite(dias) || dias <= 0) {
    return { erro: "O número de dias precisa ser maior que zero." };
  }

  const potencia_kwp = consumoMensalKwh / (hspKwhM2Dia * dias * taxaDesempenho);
  if (moduloWp === null || !Number.isFinite(moduloWp) || moduloWp <= 0) {
    return {
      potencia_kwp,
      modulos: null,
      instalada_kwp: null,
      geracao_esperada_kwh: null,
    };
  }
  const modulos = Math.ceil(
    Number(((potencia_kwp * 1000) / moduloWp).toFixed(9)),
  );
  const instalada_kwp = (modulos * moduloWp) / 1000;
  return {
    potencia_kwp,
    modulos,
    instalada_kwp,
    geracao_esperada_kwh: instalada_kwp * hspKwhM2Dia * dias * taxaDesempenho,
  };
}
