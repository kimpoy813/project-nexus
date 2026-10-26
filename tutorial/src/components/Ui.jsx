import React from "react";
import {
  AbsoluteFill,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, FONT } from "../theme.js";
import { BrandLockup } from "./BrandMark.jsx";

// Fade + rise entrance. `delay` is in frames.
export const Rise = ({ children, delay = 0, distance = 34, opacity = 1, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 18, stiffness: 110, mass: 0.9 },
  });
  return (
    <div
      style={{
        opacity: s * opacity,
        transform: `translateY(${(1 - s) * distance}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Pop the whole scene out gently at the very end so cuts feel softer.
export const SceneShell = ({ children, sceneIndex, total = 19, light = false }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeOut =
    frame < durationInFrames - 10
      ? 1
      : 1 - (frame - (durationInFrames - 10)) / 10;
  return (
    <AbsoluteFill style={{ fontFamily: FONT.stack, opacity: Math.max(0, fadeOut) }}>
      {children}
      <div
        style={{
          position: "absolute",
          top: 44,
          left: 72,
          display: "flex",
          alignItems: "center",
          gap: 16,
          opacity: light ? 0.95 : 0.9,
        }}
      >
        <BrandLockup light={light} />
      </div>
      <div
        style={{
          position: "absolute",
          top: 52,
          right: 72,
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: 2,
          color: light ? COLORS.muted : "rgba(255,255,255,0.55)",
        }}
      >
        {String(sceneIndex).padStart(2, "0")} / {String(total).padStart(2, "0")}
      </div>
    </AbsoluteFill>
  );
};

export const Eyebrow = ({ children, color = COLORS.accent }) => (
  <div
    style={{
      fontSize: 26,
      fontWeight: 700,
      letterSpacing: 5,
      textTransform: "uppercase",
      color,
      marginBottom: 18,
    }}
  >
    {children}
  </div>
);

export const Heading = ({ children, style, color = COLORS.white, size = 60 }) => (
  <h1
    style={{
      margin: 0,
      fontSize: size,
      lineHeight: 1.12,
      fontWeight: 800,
      color,
      letterSpacing: -0.8,
      ...style,
    }}
  >
    {children}
  </h1>
);

export const Body = ({
  children,
  style,
  color = "rgba(255,255,255,0.82)",
  size = 32,
}) => (
  <p style={{ margin: 0, fontSize: size, lineHeight: 1.55, color, fontWeight: 400, ...style }}>
    {children}
  </p>
);

export const Pill = ({ children, tone = "green", style }) => {
  const tones = {
    green: { bg: "rgba(31,107,18,0.35)", fg: "#c9f0b3", border: COLORS.primaryLine },
    yellow: { bg: "rgba(245,229,135,0.18)", fg: COLORS.accent, border: "rgba(245,229,135,0.45)" },
    maroon: { bg: "rgba(90,17,19,0.55)", fg: "#f0c3c5", border: "rgba(240,195,197,0.35)" },
    light: { bg: "#eef2e7", fg: COLORS.primary, border: COLORS.line },
    rose: { bg: "rgba(180,69,63,0.16)", fg: COLORS.rose, border: "rgba(180,69,63,0.4)" },
  };
  const t = tones[tone];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 24px",
        borderRadius: 999,
        fontSize: 24,
        fontWeight: 600,
        backgroundColor: t.bg,
        color: t.fg,
        border: `1.5px solid ${t.border}`,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Animated check bullet used for plain-language feature lists.
export const CheckRow = ({ children, delay = 0, color = COLORS.accent, size = 27 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 130 } });
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 18,
        opacity: s,
        transform: `translateX(${(1 - s) * -28}px)`,
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: size + 10,
          height: size + 10,
          borderRadius: "50%",
          background: "rgba(245,229,135,0.14)",
          border: "1.5px solid rgba(245,229,135,0.4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginTop: 2,
        }}
      >
        <Glyph name="check" size={size - 8} color={color} />
      </div>
      <div style={{ fontSize: size, lineHeight: 1.42, color: "rgba(255,255,255,0.88)", fontWeight: 500 }}>
        {children}
      </div>
    </div>
  );
};

// Glass card used across dark scenes.
export const GlassCard = ({ children, style, accent }) => (
  <div
    style={{
      background: "rgba(255,255,255,0.06)",
      border: `1.5px solid ${accent ?? COLORS.primaryLine}`,
      borderRadius: 24,
      padding: "34px 32px",
      backdropFilter: "blur(4px)",
      ...style,
    }}
  >
    {children}
  </div>
);

// Light "browser window" used for the UI mock scenes.
export const BrowserChrome = ({ url, children, style }) => (
  <div
    style={{
      width: 1560,
      borderRadius: 22,
      overflow: "hidden",
      backgroundColor: COLORS.paper,
      boxShadow: "0 40px 90px rgba(0,0,0,0.45)",
      border: "1px solid rgba(255,255,255,0.12)",
      ...style,
    }}
  >
    <div
      style={{
        height: 64,
        background: "#e9ede2",
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "0 24px",
        borderBottom: `1px solid ${COLORS.line}`,
      }}
    >
      {["#e0645a", "#e6b84c", "#6fbf62"].map((c) => (
        <div key={c} style={{ width: 16, height: 16, borderRadius: "50%", background: c }} />
      ))}
      <div
        style={{
          marginLeft: 18,
          flex: 1,
          height: 38,
          borderRadius: 10,
          background: COLORS.white,
          border: `1px solid ${COLORS.line}`,
          display: "flex",
          alignItems: "center",
          padding: "0 18px",
          color: COLORS.muted,
          fontSize: 22,
          fontWeight: 500,
        }}
      >
        🔒 {url}
      </div>
    </div>
    <div style={{ position: "relative" }}>{children}</div>
  </div>
);

// Animated doughnut ring matching the NExUS dashboard gauge card.
export const Ring = ({ value, size = 150, stroke = 14, delay = 0, label }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 20 } });
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.round(value * 100 * s);
  return (
    <div style={{ width: size, height: size, position: "relative" }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke={COLORS.line} strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={COLORS.primaryBright}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value * s)}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: COLORS.ink,
        }}
      >
        <div style={{ fontSize: size * 0.26, fontWeight: 800 }}>{pct}%</div>
        {label && (
          <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.muted, marginTop: 2 }}>
            {label}
          </div>
        )}
      </div>
    </div>
  );
};

// Mouse cursor that glides between keyframes: [{frame, x, y, click?}].
export const Cursor = ({ keyframes, size = 46 }) => {
  const frame = useCurrentFrame();
  const xs = keyframes.map((k) => k.x);
  const ys = keyframes.map((k) => k.y);
  const fs = keyframes.map((k) => k.frame);
  const x = interpolateClamp(frame, fs, xs);
  const y = interpolateClamp(frame, fs, ys);
  const click = keyframes.find((k) => k.click && Math.abs(frame - k.frame) <= 4);
  return (
    <div style={{ position: "absolute", left: x, top: y, zIndex: 30, pointerEvents: "none" }}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path
          d="M5 3l14 8-6.5 1.8L9 19 5 3z"
          fill={click ? COLORS.accent : COLORS.ink}
          stroke={COLORS.white}
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
      </svg>
      {click && (
        <div
          style={{
            position: "absolute",
            left: 8,
            top: 8,
            width: 34,
            height: 34,
            borderRadius: "50%",
            border: `3px solid ${COLORS.accentDeep}`,
            opacity: 1 - Math.abs(frame - click.frame) / 4,
            transform: `scale(${0.5 + Math.abs(frame - click.frame) * 0.28})`,
          }}
        />
      )}
    </div>
  );
};

import { interpolate as _interpolate } from "remotion";
const interpolateClamp = (frame, fs, vals) =>
  _interpolate(frame, fs, vals, { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

export const StatusBadge = ({ label, tone = "green", style }) => {
  const tones = {
    green: { bg: "#e3f2da", fg: "#1d5c10" },
    yellow: { bg: "#faf0c4", fg: "#7a5c00" },
    maroon: { bg: "#f3dede", fg: COLORS.secondary },
    rose: { bg: "#f7e1df", fg: COLORS.rose },
    gray: { bg: "#eceee8", fg: COLORS.muted },
  };
  const t = tones[tone];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "8px 18px",
        borderRadius: 999,
        fontSize: 21,
        fontWeight: 700,
        backgroundColor: t.bg,
        color: t.fg,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {label}
    </div>
  );
};

// Minimal inline icon set (stroke style consistent across scenes).
export const Glyph = ({ name, size = 34, color = COLORS.accent }) => {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };
  switch (name) {
    case "doc":
      return (
        <svg {...common}>
          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
          <path d="M14 3v5h5M9 13h6M9 17h6" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case "sign":
      return (
        <svg {...common}>
          <path d="M20 19.58V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v13.58a1 1 0 0 0 1.7.7L9 17h8l3.3 3.28a1 1 0 0 0 1.7-.7z" />
          <path d="M8 10h8M8 13h5" />
        </svg>
      );
    case "flag":
      return (
        <svg {...common}>
          <path d="M4 22V4a1 1 0 0 1 1-1h12l-3 5 3 5H5" />
        </svg>
      );
    case "check":
      return (
        <svg {...common}>
          <path d="M20 6 9 17l-5-5" />
        </svg>
      );
    case "return":
      return (
        <svg {...common}>
          <path d="M3 7v6h6" />
          <path d="M21 17a9 9 0 0 0-15-6.7L3 13" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path d="M3 3v18h18" />
          <path d="M7 15l4-4 3 3 5-6" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "lock":
      return (
        <svg {...common}>
          <rect x="4" y="11" width="16" height="10" rx="2" />
          <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        </svg>
      );
    case "globe":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z" />
        </svg>
      );
    case "folder":
      return (
        <svg {...common}>
          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        </svg>
      );
    default:
      return null;
  }
};
