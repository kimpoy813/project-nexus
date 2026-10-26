import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Body,
  Glyph,
} from "../components/Ui.jsx";
import { MOA_STEPS } from "../content.js";

const easeOut = Easing.out(Easing.cubic);
const ACTIVATE_AT = [28, 56, 84, 112, 140, 168];

export const MoaScene = () => {
  const frame = useCurrentFrame();
  const activeCount = ACTIVATE_AT.filter((at) => frame >= at).length;
  const lineGrow = interpolate(frame, [28, 175], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={14} total={19}>
        <AbsoluteFill
          style={{
            padding: `0 ${LAYOUT.marginX}px`,
            justifyContent: "center",
          }}
        >
          <Rise delay={4}>
            <Eyebrow>After approval — the agreement stage</Eyebrow>
          </Rise>
          <Rise delay={10}>
            <Heading size={48}>
              The <span style={{ color: COLORS.accent }}>MOA tracker</span>{" "}
              walks the partnership paper to signing
            </Heading>
          </Rise>
          <Rise delay={18}>
            <Body style={{ marginTop: 16, maxWidth: 1500, fontSize: 26 }}>
              An{" "}
              <b style={{ color: COLORS.white, fontWeight: 700 }}>
                MOA — Memorandum of Agreement —
              </b>{" "}
              is the signed document that makes a partnership with another
              office or community official. NExUS moves it through six visible
              stages:
            </Body>
          </Rise>

          <Rise delay={24}>
            <div
              style={{
                marginTop: 48,
                background: SURFACE.panel,
                border: `1px solid ${SURFACE.hairlineSoft}`,
                borderRadius: LAYOUT.radius,
                padding: "58px 56px 48px",
              }}
            >
              <div style={{ position: "relative", height: 150 }}>
                <div
                  style={{
                    position: "absolute",
                    top: 37,
                    left: 60,
                    right: 60,
                    height: 4,
                    borderRadius: 3,
                    background: "rgba(255,255,255,0.12)",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    top: 37,
                    left: 60,
                    width: `calc((100% - 120px) * ${lineGrow})`,
                    height: 4,
                    borderRadius: 3,
                    background: `linear-gradient(90deg, ${COLORS.secondary}, ${COLORS.accentDeep})`,
                  }}
                />
                {MOA_STEPS.map((step, i) => {
                  const done = i < activeCount;
                  const current = i === activeCount - 1;
                  const pop = interpolate(
                    frame - ACTIVATE_AT[i],
                    [0, 16],
                    [0.86, 1],
                    {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                      easing: easeOut,
                    }
                  );
                  const pct = i / (MOA_STEPS.length - 1);
                  return (
                    <div
                      key={step}
                      style={{
                        position: "absolute",
                        left: `calc(60px + (100% - 120px) * ${pct})`,
                        top: 0,
                        opacity: frame >= ACTIVATE_AT[i] - 6 ? 1 : 0,
                        transform: `translateX(-50%) scale(${pop})`,
                        width: 200,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                      }}
                    >
                      <div
                        style={{
                          width: 78,
                          height: 78,
                          borderRadius: "50%",
                          background: done
                            ? COLORS.secondary
                            : "rgba(255,255,255,0.08)",
                          border: `2px solid ${
                            done ? COLORS.accent : SURFACE.hairline
                          }`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {done ? (
                          <Glyph name="check" size={34} color={COLORS.accent} />
                        ) : (
                          <span
                            style={{
                              color: SURFACE.textFaint,
                              fontSize: 25,
                              fontWeight: 800,
                            }}
                          >
                            {i + 1}
                          </span>
                        )}
                      </div>
                      <div
                        style={{
                          marginTop: 16,
                          fontSize: 20,
                          lineHeight: 1.3,
                          fontWeight: current ? 800 : 600,
                          color: current
                            ? COLORS.accent
                            : "rgba(255,255,255,0.78)",
                          textAlign: "center",
                        }}
                      >
                        {step}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Rise>

          <Rise delay={110}>
            <div
              style={{
                marginTop: 34,
                display: "flex",
                gap: 16,
                alignItems: "center",
                fontSize: 24,
                color: SURFACE.textSoft,
                background: "rgba(245,229,135,0.08)",
                border: `1px solid rgba(245,229,135,0.32)`,
                borderRadius: LAYOUT.radius,
                padding: "20px 28px",
              }}
            >
              <Glyph name="doc" size={30} />
              <span>
                No outside partner? Mark the MOA{" "}
                <b style={{ color: COLORS.accent, fontWeight: 700 }}>
                  Not Required
                </b>{" "}
                and the record skips straight to implementation.
              </span>
            </div>
          </Rise>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
