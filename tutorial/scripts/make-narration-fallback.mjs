/**
 * Offline voiceover fallback using meSpeak (pure-JS eSpeak, no network, no
 * system binaries). Produces public/narration/sXX-YY.wav for every timed
 * segment in src/narration.js, choosing a speaking rate that fits the
 * segment's window inside its scene, and trimming dead air at the edges.
 *
 * Natural-voice MP3s (same stems, .mp3) take precedence in the manifest
 * scanner, so external TTS clips replace these without any code change.
 * Running this script clears prior clips first, keeping one voice per video.
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

// Clear every previously generated clip (old per-scene names included).
for (const f of readdirSync(outDir)) {
  if (/^s?\d|^scene-/.test(f) && /\.(mp3|wav)$/.test(f)) rmSync(join(outDir, f));
}

const readWav = (buf) => {
  let off = 12;
  while (off + 8 <= buf.length) {
    const id = buf.toString("latin1", off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    if (id === "fmt ") {
      var sampleRate = buf.readUInt32LE(off + 12);
    }
    if (id === "data") return { sampleRate, dataOff: off + 8, dataSize: size };
    off += 8 + size + (size % 2);
  }
  throw new Error("bad WAV");
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

const SPEEDS = [175, 185, 195, 210];
const TAIL_MARGIN = 12; // frames kept free after the line inside its scene
let failures = 0;
let made = 0;

NARRATION.forEach((entry, sceneIdx) => {
  const scene = sceneIdx + 1;
  const sceneFrames = Math.round(NARRATION_BUDGETS[sceneIdx] * 30);
  entry.segments.forEach((seg, segIdx) => {
    const windowFrames = sceneFrames - seg.at - TAIL_MARGIN;
    const windowSeconds = windowFrames / 30;
    let chosen = null;

    for (const speed of SPEEDS) {
      const raw = Buffer.from(
        meSpeak.speak(seg.text, {
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
      if (duration <= windowSeconds || speed === SPEEDS.at(-1)) {
        chosen = { samples: [...samples], sampleRate: meta.sampleRate, duration, speed };
        break;
      }
    }

    // Trim silence, then pad 100 ms each side.
    const floor = 320;
    let first = chosen.samples.findIndex((s) => Math.abs(s) > floor);
    let last = chosen.samples.length - 1;
    while (last > 0 && Math.abs(chosen.samples[last]) <= floor) last--;
    if (first < 0) first = 0;
    const pad = Math.round(chosen.sampleRate * 0.1);
    const trimmed = [
      ...new Array(pad).fill(0),
      ...chosen.samples.slice(first, last + 1),
      ...new Array(pad).fill(0),
    ];
    const finalSeconds = trimmed.length / chosen.sampleRate;
    const fit = finalSeconds <= windowSeconds ? "OK" : "OVER";
    if (fit === "OVER") failures++;

    const stem = `s${String(scene).padStart(2, "0")}-${String(segIdx + 1).padStart(2, "0")}`;
    writeFileSync(join(outDir, `${stem}.wav`), writeWav(trimmed, chosen.sampleRate));
    made++;
    console.log(
      `${stem}  spd ${chosen.speed}  ${finalSeconds.toFixed(2)}s / window ${windowSeconds.toFixed(2)}s  ${fit}  ${seg.text.slice(0, 42)}…`
    );
  });
});

if (failures) {
  console.warn(`\n${failures} segment(s) exceed their window — shorten them in src/narration.js.`);
  process.exitCode = 1;
} else {
  console.log(`\n${made} fallback clips fit their windows. Run \`npm run narration:scan\`.`);
}
