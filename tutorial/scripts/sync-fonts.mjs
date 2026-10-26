/**
 * Copies the Inter weights used by the tutorial from @fontsource/inter
 * (installed from npm) into public/fonts so Remotion's staticFile() can serve
 * them. This keeps the render fully offline — no Google Fonts network fetch.
 *
 * Re-run automatically via the `predev` / `prerender` npm hooks.
 */
import { copyFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const sourceDir = join(here, "..", "node_modules", "@fontsource", "inter", "files");
const targetDir = join(here, "..", "public", "fonts");

const weights = [400, 500, 600, 700, 800];

mkdirSync(targetDir, { recursive: true });

for (const weight of weights) {
  const file = `inter-latin-${weight}-normal.woff2`;
  const from = join(sourceDir, file);
  const to = join(targetDir, file);
  if (!existsSync(from)) {
    console.error(`Missing font source: ${from}. Run "npm install" first.`);
    process.exit(1);
  }
  copyFileSync(from, to);
}

console.log(`Inter ${weights.join("/")} synced to public/fonts (offline-ready).`);
