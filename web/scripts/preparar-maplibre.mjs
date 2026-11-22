/**
 * Copia o worker do MapLibre para public/.
 *
 * O bundler não resolve o `new Worker(new URL(...))` interno da biblioteca, e
 * sem isso o mapa registra "Worker failed to load" no console. Servindo o
 * arquivo em /maplibre-gl-worker.mjs e apontando setWorkerUrl para ele, a
 * biblioteca carrega o worker normalmente.
 */
import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";

const require = createRequire(import.meta.url);
const dist = dirname(require.resolve("maplibre-gl/dist/maplibre-gl.mjs"));
const destino = resolve(import.meta.dirname, "..", "public");

await mkdir(destino, { recursive: true });
await copyFile(
  resolve(dist, "maplibre-gl-worker.mjs"),
  resolve(destino, "maplibre-gl-worker.mjs"),
);
console.log("worker do MapLibre copiado para public/maplibre-gl-worker.mjs");
