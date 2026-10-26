import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { LogoBadge, Wordmark } from "../components/BrandMark.jsx";
import { Rise, FadeIn } from "../components/Ui.jsx";
import { JOURNEY_STEPS } from "../content.js";

export const OutroScene = () => (
  <AbsoluteFill>
    <Background />
    <AbsoluteFill
      style={{
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        padding: `0 ${LAYOUT.marginX}px`,
      }}
    >
      <Rise
        delay={4}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <LogoBadge size={116} animate />
        <div style={{ height: 24 }} />
        <Wordmark fontSize={56} tagline />
      </Rise>

      {/* Journey as one connected numbered line */}
      <div
        style={{
          position: "relative",
          display: "flex",
          justifyContent: "space-between",
          width: LAYOUT.contentWidth,
          marginTop: 56,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 19,
            left: 20,
            right: 20,
            height: 1,
            background: SURFACE.hairline,
          }}
        />
        {JOURNEY_STEPS.map((step, i) => (
          <FadeIn
            key={step.title}
            delay={20 + i * 6}
            style={{
              position: "relative",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              width: 150,
            }}
          >
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                background: i >= 5 ? COLORS.accent : COLORS.primaryBright,
                border: `1.5px solid ${
                  i >= 5 ? COLORS.accent : "rgba(201,240,179,0.5)"
                }`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 17,
                fontWeight: 800,
                color: i >= 5 ? COLORS.primary : COLORS.white,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {i + 1}
            </div>
            <div
              style={{
                marginTop: 12,
                fontSize: 18,
                fontWeight: 700,
                color: SURFACE.text,
                textAlign: "center",
              }}
            >
              {step.title}
            </div>
          </FadeIn>
        ))}
      </div>

      <Rise delay={80}>
        <div
          style={{
            marginTop: 52,
            fontSize: 40,
            fontWeight: 800,
            color: COLORS.white,
            textAlign: "center",
            letterSpacing: -0.4,
          }}
        >
          Log in, open your dashboard, and start a new proposal
        </div>
      </Rise>

      <Rise delay={94}>
        <div style={{ marginTop: 24, display: "flex", gap: 16 }}>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: COLORS.white,
              border: `1.5px solid ${SURFACE.hairline}`,
              borderRadius: 12,
              padding: "13px 30px",
            }}
          >
            Sign in
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: COLORS.primary,
              background: COLORS.accent,
              borderRadius: 12,
              padding: "13px 30px",
            }}
          >
            Start a new proposal →
          </div>
        </div>
      </Rise>
    </AbsoluteFill>
  </AbsoluteFill>
);
