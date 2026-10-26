/**
 * Scans public/narration for voiceover clips and writes
 * src/narration-manifest.json. Root.jsx mounts only clips listed here, so the
 * project always renders — a not-yet-generated line stays a quiet music-only
 * passage instead of breaking the build.
 *
 * Two producers, one folder:
 *   - natural TTS clips:  scene-XX.mp3  (preferred when present)
 *   - offline meSpeak:    scene-XX.wav  (scripts/make-narration-fallback.mjs)
 * MP3 wins if both exist for a scene. Re-run after adding/replacing a clip;
 * the `prerender` hook does this automatically.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, "..", "public", "narration");
const out = join(here, "..", "src", "narration-manifest.json");

mkdirSync(dir, { recursive: true });
const byScene = new Map();
for (const f of readdirSync(dir)) {
  const m = f.match(/^scene-(\d+)\.(mp3|wav)$/);
  if (!m) continue;
  const scene = Number(m[1]);
  const ext = m[2];
  // Prefer mp3 (natural voice) over wav (synthetic fallback).
  if (!byScene.has(scene) || ext === "mp3") byScene.set(scene, ext);
}

const scenes = [...byScene.keys()].sort((a, b) => a - b);
const manifest = {
  count: scenes.length,
  // Public-folder path per scene, e.g. { "1": "narration/scene-01.mp3" }.
  files: Object.fromEntries(
    scenes.map((s) => [
      s,
      `narration/scene-${String(s).padStart(2, "0")}.${byScene.get(s)}`,
    ])
  ),
  // Backwards-compatible plain list of scene numbers.
  scenes,
};
writeFileSync(out, JSON.stringify(manifest, null, 2) + "\n");
console.log(
  `narration manifest: ${manifest.count} clip(s) present (scenes ${
    scenes.length ? scenes.join(", ") : "none yet"
  })`
);
