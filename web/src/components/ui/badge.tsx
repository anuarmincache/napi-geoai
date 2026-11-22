import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        default: "border-line bg-paper text-forest",
        oficial: "border-leaf/40 bg-leaf/10 text-[#2b5e1c]",
        derivado: "border-sun/50 bg-sun/15 text-[#6b5000]",
        simulado: "border-[#9ab3c7] bg-[#e7f0f6] text-[#1d4d6b]",
        ausente: "border-[#d8b4b4] bg-[#fbeceC] text-[#8a2b2b]",
        escuro: "border-white/20 bg-white/10 text-white",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

/** Classe científica do número: A oficial, B derivado, C simulado. */
export function ClasseBadge({ classe }: { classe: "A" | "B" | "C" }) {
  const mapa = {
    A: { variant: "oficial" as const, texto: "Dado oficial" },
    B: { variant: "derivado" as const, texto: "Indicador calculado" },
    C: { variant: "simulado" as const, texto: "Simulação" },
  };
  const item = mapa[classe];
  return <Badge variant={item.variant}>{item.texto}</Badge>;
}
