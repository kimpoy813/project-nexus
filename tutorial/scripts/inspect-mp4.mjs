// Minimal MP4 inspector: walks ISO-BMFF boxes to report codec, dimensions,
// frame rate and duration. No external dependencies (offline environments).
import { openSync, readSync, closeSync, statSync } from "node:fs";

const [, , file] = process.argv;
if (!file) {
  console.error("usage: node inspect-mp4.mjs <file.mp4>");
  process.exit(1);
}

const fd = openSync(file, "r");
const size = statSync(file).size;
const buf = Buffer.alloc(size);
readSync(fd, buf, 0, size, 0);
closeSync(fd);

const type = (b, o) => b.toString("latin1", o + 4, o + 8);
const u32 = (b, o) => b.readUInt32BE(o);

// Collect box positions recursively, limited to what we need.
function walk(offset, end, depth, out) {
  while (offset + 8 <= end) {
    let len = u32(buf, offset);
    const t = type(buf, offset);
    let header = 8;
    if (len === 1) {
      len = Number(buf.readBigUInt64BE(offset + 8));
      header = 16;
    }
    if (len === 0) len = end - offset;
    out.push({ t, start: offset, end: offset + len, header, depth });
    const container = ["moov", "trak", "mdia", "minf", "stbl", "udta"].includes(t);
    if (container) walk(offset + header, offset + len, depth + 1, out);
    offset += len;
  }
}

const boxes = [];
walk(0, size, 0, boxes);
const find = (t, after = 0) => boxes.find((b) => b.t === t && b.start >= after);

// mvhd: version(1) flags(3) ... timescale/duration at different offsets per version
const mvhd = find("mvhd");
const v = buf[mvhd.start + mvhd.header];
let timescale, duration;
if (v === 1) {
  timescale = u32(buf, mvhd.start + mvhd.header + 20);
  duration = Number(buf.readBigUInt64BE(mvhd.start + mvhd.header + 24));
} else {
  timescale = u32(buf, mvhd.start + mvhd.header + 12);
  duration = u32(buf, mvhd.start + mvhd.header + 16);
}

// tkhd holds width/height as 16.16 fixed point
// Pick the video track's tkhd (the one with nonzero dimensions; audio is 0x0)
const tkhds = boxes.filter((b) => b.t === "tkhd");
let w = 0;
let h = 0;
for (const tkhd of tkhds) {
  const tkV1 = buf[tkhd.start + tkhd.header] === 1;
  w = buf.readUInt32BE(tkhd.start + tkhd.header + (tkV1 ? 88 : 76)) / 65536;
  h = buf.readUInt32BE(tkhd.start + tkhd.header + (tkV1 ? 92 : 80)) / 65536;
  if (w > 0 && h > 0) break;
}

// stsz: version/flags(4) + sample_size(4) + sample_count(4). Pick the video
// sample table (the avc1/cpv1/hev1 entry) rather than an audio track.
const stsds = boxes.filter((b) => b.t === "stsd");
const videoStsd =
  stsds.find((b) => ["avc1", "hvc1", "hev1", "vp09", "av01"].includes(type(buf, b.start + b.header + 8))) || stsds[0];
const trakStart = [...boxes].reverse().find((b) => b.t === "trak" && b.start < videoStsd.start);
const stsz = boxes.find(
  (b) => b.t === "stsz" && b.start > trakStart.start && b.start < trakStart.end
);
const frames = u32(buf, stsz.start + stsz.header + 8);

// codec from the video stsd: first sample entry box type
const codec = type(buf, videoStsd.start + videoStsd.header + 8);

const seconds = duration / timescale;
console.log(JSON.stringify({
  file,
  bytes: size,
  codec,
  width: Math.round(w),
  height: Math.round(h),
  timescale,
  duration: `${seconds.toFixed(2)}s`,
  frames,
  fps: +(frames / seconds).toFixed(3),
  hasMoov: Boolean(find("moov")),
}, null, 2));
