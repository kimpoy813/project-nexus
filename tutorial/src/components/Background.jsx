import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";
import { COLORS } from "../theme.js";

// Dark institutional-green backdrop shared by every scene:
// vignette + faint grid + two slow-drifting glows.
export const Background = ({ variant = "dark" }) => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 900], [0, 60], {
    extrapolateRight: "extend",
  });

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
      {/* vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(1400px 900px at 50% 30%, rgba(31,107,18,0.55), transparent 70%), radial-gradient(1000px 700px at 85% 90%, rgba(90,17,19,0.45), transparent 65%)",
        }}
      />
      {/* grid */}
      <div
        style={{
          position: "absolute",
          inset: -60,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)",
          backgroundSize: "80px 80px",
          transform: `translate3d(${-drift * 0.4}px, ${-drift * 0.25}px, 0)`,
        }}
      />
      {/* drifting glows */}
      <div
        style={{
          position: "absolute",
          width: 520,
          height: 520,
          borderRadius: "50%",
          background: "rgba(245,229,135,0.10)",
          filter: "blur(90px)",
          left: 120 + drift,
          top: 620 - drift * 0.6,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 420,
          height: 420,
          borderRadius: "50%",
          background: "rgba(31,107,18,0.55)",
          filter: "blur(80px)",
          right: 140 - drift * 0.5,
          top: 90 + drift * 0.4,
        }}
      />
    </AbsoluteFill>
  );
};
