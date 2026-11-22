import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NAPI GeoAI — inteligência territorial e energética do Paraná",
  description:
    "Território, população, energia, agropecuária e cobertura da terra dos 399 municípios do Paraná, a partir de dados oficiais em retratos datados.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full font-sans">{children}</body>
    </html>
  );
}
