import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS } from "../theme.js";

// Deterministic particle field: fixed seeds so every render is identical.
const PARTICLES = Array.from({ length: 16 }, (_, i) => {
  const seed = (i * 9301 + 49297) % 233280;
  const r = seed / 233280;
  const r2 = ((i * 4099 + 7919) % 233280) / 233280;
  const r3 = ((i * 797 + 104729) % 233280) / 233280;
  return {
    left: r * 100,
    top: r2 * 100,
    size: 3 + r3 * 5,
    drift: 14 + r2 * 26,
    speed: 0.6 + r * 0.9,
    phase: r3 * Math.PI * 2,
    opacity: 0.05 + r2 * 0.09,
  };
});

const GRAIN =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">
      <filter id="n">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
        <feColorMatrix type="saturate" values="0"/>
      </filter>
      <rect width="100%" height="100%" filter="url(#n)" opacity="0.5"/>
    </svg>`
  );

// Shared backdrop: deep institutional-green field, one soft top light, a
// faint grid, film grain, and slowly drifting light particles. Motion is
// gentle and continuous so scenes never feel like static slides.
export const Background = ({ variant = "dark" }) => {
  const frame = useCurrentFrame();

  if (variant === "light") {
    return (
      <AbsoluteFill style={{ backgroundColor: COLORS.paper }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(1200px 600px at 80% -10%, rgba(16,59,7,0.08), transparent 60%)",
          }}
        />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.primary }}>
      {/* single soft light from the top, darker toward the floor */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(1500px 850px at 50% -12%, rgba(63,140,38,0.40), transparent 62%), linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,0.22) 100%)",
        }}
      />
      {/* faint static grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
          backgroundSize: "96px 96px",
        }}
      />
      {/* slow drifting particles */}
      {PARTICLES.map((p, i) => {
        const t = frame / 30;
        const y = ((p.top - (t * p.speed * p.drift) / 140 + 100) % 100);
        const x = p.left + Math.sin(t * 0.5 + p.phase) * 1.2;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: p.size,
              height: p.size,
              borderRadius: "50%",
              background: COLORS.accent,
              opacity: p.opacity,
              filter: "blur(0.5px)",
            }}
          />
        );
      })}
      {/* grain to prevent banding and give the flat color texture */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `url("${GRAIN}")`,
          opacity: 0.05,
          mixBlendMode: "overlay",
        }}
      />
    </AbsoluteFill>
  );
};
