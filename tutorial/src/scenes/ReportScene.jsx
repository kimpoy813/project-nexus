import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Panel,
  FadeIn,
} from "../components/Ui.jsx";
import {
  IMPLEMENTATION_STEPS,
  IMPLEMENTATION_DESCRIPTIONS,
  REPORTING_FEATURES,
} from "../content.js";

export const ReportScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={15} total={19}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={4}>
          <Eyebrow>Running the activity — and proving it happened</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={46}>
            Implementation:{" "}
            <span style={{ color: COLORS.accent }}>
              six stages to final documentation
            </span>
          </Heading>
        </Rise>

        {/* One 12-column grid: six stage cards span 2 each, four reporting
            cards span 3 each — every card flush to the same outer edges. */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(12, 1fr)",
            gap: LAYOUT.gutter,
            marginTop: 36,
          }}
        >
          {IMPLEMENTATION_STEPS.map((step, i) => (
            <FadeIn
              key={step}
              delay={22 + i * 6}
              style={{ gridColumn: `span 2` }}
            >
              <div
                style={{
                  background: SURFACE.panel,
                  border: `1px solid ${SURFACE.hairlineSoft}`,
                  borderRadius: LAYOUT.radius,
                  padding: "22px 20px",
                  height: 252,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 800,
                    color: COLORS.accent,
                    letterSpacing: 1.4,
                  }}
                >
                  STAGE {String(i + 1).padStart(2, "0")}
                </div>
                <div
                  style={{
                    fontSize: 19,
                    fontWeight: 800,
                    color: COLORS.white,
                    lineHeight: 1.25,
                    margin: "12px 0 10px",
                  }}
                >
                  {step}
                </div>
                <div
                  style={{
                    fontSize: 16.5,
                    lineHeight: 1.48,
                    color: SURFACE.textSoft,
                  }}
                >
                  {IMPLEMENTATION_DESCRIPTIONS[i]}
                </div>
              </div>
            </FadeIn>
          ))}

          {REPORTING_FEATURES.map((f, i) => (
            <FadeIn
              key={f.title}
              delay={52 + i * 7}
              style={{ gridColumn: "span 3" }}
            >
              <Panel
                style={{
                  height: 196,
                  padding: "24px 26px",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div
                  style={{
                    fontSize: 21,
                    fontWeight: 800,
                    color: COLORS.accent,
                    lineHeight: 1.25,
                    marginBottom: 10,
                  }}
                >
                  {f.title}
                </div>
                <div
                  style={{
                    fontSize: 17.5,
                    lineHeight: 1.5,
                    color: SURFACE.textSoft,
                  }}
                >
                  {f.text}
                </div>
              </Panel>
            </FadeIn>
          ))}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
