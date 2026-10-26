import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Glyph,
  GlassCard,
} from "../components/Ui.jsx";
import {
  IMPLEMENTATION_STEPS,
  IMPLEMENTATION_DESCRIPTIONS,
  REPORTING_FEATURES,
} from "../content.js";

const ICONS = ["flag", "doc", "chart", "shield", "return", "check"];

const StageCard = ({ index, title, text, icon, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 17 } });
  return (
    <div
      style={{
        flex: 1,
        background: "rgba(255,255,255,0.06)",
        border: `1.5px solid ${COLORS.primaryLine}`,
        borderRadius: 20,
        padding: "24px 20px",
        opacity: s,
        transform: `translateY(${(1 - s) * 40}px)`,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          width: 60,
          height: 60,
          borderRadius: 16,
          background: "rgba(245,229,135,0.12)",
          border: "1.5px solid rgba(245,229,135,0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 16,
        }}
      >
        <Glyph name={icon} size={28} />
      </div>
      <div style={{ fontSize: 16, fontWeight: 800, color: COLORS.accent, letterSpacing: 1.4 }}>
        STAGE {index + 1}
      </div>
      <div style={{ fontSize: 21, fontWeight: 800, color: COLORS.white, lineHeight: 1.22, marginTop: 8 }}>
        {title}
      </div>
      <div style={{ fontSize: 17.5, lineHeight: 1.45, color: "rgba(255,255,255,0.68)", marginTop: 10 }}>
        {text}
      </div>
    </div>
  );
};

export const ReportScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={15} total={19}>
      <AbsoluteFill style={{ padding: "140px 110px 90px" }}>
        <Rise delay={4}>
          <Eyebrow>Running the activity — and proving it happened</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={48}>
            Implementation: <span style={{ color: COLORS.accent }}>six stages to final documentation</span>
          </Heading>
        </Rise>

        <div style={{ display: "flex", gap: 16, marginTop: 36 }}>
          {IMPLEMENTATION_STEPS.map((step, i) => (
            <StageCard
              key={step}
              index={i}
              title={step}
              text={IMPLEMENTATION_DESCRIPTIONS[i]}
              icon={ICONS[i]}
              delay={26 + i * 12}
            />
          ))}
        </div>

        <div style={{ display: "flex", gap: 22, marginTop: 38 }}>
          {REPORTING_FEATURES.map((f, i) => (
            <Rise key={f.title} delay={56 + i * 10} style={{ flex: 1 }}>
              <GlassCard style={{ height: 208, padding: "22px 22px" }}>
                <div style={{ fontSize: 23, fontWeight: 800, color: COLORS.accent, lineHeight: 1.2, marginBottom: 10 }}>
                  {f.title}
                </div>
                <div style={{ fontSize: 18.5, lineHeight: 1.45, color: "rgba(255,255,255,0.72)" }}>
                  {f.text}
                </div>
              </GlassCard>
            </Rise>
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
