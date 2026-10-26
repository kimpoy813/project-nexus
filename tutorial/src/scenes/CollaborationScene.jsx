import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Body,
  GlassCard,
  Glyph,
} from "../components/Ui.jsx";
import { COLLABORATION_FEATURES, PROPOSAL_STATUSES } from "../content.js";

const ICONS = ["doc", "return", "users", "globe"];

export const CollaborationScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={13} total={19}>
      <AbsoluteFill style={{ padding: "150px 120px 100px" }}>
        <Rise delay={4}>
          <Eyebrow>Reviews without lost paperwork</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={52}>
            Comments, revisions and approvals — <span style={{ color: COLORS.accent }}>all in one place</span>
          </Heading>
        </Rise>

        <div style={{ display: "flex", gap: 26, marginTop: 46 }}>
          {COLLABORATION_FEATURES.map((f, i) => (
            <Rise key={f.title} delay={22 + i * 12} style={{ flex: 1 }}>
              <GlassCard style={{ height: 330, display: "flex", flexDirection: "column" }}>
                <div
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: 18,
                    background: "rgba(245,229,135,0.12)",
                    border: "1.5px solid rgba(245,229,135,0.35)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 22,
                  }}
                >
                  <Glyph name={ICONS[i]} size={36} />
                </div>
                <div style={{ fontSize: 27, fontWeight: 800, color: COLORS.white, lineHeight: 1.2, marginBottom: 12 }}>
                  {f.title}
                </div>
                <div style={{ fontSize: 21, lineHeight: 1.5, color: "rgba(255,255,255,0.72)" }}>
                  {f.text}
                </div>
              </GlassCard>
            </Rise>
          ))}
        </div>

        <Rise delay={80}>
          <Body style={{ marginTop: 40, fontSize: 24 }}>
            The proposal&apos;s status moves through these stages, visible to
            everyone involved:
          </Body>
        </Rise>
        <Rise delay={92} style={{ display: "flex", gap: 12, marginTop: 18, flexWrap: "wrap" }}>
          {PROPOSAL_STATUSES.map((s, i) => (
            <div
              key={s}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                background: i >= 4 ? "rgba(180,69,63,0.18)" : "rgba(255,255,255,0.07)",
                border: `1.5px solid ${i >= 4 ? "rgba(180,69,63,0.45)" : COLORS.primaryLine}`,
                borderRadius: 999,
                padding: "10px 20px",
                fontSize: 20,
                fontWeight: 600,
                color: "rgba(255,255,255,0.88)",
              }}
            >
              <span style={{ color: COLORS.accent, fontWeight: 800 }}>{i + 1}</span>
              {s}
            </div>
          ))}
        </Rise>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
