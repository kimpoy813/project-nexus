import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { SceneShell, Eyebrow, Heading } from "../components/Ui.jsx";
import { SlideIn, DrawPath } from "../components/Motion.jsx";
import {
  IMPLEMENTATION_STEPS,
  IMPLEMENTATION_DESCRIPTIONS,
  REPORTING_FEATURES,
} from "../content.js";

const cardWidth =
  (LAYOUT.contentWidth - LAYOUT.gutter * (IMPLEMENTATION_STEPS.length - 1)) /
  IMPLEMENTATION_STEPS.length;

export const ReportScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={15} total={19}>
      <AbsoluteFill
        style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
      >
        <SlideIn delay={4} from="up" distance={18}>
          <Eyebrow>Running the activity — and proving it happened</Eyebrow>
        </SlideIn>
        <SlideIn delay={10} from="up" distance={22}>
          <Heading size={44}>
            Delivery, monitoring and reports stay{" "}
            <span style={{ color: COLORS.accent }}>on the same record</span>
          </Heading>
        </SlideIn>

        {/* implementation pipeline */}
        <div style={{ position: "relative", marginTop: 34, height: 218 }}>
          <svg
            width={LAYOUT.contentWidth}
            height={6}
            style={{ position: "absolute", top: 34, left: 0, overflow: "visible" }}
          >
            <line
              x1={cardWidth / 2}
              y1={3}
              x2={LAYOUT.contentWidth - cardWidth / 2}
              y2={3}
              stroke="rgba(255,255,255,0.10)"
              strokeWidth={2}
            />
            <DrawPath
              d={`M${cardWidth / 2} 3 H${LAYOUT.contentWidth - cardWidth / 2}`}
              length={LAYOUT.contentWidth - cardWidth}
              delay={60}
              duration={70}
              stroke={COLORS.accent}
              strokeWidth={2.5}
            />
          </svg>
          <div style={{ display: "flex", gap: LAYOUT.gutter }}>
            {IMPLEMENTATION_STEPS.map((step, i) => (
              <SlideIn
                key={step}
                delay={28 + i * 9}
                from="up"
                distance={26}
                style={{ width: cardWidth }}
              >
                <div
                  style={{
                    width: 70,
                    height: 70,
                    borderRadius: "50%",
                    background: COLORS.accent,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 26,
                    fontWeight: 800,
                    color: COLORS.primary,
                    margin: "0 auto 14px",
                  }}
                >
                  {i + 1}
                </div>
                <div
                  style={{
                    background: SURFACE.panel,
                    border: `1px solid ${SURFACE.hairlineSoft}`,
                    borderRadius: LAYOUT.radius,
                    padding: "16px 16px 18px",
                    height: 130,
                  }}
                >
                  <div
                    style={{
                      fontSize: 17.5,
                      fontWeight: 800,
                      lineHeight: 1.25,
                      color: COLORS.white,
                      marginBottom: 8,
                    }}
                  >
                    {step}
                  </div>
                  <div
                    style={{
                      fontSize: 15.5,
                      lineHeight: 1.4,
                      color: SURFACE.textSoft,
                    }}
                  >
                    {IMPLEMENTATION_DESCRIPTIONS[i]}
                  </div>
                </div>
              </SlideIn>
            ))}
          </div>
        </div>

        {/* reporting conveniences arrive with the second narration line */}
        <div
          style={{
            display: "flex",
            gap: LAYOUT.gutter,
            marginTop: 34,
          }}
        >
          {REPORTING_FEATURES.map((f, i) => (
            <SlideIn
              key={f.title}
              delay={148 + i * 11}
              from={i % 2 === 0 ? "left" : "right"}
              distance={42}
              style={{ flex: 1 }}
            >
              <div
                style={{
                  background: SURFACE.panelStrong,
                  border: `1px solid ${SURFACE.hairlineSoft}`,
                  borderRadius: LAYOUT.radius,
                  padding: "20px 22px",
                  height: 188,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div
                  style={{
                    fontSize: 21,
                    fontWeight: 800,
                    color: COLORS.accent,
                    marginBottom: 10,
                    lineHeight: 1.25,
                  }}
                >
                  {f.title}
                </div>
                <div
                  style={{
                    fontSize: 17.5,
                    lineHeight: 1.45,
                    color: SURFACE.textSoft,
                  }}
                >
                  {f.text}
                </div>
              </div>
            </SlideIn>
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
