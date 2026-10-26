/**
 * Offline voiceover fallback using meSpeak (pure-JS eSpeak, no network, no
 * system binaries). Produces public/narration/scene-XX.wav for every entry in
 * src/narration.js, choosing the first speaking rate whose output fits the
 * scene's budget, and trimming dead air at the edges.
 *
 * Natural-voice MP3s (scene-XX.mp3) take precedence in the manifest scanner,
 * so when the external TTS service is available its clips simply replace
 * these. Running this script clears any previous scene clips first, keeping
 * one consistent voice across the whole video.
 *
 * Usage: npm run narration:fallback
 */
import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { NARRATION, NARRATION_BUDGETS } from "../src/narration.js";

const require = createRequire(import.meta.url);
const meSpeak = require("mespeak");
meSpeak.loadConfig(require("mespeak/src/mespeak_config.json"));
meSpeak.loadVoice(require("mespeak/voices/en/en-us.json"));

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "..", "public", "narration");
mkdirSync(outDir, { recursive: true });

// Start from a clean set so mp3/wav generations never mix voices.
for (const f of readdirSync(outDir)) {
  if (/^scene-\d+\.(mp3|wav)$/.test(f)) rmSync(join(outDir, f));
}

const readWav = (buf) => {
  // Find the data chunk (files are simple PCM, but walk chunks to be safe).
  let off = 12;
  while (off + 8 <= buf.length) {
    const id = buf.toString("latin1", off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    if (id === "fmt ") {
      var channels = buf.readUInt16LE(off + 10);
      var sampleRate = buf.readUInt32LE(off + 12);
      var bitsPerSample = buf.readUInt16LE(off + 22);
    }
    if (id === "data") {
      var dataOff = off + 8;
      var dataSize = size;
      break;
    }
    off += 8 + size + (size % 2);
  }
  return { channels, sampleRate, bitsPerSample, dataOff, dataSize };
};

const writeWav = (samples, sampleRate) => {
  const dataSize = samples.length * 2;
  const buf = Buffer.alloc(44 + dataSize);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write("WAVE", 8);
  buf.write("fmt ", 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(dataSize, 40);
  samples.forEach((s, i) => buf.writeInt16LE(s, 44 + i * 2));
  return buf;
};

const MARGIN = 0.35; // seconds kept free inside the scene
const SPEEDS = [175, 185, 195, 210];
let failures = 0;

NARRATION.forEach((text, i) => {
  const scene = i + 1;
  const budget = NARRATION_BUDGETS[i];
  let chosen = null;

  for (const speed of SPEEDS) {
    const raw = Buffer.from(
      meSpeak.speak(text, {
        amplitude: 100,
        pitch: 45,
        speed,
        wordgap: 1,
        rawdata: "arraybuffer",
      })
    );
    const meta = readWav(raw);
    const samples = new Int16Array(
      raw.buffer,
      raw.byteOffset + meta.dataOff,
      meta.dataSize / 2
    );
    const duration = samples.length / meta.sampleRate;
    if (duration <= budget - MARGIN || speed === SPEEDS.at(-1)) {
      chosen = { samples: [...samples], sampleRate: meta.sampleRate, duration, speed };
      break;
    }
  }

  // Trim silence beyond a small floor, then pad 110 ms on each side.
  const floor = 320;
  let first = chosen.samples.findIndex((s) => Math.abs(s) > floor);
  let last = chosen.samples.length - 1;
  while (last > 0 && Math.abs(chosen.samples[last]) <= floor) last--;
  if (first < 0) first = 0;
  const pad = Math.round(chosen.sampleRate * 0.11);
  const trimmed = [
    ...new Array(pad).fill(0),
    ...chosen.samples.slice(first, last + 1),
    ...new Array(pad).fill(0),
  ];
  const finalDuration = trimmed.length / chosen.sampleRate;
  const fit = finalDuration <= budget ? "OK" : "OVER";
  if (fit === "OVER") failures++;

  const file = join(outDir, `scene-${String(scene).padStart(2, "0")}.wav`);
  writeFileSync(file, writeWav(trimmed, chosen.sampleRate));
  console.log(
    `scene ${String(scene).padStart(2, "0")}  speed ${chosen.speed}  ${finalDuration
      .toFixed(2)}s / ${budget}s  ${fit}  ${text.slice(0, 48)}…`
  );
});

if (failures) {
  console.warn(`\n${failures} clip(s) exceed their scene budget — shorten the line(s) in src/narration.js.`);
  process.exitCode = 1;
} else {
  console.log("\nAll fallback narration clips fit their scenes. Run `npm run narration:scan`.");
}
