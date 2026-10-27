/**
 * Generates public/music/nexus-bed.wav — a 135-second ambient music bed for
 * the tutorial, synthesized from scratch with no external assets so the
 * project stays fully offline.
 *
 * Arrangement (calm, institutional, in A minor):
 *   - four-chord loop Am – F – C – G, one chord every 8 seconds
 *   - warm detuned-sine pad through a one-pole low-pass, slow attacks
 *   - soft triangle sub-bass on each chord root
 *   - sparse sine "music-box" arpeggio on chord tones, deterministic random
 *   - a whisper of filtered noise as air
 *   - tanh soft saturation, 2.5s fade-in, 4s fade-out
 *
 * Output: 44.1 kHz, 16-bit stereo PCM WAV. Re-run with `npm run music`.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const outPath = join(here, "..", "public", "music", "nexus-bed.wav");

const SR = 44100;
const DURATION = 146; // covers the transition-overlapped ~144s composition
const N = SR * DURATION;
const TWO_PI = 2 * Math.PI;

// Equal-temperament frequency from a note name (e.g. A4 = 440 Hz).
const SEMIS = { C: -9, "C#": -8, D: -7, "D#": -6, E: -5, F: -4, "F#": -3, G: -2, "G#": -1, A: 0, "A#": 1, B: 2 };
const note = (name) => {
  const m = name.match(/^([A-G]#?)(\d)$/);
  const semis = SEMIS[m[1]] + (Number(m[2]) - 4) * 12;
  return 440 * Math.pow(2, semis / 12);
};

// Chord loop: pad voices, bass root, and arpeggio pool.
const CHORDS = [
  { pad: ["A3", "C4", "E4"], bass: "A2", arp: ["A4", "C5", "E5", "A5"] },
  { pad: ["F3", "A3", "C4"], bass: "F2", arp: ["F4", "A4", "C5", "F5"] },
  { pad: ["C4", "E4", "G4"], bass: "C3", arp: ["C5", "E5", "G5", "C6"] },
  { pad: ["G3", "B3", "D4"], bass: "G2", arp: ["G4", "B4", "D5", "G5"] },
];
const CHORD_SECONDS = 8;

// Deterministic PRNG so the bed is identical on every run.
const mulberry32 = (seed) => () => {
  seed |= 0;
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const rand = mulberry32(20240517);

// One-pole low-pass shared by the pad voices.
const makeLP = (cutoff) => {
  const rc = 1 / (TWO_PI * cutoff);
  const alpha = 1 / SR / (rc + 1 / SR);
  let y = 0;
  return (x) => {
    y += alpha * (x - y);
    return y;
  };
};

const sine = (freq, t, phase = 0) => Math.sin(TWO_PI * freq * t + phase);
const triangle = (freq, t) => {
  const ph = freq * t - Math.floor(freq * t);
  return 4 * Math.abs(ph - 0.5) - 1;
};

// ADSR-ish envelope in seconds.
const env = (t, start, attack, release, total) => {
  const relStart = start + total - release;
  if (t < start || t > start + total) return 0;
  if (t < start + attack) return (t - start) / attack;
  if (t >= relStart) return Math.max(0, (start + total - t) / release);
  return 1;
};

const mixL = new Float32Array(N);
const mixR = new Float32Array(N);
const add = (i, l, r) => {
  if (i >= 0 && i < N) {
    mixL[i] += l;
    mixR[i] += r;
  };
};

// Pad voices live for the whole chord with overlap; each gets its own filter.
for (let c = 0; c * CHORD_SECONDS < DURATION; c++) {
  const chord = CHORDS[c % CHORDS.length];
  const start = c * CHORD_SECONDS;
  const total = CHORD_SECONDS + 1.2; // slight legato overlap

  chord.pad.forEach((n, vi) => {
    const f = note(n);
    const lp = makeLP(850);
    for (let i = 0; i < N; i++) {
      const t = i / SR;
      const e = env(t, start, 1.4, 1.6, total);
      if (e === 0) continue;
      // two detuned oscillators for warmth, panned gently apart
      const det = 1.005;
      const sig =
        0.5 * sine(f, t) +
        0.5 * sine(f * det, t, 0.7) +
        0.25 * sine(f * 0.5, t); // octave-down body
      const filtered = lp(sig);
      const g = 0.055 * e;
      add(i, filtered * g * 0.85, filtered * g * 1.0);
    }
  });

  // Sub bass: triangle root, quiet, centered.
  const bf = note(chord.bass);
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    const e = env(t, start, 0.35, 0.9, CHORD_SECONDS);
    if (e === 0) continue;
    add(i, triangle(bf, t) * 0.09 * e, triangle(bf, t) * 0.09 * e);
  }

  // Sparse music-box arpeggio: one possible pluck every half second.
  for (let b = 0; b < CHORD_SECONDS * 2; b++) {
    if (rand() > 0.42) continue;
    const pool = chord.arp;
    const f = note(pool[Math.floor(rand() * pool.length)]);
    const pStart = start + b * 0.5 + rand() * 0.08;
    const pan = b % 2 === 0 ? -0.35 : 0.35;
    for (let i = 0; i < SR * 1.6; i++) {
      const t = i / SR;
      const idx = Math.floor((pStart + t) * SR);
      if (idx >= N) break;
      const decay = Math.exp(-t / 0.42);
      const sig = sine(f, t) * decay * 0.05;
      add(idx, sig * (1 - Math.max(0, pan) * 0.6), sig * (1 + Math.min(0, pan) * 0.6));
    }
  }

  // Air: looping filtered noise swell, barely audible.
  let nz = 0;
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    const e = env(t, start, 2.2, 2.2, CHORD_SECONDS);
    if (e === 0) continue;
    nz += 0.02 * (rand() * 2 - 1); // integrated noise = brown-ish
    nz *= 0.985;
    const g = 0.014 * e;
    add(i, nz * g, -nz * g);
  }
}

// Master chain: soft clip, fades, DC removal, peak normalize.
const fadeIn = 2.5 * SR;
const fadeOut = 4 * SR;
let peak = 0;
for (let i = 0; i < N; i++) {
  let l = Math.tanh(mixL[i] * 1.15);
  let r = Math.tanh(mixR[i] * 1.15);
  const fi = i < fadeIn ? i / fadeIn : 1;
  const fo = i > N - fadeOut ? (N - i) / fadeOut : 1;
  const g = Math.min(fi, fo);
  l *= g;
  r *= g;
  mixL[i] = l;
  mixR[i] = r;
  peak = Math.max(peak, Math.abs(l), Math.abs(r));
}
const norm = 0.92 / peak;

// Encode 16-bit stereo PCM WAV.
const dataBytes = N * 4;
const buf = Buffer.alloc(44 + dataBytes);
buf.write("RIFF", 0);
buf.writeUInt32LE(36 + dataBytes, 4);
buf.write("WAVE", 8);
buf.write("fmt ", 12);
buf.writeUInt32LE(16, 16);
buf.writeUInt16LE(1, 20); // PCM
buf.writeUInt16LE(2, 22); // stereo
buf.writeUInt32LE(SR, 24);
buf.writeUInt32LE(SR * 4, 28); // byte rate
buf.writeUInt16LE(4, 32); // block align
buf.writeUInt16LE(16, 34); // bits per sample
buf.write("data", 36);
buf.writeUInt32LE(dataBytes, 40);
for (let i = 0; i < N; i++) {
  const l = Math.max(-1, Math.min(1, mixL[i] * norm));
  const r = Math.max(-1, Math.min(1, mixR[i] * norm));
  buf.writeInt16LE(Math.round(l * 32767), 44 + i * 4);
  buf.writeInt16LE(Math.round(r * 32767), 46 + i * 4);
}

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, buf);
console.log(
  `music bed written: ${outPath} (${(buf.length / 1024 / 1024).toFixed(1)} MB, ${DURATION}s, 44.1kHz stereo)`
);
