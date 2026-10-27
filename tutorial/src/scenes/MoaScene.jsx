import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { SceneShell, Eyebrow, Heading, Body } from "../components/Ui.jsx";
import {
  SlideIn,
  PopIn,
  DrawCheck,
  DrawPath,
  FlowToken,
  easeOut,
} from "../components/Motion.jsx";
import { MOA_STEPS } from "../content.js";

const PIPE_WIDTH = LAYOUT.contentWidth; // 1680
const INSET = 34;
const nodeX = (i) => INSET + (i * (PIPE_WIDTH - INSET * 2)) / (MOA_STEPS.length - 1);
const ACTIVATE_AT = [40, 66, 92, 118, 144, 170];
const LINE_LENGTH = PIPE_WIDTH - INSET * 2;

const MoaNode = ({ label, i }) => {
  const frame = useCurrentFrame();
  const on = frame >= ACTIVATE_AT[i];
  const pop = interpolate(frame - ACTIVATE_AT[i], [0, 16], [0.75, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  const x = nodeX(i);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: 0,
        transform: "translateX(-50%)",
        width: 224,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        textAlign: "center",
      }}
    >
      <PopIn delay={ACTIVATE_AT[i]}>
        <div
          style={{
            width: 62,
            height: 62,
            borderRadius: "50%",
            background: on ? COLORS.accent : "rgba(255,255,255,0.08)",
            border: `2px solid ${on ? COLORS.accent : "rgba(255,255,255,0.3)"}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${pop})`,
          }}
        >
          {on ? (
            <DrawCheck delay={ACTIVATE_AT[i] + 4} size={30} color={COLORS.primary} />
          ) : (
            <span
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: SURFACE.textFaint,
              }}
            >
              {i + 1}
            </span>
          )}
        </div>
      </PopIn>
      <div
        style={{
          marginTop: 16,
          fontSize: 19,
          fontWeight: on ? 700 : 500,
          lineHeight: 1.3,
          color: on ? COLORS.white : SURFACE.textFaint,
        }}
      >
        {label}
      </div>
    </div>
  );
};

export const MoaScene = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={14} total={19}>
        <AbsoluteFill
          style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
        >
          <SlideIn delay={4} from="up" distance={18}>
            <Eyebrow>When partners are involved — the MOA</Eyebrow>
          </SlideIn>
          <SlideIn delay={10} from="up" distance={22}>
            <Heading size={46}>
              A{" "}
              <span style={{ color: COLORS.accent }}>
                Memorandum of Agreement
              </span>{" "}
              follows its own tracked pipeline
            </Heading>
          </SlideIn>
          <SlideIn delay={20} from="up" distance={16}>
            <Body style={{ marginTop: 14, maxWidth: 1500, fontSize: 24 }}>
              An MOA is the signed understanding between the institution and its
              partner. NExUS carries it through legal review, certification and
              signing — with a tracker the whole time.
            </Body>
          </SlideIn>

          <SlideIn delay={28} from="up" distance={26} style={{ marginTop: 70 }}>
            <div style={{ position: "relative", width: PIPE_WIDTH, height: 220 }}>
              {/* base track */}
              <svg
                width={PIPE_WIDTH}
                height={6}
                style={{ position: "absolute", top: 28, left: 0, overflow: "visible" }}
              >
                <line
                  x1={INSET}
                  y1={3}
                  x2={PIPE_WIDTH - INSET}
                  y2={3}
                  stroke="rgba(255,255,255,0.12)"
                  strokeWidth={2}
                />
                <DrawPath
                  d={`M${INSET} 3 H${PIPE_WIDTH - INSET}`}
                  length={LINE_LENGTH}
                  delay={36}
                  duration={136}
                  stroke={COLORS.accent}
                  strokeWidth={2.5}
                />
              </svg>
              <FlowToken
                size={18}
                fadeAfterLast={10}
                keyframes={ACTIVATE_AT.map((f, i) => ({
                  frame: f + 2,
                  x: nodeX(i),
                  y: 31,
                }))}
              />
              {MOA_STEPS.map((label, i) => (
                <MoaNode key={label} label={label} i={i} />
              ))}
            </div>
          </SlideIn>

          <SlideIn delay={186} from="up" distance={20}>
            <div
              style={{
                marginTop: 26,
                alignSelf: "center",
                background: "rgba(245,229,135,0.10)",
                border: "1px solid rgba(245,229,135,0.35)",
                borderRadius: 999,
                padding: "14px 30px",
                fontSize: 23,
                fontWeight: 600,
                color: COLORS.accent,
              }}
            >
              No partner? Skip this stage — a proposal never needs an MOA.
            </div>
          </SlideIn>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
