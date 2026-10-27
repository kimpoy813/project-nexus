/**
 * Scans public/narration for timed voiceover segments and writes
 * src/narration-manifest.json. Root.jsx mounts <Audio> at each segment's `at`
 * frame and Motion.jsx renders synced captions from the same data, so the
 * spoken words always match the visual beat.
 *
 * File convention: sXX-YY.mp3 (natural TTS, preferred) or .wav (offline
 * meSpeak fallback). MP3 wins if both exist for one segment. The script
 * measures each clip's duration directly (MP3 frame headers / WAV header),
 * so no external tooling is required.
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { NARRATION } from "../src/narration.js";

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, "..", "public", "narration");
const out = join(here, "..", "src", "narration-manifest.json");
mkdirSync(dir, { recursive: true });

const wavDuration = (buf) => {
  let off = 12;
  while (off + 8 <= buf.length) {
    const id = buf.toString("latin1", off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    if (id === "fmt ") {
      var channels = buf.readUInt16LE(off + 10);
      var sampleRate = buf.readUInt32LE(off + 12);
      var bits = buf.readUInt16LE(off + 22);
    }
    if (id === "data") return size / (sampleRate * channels * (bits / 8));
    off += 8 + size + (size % 2);
  }
  throw new Error("no data chunk in WAV");
};

const mp3Duration = (buf) => {
  const brV1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0];
  const brV2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0];
  const srV1 = [44100, 48000, 32000];
  const srV2 = [22050, 24000, 16000];
  let i = 0;
  if (buf.slice(0, 3).toString() === "ID3") {
    i =
      10 +
      ((buf[6] & 0x7f) << 21 |
        (buf[7] & 0x7f) << 14 |
        (buf[8] & 0x7f) << 7 |
        (buf[9] & 0x7f));
  }
  let frames = 0;
  let sampleRate = 44100;
  while (i + 4 <= buf.length) {
    if (buf[i] !== 0xff || (buf[i + 1] & 0xe0) !== 0xe0) {
      i++;
      continue;
    }
    const ver = (buf[i + 1] >> 3) & 3;
    const layer = (buf[i + 1] >> 1) & 3;
    const bri = (buf[i + 2] >> 4) & 0xf;
    const sri = (buf[i + 2] >> 2) & 3;
    const pad = (buf[i + 2] >> 1) & 1;
    if (layer !== 1 || bri === 0 || bri === 15 || sri === 3) {
      i++;
      continue;
    }
    const v1 = ver === 3;
    const bitrate = (v1 ? brV1 : brV2)[bri] * 1000;
    sampleRate = (v1 ? srV1 : srV2)[sri];
    if (!bitrate || !sampleRate) {
      i++;
      continue;
    }
    i += Math.floor((144 * bitrate) / sampleRate) + pad;
    frames++;
  }
  return (frames * 1152) / sampleRate;
};

const files = new Set(readdirSync(dir));
const scenes = [];
let missing = 0;

for (let sceneIdx = 0; sceneIdx < NARRATION.length; sceneIdx++) {
  const scene = sceneIdx + 1;
  const segments = [];
  for (let segIdx = 0; segIdx < NARRATION[sceneIdx].segments.length; segIdx++) {
    const seg = NARRATION[sceneIdx].segments[segIdx];
    const stem = `s${String(scene).padStart(2, "0")}-${String(segIdx + 1).padStart(2, "0")}`;
    const file = files.has(`${stem}.mp3`) ? `${stem}.mp3` : files.has(`${stem}.wav`) ? `${stem}.wav` : null;
    if (!file) {
      missing++;
      continue;
    }
    const data = readFileSync(join(dir, file));
    const seconds = file.endsWith(".wav") ? wavDuration(data) : mp3Duration(data);
    segments.push({
      file: `narration/${file}`,
      at: seg.at,
      frames: Math.ceil(seconds * 30),
      text: seg.text,
    });
  }
  if (segments.length) scenes.push({ scene, segments });
}

const manifest = {
  count: scenes.reduce((n, s) => n + s.segments.length, 0),
  scenes,
};
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(manifest, null, 2) + "\n");
console.log(
  `narration manifest: ${manifest.count} segment(s) across ${scenes.length} scene(s)` +
    (missing ? `, ${missing} segment(s) missing clips` : "")
);
