import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { Rise, SceneShell, Eyebrow, Heading, Body } from "../components/Ui.jsx";
import { ROLES } from "../content.js";

const ACCENT = {
  yellow: { chip: "rgba(245,229,135,0.16)", border: "rgba(245,229,135,0.45)", text: COLORS.accent },
  green: { chip: "rgba(31,107,18,0.4)", border: COLORS.primaryLine, text: "#c9f0b3" },
  maroon: { chip: "rgba(90,17,19,0.5)", border: "rgba(240,195,197,0.35)", text: "#f0c3c5" },
};

export const RolesScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={3}>
      <AbsoluteFill style={{ padding: "132px 120px 70px" }}>
        <Rise delay={6}>
          <Eyebrow>Who uses NExUS?</Eyebrow>
        </Rise>
        <Rise delay={12}>
          <Heading size={48}>
            Seven roles, each with its <span style={{ color: COLORS.accent }}>own dashboard</span>
          </Heading>
        </Rise>
        <Rise delay={20}>
          <Body style={{ marginTop: 16, maxWidth: 1500, fontSize: 28 }}>
            After login you land on the dashboard built for your role. Here is who
            everyone is — the next seven scenes show exactly what each one can do.
          </Body>
        </Rise>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 18,
            marginTop: 34,
          }}
        >
          {ROLES.map((role, i) => {
            const a = ACCENT[role.accent];
            return (
              <Rise
                key={role.key}
                delay={30 + i * 9}
                style={{
                  // Center the lone seventh card across the two middle columns.
                  gridColumn: i === 6 ? "2 / 4" : undefined,
                }}
              >
                <div
                  style={{
                    background: a.chip,
                    border: `1.5px solid ${a.border}`,
                    borderRadius: 18,
                    padding: "20px 22px",
                    height: 178,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div style={{ fontSize: 28, fontWeight: 800, color: COLORS.white }}>
                    {role.key}
                  </div>
                  <div
                    style={{
                      marginTop: "auto",
                      paddingTop: 12,
                      fontSize: 19.5,
                      lineHeight: 1.4,
                      color: a.text,
                      fontWeight: 500,
                    }}
                  >
                    {role.who}
                  </div>
                </div>
              </Rise>
            );
          })}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
