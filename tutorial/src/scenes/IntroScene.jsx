import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { LogoBadge, Wordmark } from "../components/BrandMark.jsx";
import { Rise, Pill } from "../components/Ui.jsx";

export const IntroScene = () => {
  const frame = useCurrentFrame();
  const lineGrow = interpolate(frame, [20, 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}
      >
        <Rise delay={4}>
          <LogoBadge size={168} animate />
        </Rise>

        <div style={{ height: 30 }} />

        <Rise delay={14}>
          <Wordmark fontSize={96} tagline />
        </Rise>

        <div
          style={{
            height: 5,
            width: 420 * lineGrow,
            borderRadius: 4,
            background: COLORS.accent,
            margin: "30px 0",
          }}
        />

        <Rise delay={26}>
          <div
            style={{
              fontSize: 58,
              fontWeight: 800,
              color: COLORS.white,
              letterSpacing: -0.6,
              textAlign: "center",
            }}
          >
            A Plain-Language Guide to NExUS
          </div>
        </Rise>
        <Rise delay={52}>
          <div style={{ fontSize: 30, color: "rgba(255,255,255,0.68)", marginTop: 16, textAlign: "center", maxWidth: 1200 }}>
            What it does, what every role can do, and how a proposal travels
            from an idea to a finished, documented activity
          </div>
        </Rise>

        <div style={{ height: 56 }} />

        <Rise delay={68} style={{ display: "flex", gap: 18 }}>
          <Pill tone="green">7 roles</Pill>
          <Pill tone="yellow">20-step proposal form</Pill>
          <Pill tone="maroon">One record, start to finish</Pill>
        </Rise>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
