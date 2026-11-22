/**
 * Gera os dados do front antes de `npm run dev` e `npm run build`.
 *
 * Os arquivos de public/dados/ ficam fora do Git para não duplicar o artefato
 * versionado em data/derived/ nem deixá-lo desatualizar. Sem esta etapa, quem
 * faz `git pull` fica com dados antigos e as abas novas aparecem vazias.
 *
 * Se o Python não estiver disponível, o script avisa e deixa seguir: a
 * interface continua abrindo com o que já existir e diz o que falta.
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const raiz = resolve(import.meta.dirname, "..", "..");
const gerador = resolve(raiz, "scripts", "build_web_data.py");

if (!existsSync(gerador)) {
  console.warn(`aviso: ${gerador} não encontrado; dados não foram gerados.`);
  process.exit(0);
}

const candidatos = [
  ["python3", [gerador]],
  ["python", [gerador]],
  ["py", ["-3", gerador]],
];

for (const [comando, argumentos] of candidatos) {
  const resultado = spawnSync(comando, argumentos, {
    cwd: raiz,
    stdio: "inherit",
  });
  if (resultado.error?.code === "ENOENT") continue;
  if (resultado.status === 0) process.exit(0);
  console.warn(
    `aviso: ${comando} terminou com código ${resultado.status}. ` +
      "Os dados podem estar desatualizados.",
  );
  process.exit(0);
}

console.warn(
  "aviso: Python não encontrado no PATH, então os dados não foram " +
    "regerados.\n  Rode na raiz do repositório:\n" +
    "    python scripts/build_web_data.py",
);
