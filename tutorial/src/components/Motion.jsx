import React from "react";
import {
  Easing,
  interpolate,
  useCurrentFrame,
  staticFile,
} from "remotion";
import { COLORS, MOTION } from "../theme.js";
import narrationManifest from "../narration-manifest.json";

const easeOut = Easing.out(Easing.cubic);
const easeInOut = Easing.inOut(Easing.cubic);

const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));

// Fade with a directional slide. `from` sets the entry direction.
export const SlideIn = ({
  children,
  delay = 0,
  from = "up",
  distance = 36,
  duration = MOTION.fadeDuration + 4,
  style,
}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  const delta = (1 - t) * distance;
  const transform =
    from === "up"
      ? `translateY(${delta}px)`
      : from === "down"
      ? `translateY(${-delta}px)`
      : from === "left"
      ? `translateX(${-delta}px)`
      : `translateX(${delta}px)`;
  return (
    <div style={{ opacity: t, transform, ...style }}>{children}</div>
  );
};

// Scale-and-fade settle for badges and icons.
export const PopIn = ({ children, delay = 0, scale = 0.82, style }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return (
    <div
      style={{
        opacity: t,
        transform: `scale(${scale + (1 - scale) * t})`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Count-up number, tabular figures so width never jitters.
export const AnimatedNumber = ({
  value,
  delay = 0,
  duration = 34,
  suffix = "",
  style,
}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOut,
  });
  const shown = Math.round(value * t);
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>
      {shown}
      {suffix}
    </span>
  );
};

// Animated horizontal fill bar. `progress` is a 0..1 value (frame-driven).
export const ProgressBar = ({ progress, height = 8, color, track, style }) => (
  <div
    style={{
      height,
      borderRadius: height,
      background: track ?? "rgba(255,255,255,0.14)",
      overflow: "hidden",
      ...style,
    }}
  >
    <div
      style={{
        width: `${clamp(progress) * 100}%`,
        height: "100%",
        borderRadius: height,
        background: color ?? COLORS.accent,
      }}
    />
  </div>
);

// SVG path that draws itself. Pass the measured path length explicitly so no
// runtime measurement is needed during headless rendering.
export const DrawPath = ({
  d,
  length,
  delay = 0,
  duration = 40,
  stroke = COLORS.accent,
  strokeWidth = 3,
  style,
  ...rest
}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOut,
  });
  return (
    <path
      d={d}
      fill="none"
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeDasharray={length}
      strokeDashoffset={length * (1 - t)}
      style={style}
      {...rest}
    />
  );
};

// Check mark that strokes itself on.
export const DrawCheck = ({ delay = 0, size = 26, color = COLORS.accent }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  const len = 30;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M20 6 9 17l-5-5"
        stroke={color}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={len}
        strokeDashoffset={len * (1 - t)}
      />
    </svg>
  );
};

// A small "record" token that glides along x keyframes, used to show one
// proposal record traveling through a pipeline. With fadeAfterLast it
// dissolves on arrival so it never covers the final node's check mark.
export const FlowToken = ({
  keyframes,
  size = 22,
  color = COLORS.accent,
  fadeAfterLast = 0,
}) => {
  const frame = useCurrentFrame();
  const xs = keyframes.map((k) => k.x);
  const ys = keyframes.map((k) => k.y);
  const fs = keyframes.map((k) => k.frame);
  const x = interpolate(frame, fs, xs, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(frame, fs, ys, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lastFrame = fs[fs.length - 1];
  const opacity =
    fadeAfterLast > 0
      ? interpolate(frame, [lastFrame, lastFrame + fadeAfterLast], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        boxShadow: `0 0 18px ${color}`,
        transform: "translate(-50%, -50%)",
        opacity,
        zIndex: 5,
      }}
    />
  );
};

// Synced caption bar: shows the narration line while its clip is expected to
// play, so words and visuals always agree. Reads the generated manifest.
export const Caption = ({ sceneIndex }) => {
  const frame = useCurrentFrame();
  const scene = narrationManifest.scenes?.find(
    (s) => s.scene === sceneIndex + 1
  );
  if (!scene) return null;
  const active = scene.segments.find((seg) => {
    const start = seg.at;
    const end = seg.at + seg.frames + 10;
    return frame >= start && frame <= end;
  });
  if (!active) return null;
  const fade = interpolate(
    frame,
    [active.at, active.at + 6, active.at + active.frames, active.at + active.frames + 8],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return (
    <div
      style={{
        position: "absolute",
        bottom: 34,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: fade,
        zIndex: 40,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: 1460,
          background: "rgba(8,28,5,0.72)",
          border: "1px solid rgba(255,255,255,0.14)",
          borderRadius: 14,
          padding: "14px 30px",
          fontSize: 25,
          fontWeight: 500,
          lineHeight: 1.4,
          color: "rgba(255,255,255,0.94)",
          textAlign: "center",
          backdropFilter: "blur(6px)",
        }}
      >
        {active.text}
      </div>
    </div>
  );
};

// Re-export for scenes that want the plain eased fade without movement.
export { easeOut, easeInOut };
