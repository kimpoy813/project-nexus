import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  FadeIn,
} from "../components/Ui.jsx";
import { ROLES } from "../content.js";

const ACCENT = {
  yellow: COLORS.accent,
  green: "#9edb8a",
  maroon: "#e6b3b5",
};

export const RoleDetailScene = ({ roleIndex, sceneIndex }) => {
  const role = ROLES[roleIndex];
  const accent = ACCENT[role.accent];

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={sceneIndex} total={19}>
        <AbsoluteFill
          style={{
            padding: `0 ${LAYOUT.marginX}px`,
            justifyContent: "center",
          }}
        >
          <Rise delay={4}>
            <Eyebrow>
              Role {roleIndex + 1} of 7 — what they can do
            </Eyebrow>
          </Rise>

          <div style={{ display: "flex", gap: 56, marginTop: 18 }}>
            {/* left: identity */}
            <Rise
              delay={10}
              style={{ width: 440, flexShrink: 0, display: "flex", flexDirection: "column" }}
            >
              <div
                style={{
                  fontSize: 120,
                  fontWeight: 800,
                  lineHeight: 1,
                  color: "rgba(255,255,255,0.10)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {String(roleIndex + 1).padStart(2, "0")}
              </div>
              <div
                style={{
                  fontSize: 56,
                  fontWeight: 800,
                  color: COLORS.white,
                  lineHeight: 1.08,
                  marginTop: 18,
                }}
              >
                {role.key}
              </div>
              <div
                style={{
                  fontSize: 25,
                  lineHeight: 1.45,
                  color: accent,
                  fontWeight: 600,
                  marginTop: 18,
                }}
              >
                {role.who}
              </div>

              {role.boundary && (
                <div
                  style={{
                    marginTop: 30,
                    background: "rgba(90,17,19,0.30)",
                    border: "1px solid rgba(240,195,197,0.35)",
                    borderRadius: LAYOUT.radius,
                    padding: "20px 22px",
                    fontSize: 19,
                    lineHeight: 1.5,
                    color: SURFACE.text,
                  }}
                >
                  <b style={{ color: "#f0c3c5", fontWeight: 700 }}>
                    A deliberate limit:
                  </b>{" "}
                  {role.boundary}
                </div>
              )}
            </Rise>

            {/* divider */}
            <div
              style={{
                width: 1,
                background: SURFACE.hairlineSoft,
                margin: "8px 0",
              }}
            />

            {/* right: functions as an editorial hairline list */}
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
              }}
            >
              {role.functions.map((fn, i) => (
                <FadeIn key={fn} delay={22 + i * 8}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 20,
                      padding: i === 0 ? "14px 0 16px" : "16px 0",
                      borderTop:
                        i === 0
                          ? "none"
                          : `1px solid ${SURFACE.hairlineSoft}`,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 19,
                        fontWeight: 700,
                        color: COLORS.accent,
                        fontVariantNumeric: "tabular-nums",
                        flexShrink: 0,
                        width: 34,
                      }}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span
                      style={{
                        fontSize: 25,
                        lineHeight: 1.45,
                        color: SURFACE.text,
                        fontWeight: 500,
                      }}
                    >
                      {fn}
                    </span>
                  </div>
                </FadeIn>
              ))}
            </div>
          </div>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
