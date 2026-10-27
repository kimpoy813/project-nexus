import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  interpolate as _interpolate,
  useCurrentFrame,
} from "remotion";
import { COLORS, FONT, LAYOUT, MOTION, SURFACE } from "../theme.js";
import { BrandLockup } from "./BrandMark.jsx";

const easeOut = Easing.out(Easing.cubic);

// Quiet entrance: opacity + a short rise, one easing, no spring/bounce.
export const Rise = ({ children, delay = 0, distance = MOTION.rise, style }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, MOTION.fadeDuration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return (
    <div
      style={{
        opacity: t,
        transform: `translateY(${(1 - t) * distance}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Fade with no movement, for elements already anchored to a grid.
export const FadeIn = ({ children, delay = 0, style }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame - delay, [0, MOTION.fadeDuration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return <div style={{ opacity, ...style }}>{children}</div>;
};

// Scene chrome: brand lockup + counter aligned to the shared content margins,
// with a hairline rule tying the header together. Scene-to-scene fades are
// handled by TransitionSeries in Root.jsx, so the shell stays fully opaque.
export const SceneShell = ({ children, sceneIndex, total = 19, light = false }) => {
  return (
    <AbsoluteFill style={{ fontFamily: FONT.stack }}>
      {children}
      <div
        style={{
          position: "absolute",
          top: LAYOUT.headerTop,
          left: LAYOUT.marginX,
          right: LAYOUT.marginX,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <BrandLockup light={light} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            fontSize: 20,
            fontWeight: 600,
            letterSpacing: 2,
            color: light ? COLORS.muted : SURFACE.textFaint,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          <span
            style={{
              width: 44,
              height: 1,
              background: light ? COLORS.line : SURFACE.hairline,
            }}
          />
          {String(sceneIndex).padStart(2, "0")} / {String(total).padStart(2, "0")}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const Eyebrow = ({ children, color = COLORS.accent }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 14,
      fontSize: 22,
      fontWeight: 700,
      letterSpacing: 3,
      textTransform: "uppercase",
      color,
      marginBottom: 20,
    }}
  >
    <span style={{ width: 28, height: 3, borderRadius: 2, background: color }} />
    {children}
  </div>
);

export const Heading = ({ children, style, color = COLORS.white, size = 56 }) => (
  <h1
    style={{
      margin: 0,
      fontSize: size,
      lineHeight: 1.14,
      fontWeight: 800,
      color,
      letterSpacing: -0.7,
      ...style,
    }}
  >
    {children}
  </h1>
);

export const Body = ({
  children,
  style,
  color = SURFACE.textSoft,
  size = 30,
}) => (
  <p
    style={{
      margin: 0,
      fontSize: size,
      lineHeight: 1.55,
      color,
      fontWeight: 400,
      ...style,
    }}
  >
    {children}
  </p>
);

// Restrained label chip: flat tint, no heavy outline.
export const Pill = ({ children, tone = "green", style }) => {
  const tones = {
    green: { bg: "rgba(31,107,18,0.40)", fg: "#c9f0b3" },
    yellow: { bg: "rgba(245,229,135,0.16)", fg: COLORS.accent },
    maroon: { bg: "rgba(90,17,19,0.55)", fg: "#f0c3c5" },
    light: { bg: "#eef2e7", fg: COLORS.primary },
    rose: { bg: "rgba(180,69,63,0.18)", fg: COLORS.rose },
  };
  const t = tones[tone];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        padding: "11px 22px",
        borderRadius: 999,
        fontSize: 23,
        fontWeight: 600,
        backgroundColor: t.bg,
        color: t.fg,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Editorial list marker: a small gold dot, fading in place (no slide).
export const PointRow = ({ children, delay = 0, size = 26 }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame - delay, [0, MOTION.fadeDuration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 18,
        opacity,
      }}
    >
      <span
        style={{
          flexShrink: 0,
          width: 9,
          height: 9,
          borderRadius: "50%",
          background: COLORS.accent,
          transform: "translateY(-3px)",
        }}
      />
      <div
        style={{
          fontSize: size,
          lineHeight: 1.45,
          color: SURFACE.text,
          fontWeight: 500,
        }}
      >
        {children}
      </div>
    </div>
  );
};

// Back-compat alias used by scenes not yet migrated.
export const CheckRow = PointRow;

// Quiet panel: near-opaque fill, single hairline border, no blur.
export const Panel = ({ children, style, accent }) => (
  <div
    style={{
      background: SURFACE.panel,
      border: `1px solid ${accent ?? SURFACE.hairlineSoft}`,
      borderRadius: LAYOUT.radius,
      padding: "32px 30px",
      ...style,
    }}
  >
    {children}
  </div>
);

export const GlassCard = Panel;

// Large translucent index numeral used instead of repeated icon tiles.
export const IndexNumeral = ({ value, color = COLORS.accent, style }) => (
  <div
    style={{
      fontSize: 44,
      fontWeight: 800,
      letterSpacing: 1,
      color,
      fontVariantNumeric: "tabular-nums",
      lineHeight: 1,
      ...style,
    }}
  >
    {String(value).padStart(2, "0")}
  </div>
);

// Light "browser window" for the UI mock scenes. Neutral window controls and
// an inline SVG lock instead of traffic-light dots and an emoji.
export const BrowserChrome = ({ url, children, style }) => (
  <div
    style={{
      width: 1560,
      borderRadius: 20,
      overflow: "hidden",
      backgroundColor: COLORS.paper,
      boxShadow: "0 30px 70px rgba(0,0,0,0.40)",
      border: `1px solid ${SURFACE.hairline}`,
      ...style,
    }}
  >
    <div
      style={{
        height: 60,
        background: "#e9ede2",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "0 24px",
        borderBottom: `1px solid ${COLORS.line}`,
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{ width: 12, height: 12, borderRadius: "50%", background: "#c4cbb9" }}
        />
      ))}
      <div
        style={{
          marginLeft: 18,
          flex: 1,
          height: 36,
          borderRadius: 9,
          background: COLORS.white,
          border: `1px solid ${COLORS.line}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 18px",
          color: COLORS.muted,
          fontSize: 21,
          fontWeight: 500,
        }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke={COLORS.muted} strokeWidth="2.2" strokeLinecap="round">
          <rect x="4" y="11" width="16" height="10" rx="2" />
          <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        </svg>
        {url}
      </div>
    </div>
    <div style={{ position: "relative" }}>{children}</div>
  </div>
);

// Doughnut ring matching the NExUS dashboard gauge card.
export const Ring = ({ value, size = 150, stroke = 14, delay = 0, label }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, 28], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.round(value * 100 * t);
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
          strokeDashoffset={c * (1 - value * t)}
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

// Mouse cursor gliding between keyframes. A click is a quiet scale-down;
// no expanding halo rings.
export const Cursor = ({ keyframes, size = 44 }) => {
  const frame = useCurrentFrame();
  const xs = keyframes.map((k) => k.x);
  const ys = keyframes.map((k) => k.y);
  const fs = keyframes.map((k) => k.frame);
  const x = interpolateClamp(frame, fs, xs);
  const y = interpolateClamp(frame, fs, ys);
  const click = keyframes.find((k) => k.click && Math.abs(frame - k.frame) <= 3);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        zIndex: 30,
        pointerEvents: "none",
        transform: click ? "scale(0.86)" : "scale(1)",
      }}
    >
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        <path
          d="M5 3l14 8-6.5 1.8L9 19 5 3z"
          fill={COLORS.ink}
          stroke={COLORS.white}
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};

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

// Minimal inline icon set, retained for the product mockups and the few
// places a pictogram carries meaning (shield, lock, globe).
export const Glyph = ({ name, size = 34, color = COLORS.accent }) => {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: 1.8,
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
