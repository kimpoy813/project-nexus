import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { Rise, SceneShell, Eyebrow, Heading, FadeIn } from "../components/Ui.jsx";
import { GLOSSARY } from "../content.js";

const TermCard = ({ item, index }) => (
  <FadeIn delay={16 + index * 5}>
    <div
      style={{
        background: SURFACE.panel,
        border: `1px solid ${SURFACE.hairlineSoft}`,
        borderRadius: LAYOUT.radius,
        padding: "24px 26px",
        height: 178,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <span
          style={{
            width: 18,
            height: 3,
            borderRadius: 2,
            background: COLORS.accent,
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontSize: 26,
            fontWeight: 800,
            color: COLORS.accent,
            letterSpacing: 0.2,
          }}
        >
          {item.term}
        </span>
      </div>
      <div
        style={{
          fontSize: 20,
          lineHeight: 1.48,
          color: SURFACE.textSoft,
        }}
      >
        {item.meaning}
      </div>
    </div>
  </FadeIn>
);

export const GlossaryScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={2}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={6}>
          <Eyebrow>Words you will hear</Eyebrow>
        </Rise>
        <Rise delay={12}>
          <Heading size={50}>
            The terms behind NExUS, in{" "}
            <span style={{ color: COLORS.accent }}>plain English</span>
          </Heading>
        </Rise>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 20,
            marginTop: 42,
          }}
        >
          {GLOSSARY.map((item, i) => (
            <TermCard key={item.term} item={item} index={i} />
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
