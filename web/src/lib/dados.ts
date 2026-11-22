/** Tipos e formatadores dos dados estáticos gerados por scripts/build_web_data.py. */

export type Classe = "A" | "B" | "C";

export interface Kpi {
  id: string;
  rotulo: string;
  valor: number;
  unidade: string;
  detalhe: string;
  classe: Classe;
  fonte: string;
  data: string;
}

export interface Camada {
  id: string;
  rotulo: string;
  unidade: string;
  descricao: string;
  cor: string;
  disponivel: boolean;
  classe: Classe;
  fonte: string;
}

export interface Resumo {
  gerado_em: string;
  kpis: Kpi[];
  camadas: Camada[];
  avisos: string[];
  ndvi: {
    municipios: number | null;
    com_passagem: number | null;
    cenas: number | null;
    publicados: number;
    medidos: number;
  };
  fontes: { nome: string; detalhe: string }[];
}

export interface PropsMunicipio {
  cd: string;
  nome: string;
  area_km2: number | null;
  habitantes: number | null;
  densidade: number | null;
  siga_mw: number | null;
  siga_usinas: number | null;
  mmgd_mw: number | null;
  mmgd_n: number | null;
  mmgd_kw_hab: number | null;
  lc_formacao_florestal?: number | null;
  lc_agricultura?: number | null;
  lc_area_urbanizada?: number | null;
  [chave: string]: string | number | null | undefined;
}

export interface Series {
  mmgd_classes?: { nome: string; valor: number }[];
  mmgd_top?: { nome: string; mw: number; n: number }[];
  siga_tecnologia?: { nome: string; mw: number }[];
  cobertura?: {
    anos: number[];
    series: { chave: string; nome: string; cor: string; ha: number[] }[];
  };
  cobertura_2025?: { nome: string; cor: string; ha: number; pct: number | null }[];
  lavouras?: { nome: string; area_ha: number; producao_t: number }[];
  pecuaria?: { nome: string; valor: number; unidade: string }[];
}

export interface Ficha {
  cd: string;
  nome: string;
  habitantes: number | null;
  area_km2: number | null;
  densidade: number | null;
  siga?: { usinas: number; mw: number | null };
  mmgd?: { n: number; mw: number | null };
  cobertura?: { nome: string; cor: string; pct: number | null }[];
  pecuaria?: { nome: string; valor: number | null }[];
}

const NOMES_TECNOLOGIA: Record<string, string> = {
  UHE: "Hidrelétrica (UHE)",
  PCH: "Pequena central hidrelétrica",
  CGH: "Central geradora hidrelétrica",
  UTE: "Termelétrica",
  UFV: "Solar fotovoltaica",
  EOL: "Eólica",
};

export function nomeTecnologia(sigla: string) {
  return NOMES_TECNOLOGIA[sigla] ?? sigla;
}

export function num(valor: number | null | undefined, casas = 0) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "n/d";
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

/** Número grande em forma curta: 6.902 MW vira "6,9 GW" quando pedido. */
export function compacto(valor: number | null | undefined, casas = 1) {
  if (valor === null || valor === undefined) return "n/d";
  if (Math.abs(valor) >= 1_000_000) return `${num(valor / 1_000_000, casas)} mi`;
  if (Math.abs(valor) >= 1_000) return num(valor, 0);
  return num(valor, casas);
}

export async function carregar<T>(arquivo: string): Promise<T> {
  const resposta = await fetch(`/dados/${arquivo}`, { cache: "force-cache" });
  if (!resposta.ok) {
    throw new Error(`Dados indisponíveis: ${arquivo}`);
  }
  return (await resposta.json()) as T;
}
