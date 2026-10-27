import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { SceneShell, Eyebrow } from "../components/Ui.jsx";
import { SlideIn, PopIn } from "../components/Motion.jsx";
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
          style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
        >
          <SlideIn delay={4} from="up" distance={18}>
            <Eyebrow>Role {roleIndex + 1} of 7 — what they can do</Eyebrow>
          </SlideIn>

          <div style={{ display: "flex", gap: 56, marginTop: 16 }}>
            {/* left: identity */}
            <SlideIn
              delay={10}
              from="left"
              distance={44}
              style={{ width: 440, flexShrink: 0, display: "flex", flexDirection: "column" }}
            >
              <div
                style={{
                  fontSize: 118,
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
                  fontSize: 54,
                  fontWeight: 800,
                  color: COLORS.white,
                  lineHeight: 1.08,
                  marginTop: 16,
                }}
              >
                {role.key}
              </div>
              <div
                style={{
                  fontSize: 24,
                  lineHeight: 1.45,
                  color: accent,
                  fontWeight: 600,
                  marginTop: 16,
                }}
              >
                {role.who}
              </div>

              {role.boundary && (
                <SlideIn delay={168} from="up" distance={22}>
                  <div
                    style={{
                      marginTop: 28,
                      background: "rgba(90,17,19,0.30)",
                      border: "1px solid rgba(240,195,197,0.35)",
                      borderRadius: LAYOUT.radius,
                      padding: "18px 20px",
                      fontSize: 18.5,
                      lineHeight: 1.5,
                      color: SURFACE.text,
                    }}
                  >
                    <b style={{ color: "#f0c3c5", fontWeight: 700 }}>
                      A deliberate limit:
                    </b>{" "}
                    {role.boundary}
                  </div>
                </SlideIn>
              )}
            </SlideIn>

            {/* divider */}
            <div
              style={{
                width: 1,
                background: SURFACE.hairlineSoft,
                margin: "8px 0",
              }}
            />

            {/* right: functions arrive one by one under the narration */}
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
              }}
            >
              {role.functions.map((fn, i) => (
                <SlideIn
                  key={fn}
                  delay={40 + i * 22}
                  from="left"
                  distance={36}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 20,
                      padding: i === 0 ? "13px 0 15px" : "15px 0",
                      borderTop:
                        i === 0 ? "none" : `1px solid ${SURFACE.hairlineSoft}`,
                    }}
                  >
                    <PopIn delay={42 + i * 22}>
                      <span
                        style={{
                          fontSize: 19,
                          fontWeight: 700,
                          color: COLORS.accent,
                          fontVariantNumeric: "tabular-nums",
                          width: 34,
                          display: "inline-block",
                        }}
                      >
                        {String(i + 1).padStart(2, "0")}
                      </span>
                    </PopIn>
                    <span
                      style={{
                        fontSize: 24.5,
                        lineHeight: 1.45,
                        color: SURFACE.text,
                        fontWeight: 500,
                      }}
                    >
                      {fn}
                    </span>
                  </div>
                </SlideIn>
              ))}
            </div>
          </div>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
