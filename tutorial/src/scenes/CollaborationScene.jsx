import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Body,
  Panel,
  IndexNumeral,
  FadeIn,
} from "../components/Ui.jsx";
import { COLLABORATION_FEATURES, PROPOSAL_STATUSES } from "../content.js";

export const CollaborationScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={13} total={19}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={4}>
          <Eyebrow>Reviews without lost paperwork</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={50}>
            Comments, revisions and approvals —{" "}
            <span style={{ color: COLORS.accent }}>all in one place</span>
          </Heading>
        </Rise>

        <div style={{ display: "flex", gap: LAYOUT.gutter, marginTop: 40 }}>
          {COLLABORATION_FEATURES.map((f, i) => (
            <Rise key={f.title} delay={20 + i * 7} style={{ flex: 1 }}>
              <Panel
                style={{
                  height: 300,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <IndexNumeral value={i + 1} />
                <div
                  style={{
                    fontSize: 25,
                    fontWeight: 800,
                    color: COLORS.white,
                    lineHeight: 1.25,
                    margin: "20px 0 12px",
                  }}
                >
                  {f.title}
                </div>
                <div
                  style={{
                    fontSize: 20,
                    lineHeight: 1.5,
                    color: SURFACE.textSoft,
                  }}
                >
                  {f.text}
                </div>
              </Panel>
            </Rise>
          ))}
        </div>

        <Rise delay={56}>
          <Body style={{ marginTop: 36, fontSize: 23 }}>
            The proposal&apos;s status moves through these stages, visible to
            everyone involved:
          </Body>
        </Rise>
        <FadeIn delay={66} style={{ marginTop: 16 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {PROPOSAL_STATUSES.map((s, i) => (
              <div
                key={s}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  background:
                    i >= 4 ? "rgba(180,69,63,0.14)" : SURFACE.panelStrong,
                  border: `1px solid ${
                    i >= 4
                      ? "rgba(180,69,63,0.40)"
                      : SURFACE.hairlineSoft
                  }`,
                  borderRadius: 12,
                  padding: "11px 18px",
                  fontSize: 19,
                  fontWeight: 600,
                  color: SURFACE.text,
                }}
              >
                <span
                  style={{
                    color: i >= 4 ? COLORS.rose : COLORS.accent,
                    fontWeight: 800,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                {s}
              </div>
            ))}
          </div>
        </FadeIn>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
