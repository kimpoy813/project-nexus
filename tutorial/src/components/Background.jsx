import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";

// Shared backdrop, deliberately static: a deep institutional-green field
// with one soft top light, a faint technical grid and a film-grain overlay.
// No drifting glows or animated layers — motion comes from the content.
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

export const Background = ({ variant = "dark" }) => {
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
