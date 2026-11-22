"use client";

import { useEffect, useState } from "react";
import { carregar } from "@/lib/dados";

export interface EstadoDados<T> {
  dados: T | null;
  erro: string | null;
  carregando: boolean;
}

/** Carrega um arquivo de public/dados. Falha vira mensagem, nunca número. */
export function useDados<T>(arquivo: string): EstadoDados<T> {
  const [estado, setEstado] = useState<EstadoDados<T>>({
    dados: null,
    erro: null,
    carregando: true,
  });

  useEffect(() => {
    let ativo = true;
    carregar<T>(arquivo)
      .then((dados) => {
        if (ativo) setEstado({ dados, erro: null, carregando: false });
      })
      .catch((e: Error) => {
        if (ativo) setEstado({ dados: null, erro: e.message, carregando: false });
      });
    return () => {
      ativo = false;
    };
  }, [arquivo]);

  return estado;
}
