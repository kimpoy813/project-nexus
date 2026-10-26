import React from "react";
import { Img, staticFile, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "../theme.js";

// The real NExUS logo (the green "Ni" monogram, static/images/nexus-logo.svg
// in the Django app), presented exactly as the app presents it on the dark
// green auth panel: a white rounded tile with padding and a soft shadow.
export const LogoBadge = ({ size = 120, animate = false, tilePadding = 0.16 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = animate
    ? spring({ frame, fps, config: { damping: 14, stiffness: 120 } })
    : 1;

  return (
    <div
      style={{
        width: size,
        height: size,
        transform: `scale(${pop})`,
        borderRadius: size * 0.22,
        background: COLORS.white,
        padding: size * tilePadding,
        boxShadow: "0 18px 50px rgba(0,0,0,0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxSizing: "border-box",
      }}
    >
      <Img
        src={staticFile("nexus-logo.svg")}
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />
    </div>
  );
};

// Raw logo without the tile — for light "browser window" mockups where the
// app itself shows the logo directly on white (e.g. the public navbar).
export const LogoRaw = ({ size = 44 }) => (
  <Img
    src={staticFile("nexus-logo.svg")}
    style={{ width: size, height: size, objectFit: "contain" }}
  />
);

export const Wordmark = ({
  fontSize = 56,
  color = COLORS.white,
  tagline = false,
  taglineColor = "rgba(255,255,255,0.55)",
}) => (
  <div style={{ display: "flex", flexDirection: "column" }}>
    <div
      style={{
        fontFamily: "Inter, sans-serif",
        fontWeight: 800,
        fontSize,
        letterSpacing: -fontSize * 0.02,
        color,
        lineHeight: 1,
      }}
    >
      NExUS
    </div>
    {tagline && (
      <div
        style={{
          marginTop: fontSize * 0.16,
          fontSize: fontSize * 0.21,
          fontWeight: 700,
          letterSpacing: fontSize * 0.09,
          textTransform: "uppercase",
          color: taglineColor,
        }}
      >
        Networked Extension Unified System
      </div>
    )}
  </div>
);

// Convenience lockup used in scene headers: small badge + wordmark.
export const BrandLockup = ({ light = false, badge = 44, word = 26 }) => (
  <div style={{ display: "flex", alignItems: "center", gap: badge * 0.35 }}>
    <LogoBadge size={badge} tilePadding={0.18} />
    <Wordmark fontSize={word} color={light ? COLORS.primary : COLORS.white} />
  </div>
);
