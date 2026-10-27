import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { SceneShell, Eyebrow, Heading } from "../components/Ui.jsx";
import { SlideIn } from "../components/Motion.jsx";
import { GLOSSARY } from "../content.js";

// First six cards are the people/process words explained by VO segment 1;
// the remaining six are the document/tracking words of segment 2.
const PEOPLE_TERMS = 6;

const TermCard = ({ item, index, active }) => {
  const frame = useCurrentFrame();
  const glow = interpolate(frame, [active[0], active[1], active[2], active[3]], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const row = Math.floor(index / 4);
  return (
    <SlideIn delay={26 + row * 62 + (index % 4) * 7} from="up" distance={26}>
      <div
        style={{
          background: SURFACE.panel,
          border: `1px solid ${
            glow > 0
              ? `rgba(245,229,135,${0.25 + glow * 0.5})`
              : SURFACE.hairlineSoft
          }`,
          borderRadius: LAYOUT.radius,
          padding: "24px 26px",
          height: 172,
          display: "flex",
          flexDirection: "column",
          boxShadow:
            glow > 0
              ? `0 0 ${28 * glow}px rgba(245,229,135,${0.12 * glow})`
              : "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <span
            style={{
              width: 18,
              height: 3,
              borderRadius: 2,
              background: COLORS.accent,
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 25, fontWeight: 800, color: COLORS.accent }}>
            {item.term}
          </span>
        </div>
        <div style={{ fontSize: 19.5, lineHeight: 1.48, color: SURFACE.textSoft }}>
          {item.meaning}
        </div>
      </div>
    </SlideIn>
  );
};

export const GlossaryScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={2}>
      <AbsoluteFill
        style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
      >
        <SlideIn delay={6} from="up">
          <Eyebrow>Words you will hear</Eyebrow>
        </SlideIn>
        <SlideIn delay={12} from="up" distance={24}>
          <Heading size={48}>
            The terms behind NExUS, in{" "}
            <span style={{ color: COLORS.accent }}>plain English</span>
          </Heading>
        </SlideIn>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 20,
            marginTop: 40,
          }}
        >
          {GLOSSARY.map((item, i) => (
            <TermCard
              key={item.term}
              item={item}
              index={i}
              // People words glow under segment 1, document words under 2.
              active={
                i < PEOPLE_TERMS ? [14, 34, 158, 176] : [182, 202, 300, 322]
              }
            />
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
