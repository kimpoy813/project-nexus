import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { LogoBadge, Wordmark } from "../components/BrandMark.jsx";
import { Rise, Pill } from "../components/Ui.jsx";
import { JOURNEY_STEPS } from "../content.js";

export const OutroScene = () => (
  <AbsoluteFill>
    <Background />
    <AbsoluteFill
      style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}
    >
      <Rise delay={4} style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <LogoBadge size={124} animate />
        <div style={{ height: 22 }} />
        <Wordmark fontSize={60} tagline />
      </Rise>

      <div style={{ height: 40 }} />

      <div style={{ display: "flex", gap: 10, alignItems: "center", maxWidth: 1600, flexWrap: "wrap", justifyContent: "center" }}>
        {JOURNEY_STEPS.map((step, i) => (
          <Rise key={step.title} delay={22 + i * 8} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Pill tone={i >= 5 ? "yellow" : "green"}>{step.title}</Pill>
            {i < JOURNEY_STEPS.length - 1 && (
              <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 24, fontWeight: 700 }}>→</span>
            )}
          </Rise>
        ))}
      </div>

      <Rise delay={92}>
        <div
          style={{
            marginTop: 52,
            fontSize: 44,
            fontWeight: 800,
            color: COLORS.white,
            textAlign: "center",
            letterSpacing: -0.5,
            maxWidth: 1300,
          }}
        >
          Log in, open your dashboard, and start a new proposal
        </div>
      </Rise>

      <Rise delay={108}>
        <div style={{ marginTop: 20, fontSize: 28, color: "rgba(255,255,255,0.65)" }}>
          <span style={{ fontFamily: "monospace", color: COLORS.accent }}>/login/</span>
          {"  →  "}
          <span style={{ fontFamily: "monospace", color: COLORS.accent }}>/proposals/new/</span>
        </div>
      </Rise>
    </AbsoluteFill>
  </AbsoluteFill>
);
