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
  /** "faixa" quando o indicador é uma razão e o zero não é referência. */
  escala?: "zero" | "faixa";
}

export interface Resumo {
  gerado_em: string;
  kpis: Kpi[];
  camadas: Camada[];
  avisos: string[];
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
  pecuaria?: { nome: string; valor: number | null; unidade: string }[];
  parecidos?: {
    metodo: string;
    variaveis: string[];
    aviso: string | null;
    lista: {
      cd: string;
      nome: string;
      distancia: number;
      parecido_em: string[];
      diferente_em: string[];
    }[];
  };
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
  const limpa = (sigla ?? "").trim();
  if (!limpa || limpa === "(vazio)")
    return "Tecnologia não informada no cadastro";
  return NOMES_TECNOLOGIA[limpa] ?? limpa;
}

/** Converte 2026-11-12 em 12/11/2026. Deixa passar o que não for data ISO. */
export function dataBr(valor: string | null | undefined) {
  if (!valor) return "n/d";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(valor.trim());
  return m ? `${m[3]}/${m[2]}/${m[1]}` : valor;
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

/* ------------------------------------------------------------------ */
/* Tipos das demais abas                                               */
/* ------------------------------------------------------------------ */

export interface MunicipioMmgd {
  cd: string;
  nome: string;
  n: number;
  mw: number;
  uc_credito: number | null;
  por_tipo: Record<string, number>;
  por_classe: Record<string, number>;
  por_porte: Record<string, number>;
}

export interface MunicipioSiga {
  cd: string;
  nome: string;
  status: string;
  n: number;
  mw_fiscalizada: number;
  mw_outorgada: number;
  por_tipo: Record<string, number>;
}

export interface Energia {
  mmgd: {
    periodo: string;
    unidade: string;
    totais: {
      instalacoes: number;
      mw: number;
      uc_credito: number;
      sem_potencia: number;
      por_tipo: Record<string, number>;
      por_classe: Record<string, number>;
    };
    municipios: MunicipioMmgd[];
    avisos: string[];
    nota_temporal: string | null;
  } | null;
  siga: {
    fase: string;
    coleta: string;
    unidade: string;
    totais: {
      usinas: number;
      mw: number;
      nao_associados: number;
      mw_nao_associados: number;
      sem_potencia: number;
      por_tipo: Record<string, number>;
      usinas_por_tipo: Record<string, number>;
    };
    municipios: MunicipioSiga[];
    limitacao: string | null;
    nota_metrica: string | null;
  } | null;
}

export interface ResumoEstadual {
  soma_publicada: number | null;
  contagem_por_status: Record<string, number>;
}

export interface Cultura {
  id: string;
  nome: string;
  unidade_area: string;
  unidade_producao: string;
  unidade_rendimento: string;
  estado_colhida: ResumoEstadual;
  estado_area: ResumoEstadual;
  estado_producao: ResumoEstadual;
  municipios: Record<
    string,
    {
      area: number | null;
      colhida: number | null;
      producao: number | null;
      rendimento: number | null;
      status: string;
    }
  >;
}

export interface Rebanho {
  chave: string;
  nome: string;
  unidade: string;
  fonte: string;
  estado: ResumoEstadual;
  municipios: Record<string, { v: number | null; s: string }>;
}

export interface Agricultura {
  ano_pam: string | number;
  ano_ppm: string | number;
  culturas: Cultura[];
  rebanhos: Rebanho[];
  avisos: string[];
  fontes: string[];
}

export interface Cobertura {
  colecao: number;
  anos: number[];
  ultimo_ano: number;
  grupos: { chave: string; nome: string; cor: string }[];
  regra_anos: string;
  estado: Record<string, Record<string, number>>;
  mudanca_estado: {
    nome: string;
    ha_inicio: number;
    ha_fim: number;
    delta_ha: number;
    delta_pp: number | null;
  }[];
  municipios: Record<
    string,
    {
      pct: Record<string, Record<string, number>>;
      ha_mapeada: number;
      area_ibge_km2: number;
      delta_ibge: number;
    }
  >;
  avisos: string[];
  fontes: string[];
  qualidade: {
    median_abs: number;
    max_abs: number;
    municipalities_above_1_percent: number;
  } | null;
}

export interface Fontes {
  catalogo: {
    id: string;
    organizacao: string;
    produto: string;
    url: string;
    formatos: string[];
    licenca: string;
    cadencia: string;
    cobertura: string;
    granularidade: string;
    crs: string;
    catalogado_em: string;
    status: string;
    autenticacao: boolean;
    notas: string;
  }[];
  artefatos: {
    rotulo: string;
    arquivo: string;
    preparado_em: string;
    organizacao: string | null;
    produto: string | null;
    sha256: string | null;
    licenca: string | null;
  }[];
  regras: string[];
}
