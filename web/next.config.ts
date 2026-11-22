import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Protótipo: exportação estática, para publicar como site de arquivos.
  // Os dados vêm de public/dados/, gerados por scripts/build_web_data.py.
  output: "export",
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
};

export default nextConfig;
