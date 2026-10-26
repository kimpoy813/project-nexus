/**
 * Scans public/narration for generated voiceover clips and writes
 * src/narration-manifest.json. Root.jsx reads the manifest and only mounts an
 * <Audio> track for clips that actually exist, so the project always renders —
 * a not-yet-generated line simply stays silent while the music bed continues.
 *
 * Re-run after adding/replacing any clip; `prerender` does this automatically.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, "..", "public", "narration");
const out = join(here, "..", "src", "narration-manifest.json");

mkdirSync(dir, { recursive: true });
const files = readdirSync(dir)
  .filter((f) => /^scene-\d+\.mp3$/.test(f))
  .sort();

const manifest = {
  count: files.length,
  // Sorted zero-padded scene numbers with clips, e.g. [1, 3, 5].
  scenes: files.map((f) => Number(f.match(/\d+/)[0])),
};
writeFileSync(out, JSON.stringify(manifest, null, 2) + "\n");
console.log(
  `narration manifest: ${manifest.count} clip(s) present (scenes ${
    manifest.scenes.length ? manifest.scenes.join(", ") : "none yet"
  })`
);
