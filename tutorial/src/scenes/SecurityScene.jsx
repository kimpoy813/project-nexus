import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  FadeIn,
} from "../components/Ui.jsx";
import { SAFETY_FEATURES } from "../content.js";

export const SecurityScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={17} total={19}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={4}>
          <Eyebrow>Safe, tidy and easy to come back to</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={46}>
            The everyday safeguards built into{" "}
            <span style={{ color: COLORS.accent }}>every account</span>
          </Heading>
        </Rise>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 20,
            marginTop: 38,
          }}
        >
          {SAFETY_FEATURES.map((f, i) => (
            <FadeIn key={f.title} delay={16 + i * 5}>
              <div
                style={{
                  background: SURFACE.panel,
                  border: `1px solid ${SURFACE.hairlineSoft}`,
                  borderRadius: LAYOUT.radius,
                  padding: "24px 22px",
                  height: 262,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <span
                  style={{
                    fontSize: 15,
                    fontWeight: 800,
                    color: SURFACE.textFaint,
                    letterSpacing: 1.5,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 800,
                    color: COLORS.white,
                    lineHeight: 1.25,
                    margin: "16px 0 10px",
                  }}
                >
                  {f.title}
                </div>
                <div
                  style={{
                    fontSize: 17.5,
                    lineHeight: 1.5,
                    color: SURFACE.textSoft,
                  }}
                >
                  {f.text}
                </div>
              </div>
            </FadeIn>
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
