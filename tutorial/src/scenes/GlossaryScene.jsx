import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { Rise, SceneShell, Eyebrow, Heading } from "../components/Ui.jsx";
import { GLOSSARY } from "../content.js";

const TermCard = ({ item, index }) => (
  <Rise delay={18 + index * 7}>
    <div
      style={{
        background: "rgba(255,255,255,0.06)",
        border: `1.5px solid ${COLORS.primaryLine}`,
        borderRadius: 18,
        padding: "22px 24px",
        height: 205,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: 27,
          fontWeight: 800,
          color: COLORS.accent,
          marginBottom: 10,
          letterSpacing: 0.3,
        }}
      >
        {item.term}
      </div>
      <div style={{ fontSize: 20.5, lineHeight: 1.45, color: "rgba(255,255,255,0.75)" }}>
        {item.meaning}
      </div>
    </div>
  </Rise>
);

export const GlossaryScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={2}>
      <AbsoluteFill style={{ padding: "150px 120px 90px" }}>
        <Rise delay={6}>
          <Eyebrow>Words you will hear</Eyebrow>
        </Rise>
        <Rise delay={12}>
          <Heading size={52}>
            The terms behind NExUS, in <span style={{ color: COLORS.accent }}>plain English</span>
          </Heading>
        </Rise>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 20,
            marginTop: 44,
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
