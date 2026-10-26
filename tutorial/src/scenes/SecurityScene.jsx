import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { Rise, SceneShell, Eyebrow, Heading, Glyph } from "../components/Ui.jsx";
import { SAFETY_FEATURES } from "../content.js";

const ICONS = ["users", "return", "lock", "shield", "doc", "users", "folder", "chart"];

export const SecurityScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={17} total={19}>
      <AbsoluteFill style={{ padding: "150px 120px 100px" }}>
        <Rise delay={4}>
          <Eyebrow>Safe, tidy and easy to come back to</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={48}>
            The everyday safeguards built into <span style={{ color: COLORS.accent }}>every account</span>
          </Heading>
        </Rise>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 22,
            marginTop: 52,
          }}
        >
          {SAFETY_FEATURES.map((f, i) => (
            <Rise key={f.title} delay={18 + i * 7}>
              <div
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: `1.5px solid ${COLORS.primaryLine}`,
                  borderRadius: 20,
                  padding: "24px 22px",
                  height: 272,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 16,
                    background: "rgba(245,229,135,0.12)",
                    border: "1.5px solid rgba(245,229,135,0.35)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 18,
                  }}
                >
                  <Glyph name={ICONS[i]} size={30} />
                </div>
                <div style={{ fontSize: 23, fontWeight: 800, color: COLORS.white, lineHeight: 1.2 }}>
                  {f.title}
                </div>
                <div style={{ fontSize: 18.5, lineHeight: 1.45, color: "rgba(255,255,255,0.7)", marginTop: 10 }}>
                  {f.text}
                </div>
              </div>
            </Rise>
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
