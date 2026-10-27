import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  SceneShell,
  Eyebrow,
  Heading,
  Panel,
  IndexNumeral,
} from "../components/Ui.jsx";
import { SlideIn, FlowToken, easeOut } from "../components/Motion.jsx";
import { COLLABORATION_FEATURES, PROPOSAL_STATUSES } from "../content.js";

const NODE_W = 168;
const PIPELINE_W = LAYOUT.contentWidth - 68; // panel padding 34px each side
const nodeCenterX = (i) =>
  NODE_W / 2 +
  (i * (PIPELINE_W - NODE_W)) / (PROPOSAL_STATUSES.length - 1);

const Pipeline = () => {
  const frame = useCurrentFrame();
  const startAt = 132;
  const stepAt = 15;
  const lineGrow = interpolate(
    frame,
    [startAt, startAt + stepAt * (PROPOSAL_STATUSES.length - 1)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeOut }
  );
  const firstX = nodeCenterX(0);
  const lastX = nodeCenterX(PROPOSAL_STATUSES.length - 1);
  return (
    <SlideIn delay={120} from="up" distance={24}>
      <div
        style={{
          marginTop: 40,
          background: "rgba(0,0,0,0.18)",
          border: `1px solid ${SURFACE.hairlineSoft}`,
          borderRadius: LAYOUT.radius,
          padding: "26px 34px 30px",
        }}
      >
        <div
          style={{
            fontSize: 18,
            fontWeight: 700,
            letterSpacing: 2,
            color: SURFACE.textFaint,
            textTransform: "uppercase",
            marginBottom: 20,
          }}
        >
          One record, seven statuses
        </div>
        <div style={{ position: "relative", width: PIPELINE_W, height: 92 }}>
          <div
            style={{
              position: "absolute",
              left: firstX,
              top: 14,
              height: 2,
              width: lastX - firstX,
              background: "rgba(255,255,255,0.14)",
            }}
          />
          <div
            style={{
              position: "absolute",
              left: firstX,
              top: 14,
              height: 2,
              width: (lastX - firstX) * lineGrow,
              background: COLORS.accent,
            }}
          />
          <FlowToken
            size={16}
            fadeAfterLast={10}
            keyframes={PROPOSAL_STATUSES.map((_, i) => ({
              frame: startAt + 4 + i * stepAt,
              x: nodeCenterX(i),
              y: 15,
            }))}
          />
          {PROPOSAL_STATUSES.map((label, i) => {
            const on = frame >= startAt + i * stepAt;
            return (
              <div
                key={label}
                style={{
                  position: "absolute",
                  left: nodeCenterX(i),
                  top: 0,
                  transform: "translateX(-50%)",
                  width: NODE_W,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 12,
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: "50%",
                    background: on ? COLORS.accent : "rgba(255,255,255,0.10)",
                    border: `2px solid ${
                      on ? COLORS.accent : "rgba(255,255,255,0.28)"
                    }`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 14,
                    fontWeight: 800,
                    color: COLORS.primary,
                  }}
                >
                  {on ? "✓" : i + 1}
                </div>
                <div
                  style={{
                    fontSize: 16.5,
                    lineHeight: 1.3,
                    fontWeight: on ? 700 : 500,
                    color: on ? COLORS.white : SURFACE.textFaint,
                  }}
                >
                  {label}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SlideIn>
  );
};

export const CollaborationScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={13} total={19}>
      <AbsoluteFill
        style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
      >
        <SlideIn delay={4} from="up" distance={18}>
          <Eyebrow>Reviews without lost paperwork</Eyebrow>
        </SlideIn>
        <SlideIn delay={10} from="up" distance={22}>
          <Heading size={46}>
            Comments, revisions and approvals —{" "}
            <span style={{ color: COLORS.accent }}>all in one place</span>
          </Heading>
        </SlideIn>

        <div style={{ display: "flex", gap: LAYOUT.gutter, marginTop: 34 }}>
          {COLLABORATION_FEATURES.map((f, i) => (
            <SlideIn
              key={f.title}
              delay={22 + i * 12}
              from={i % 2 === 0 ? "left" : "right"}
              distance={46}
              style={{ flex: 1 }}
            >
              <Panel style={{ height: 268, display: "flex", flexDirection: "column" }}>
                <IndexNumeral value={i + 1} />
                <div
                  style={{
                    fontSize: 25,
                    fontWeight: 800,
                    color: COLORS.white,
                    margin: "18px 0 12px",
                    lineHeight: 1.25,
                  }}
                >
                  {f.title}
                </div>
                <div
                  style={{
                    fontSize: 19.5,
                    lineHeight: 1.5,
                    color: SURFACE.textSoft,
                  }}
                >
                  {f.text}
                </div>
              </Panel>
            </SlideIn>
          ))}
        </div>

        <Pipeline />
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
