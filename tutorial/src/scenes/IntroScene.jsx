import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { LogoBadge, Wordmark } from "../components/BrandMark.jsx";
import { Rise } from "../components/Ui.jsx";

const STATS = [
  { figure: "7", label: "User roles, each with its own dashboard" },
  { figure: "20", label: "Guided sections in the proposal form" },
  { figure: "1", label: "Record that follows the work from idea to close" },
];

export const IntroScene = () => {
  const frame = useCurrentFrame();
  const lineGrow = interpolate(frame, [22, 52], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
        }}
      >
        <Rise delay={4}>
          <LogoBadge size={156} animate />
        </Rise>

        <div style={{ height: 34 }} />

        <Rise delay={14}>
          <Wordmark fontSize={88} tagline />
        </Rise>

        <div
          style={{
            height: 3,
            width: 380 * lineGrow,
            borderRadius: 2,
            background: COLORS.accent,
            margin: "34px 0 30px",
          }}
        />

        <Rise delay={26}>
          <div
            style={{
              fontSize: 54,
              fontWeight: 800,
              color: COLORS.white,
              letterSpacing: -0.6,
              textAlign: "center",
            }}
          >
            A Plain-Language Guide to NExUS
          </div>
        </Rise>
        <Rise delay={38}>
          <div
            style={{
              fontSize: 29,
              color: SURFACE.textSoft,
              marginTop: 18,
              textAlign: "center",
              maxWidth: 1180,
              lineHeight: 1.5,
            }}
          >
            What it does, what every role can do, and how a proposal travels
            from an idea to a finished, documented activity
          </div>
        </Rise>

        <div style={{ height: 64 }} />

        <Rise delay={54} style={{ display: "flex", alignItems: "stretch" }}>
          {STATS.map((s, i) => (
            <React.Fragment key={s.label}>
              {i > 0 && (
                <div
                  style={{
                    width: 1,
                    background: "rgba(255,255,255,0.22)",
                    margin: "6px 44px",
                  }}
                />
              )}
              <div
                style={{
                  width: 360,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  textAlign: "center",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    fontSize: 52,
                    fontWeight: 800,
                    color: COLORS.accent,
                    lineHeight: 1,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {s.figure}
                </div>
                <div
                  style={{
                    fontSize: 21,
                    lineHeight: 1.45,
                    color: SURFACE.textSoft,
                  }}
                >
                  {s.label}
                </div>
              </div>
            </React.Fragment>
          ))}
        </Rise>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
