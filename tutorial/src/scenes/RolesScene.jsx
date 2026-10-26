import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { Rise, SceneShell, Eyebrow, Heading, Body, FadeIn } from "../components/Ui.jsx";
import { ROLES } from "../content.js";

const TINT = {
  yellow: { dot: COLORS.accent, text: COLORS.accent },
  green: { dot: "#7ed063", text: "#b6e6a4" },
  maroon: { dot: "#e09a9c", text: "#eec3c5" },
};

export const RolesScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={3}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={6}>
          <Eyebrow>Who uses NExUS?</Eyebrow>
        </Rise>
        <Rise delay={12}>
          <Heading size={48}>
            Seven roles, each with its{" "}
            <span style={{ color: COLORS.accent }}>own dashboard</span>
          </Heading>
        </Rise>
        <Rise delay={20}>
          <Body style={{ marginTop: 16, maxWidth: 1450, fontSize: 27 }}>
            After login you land on the dashboard built for your role. Here is
            who everyone is — the next seven scenes show exactly what each one
            can do.
          </Body>
        </Rise>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(12, 1fr)",
            gap: LAYOUT.gutter,
            marginTop: 40,
          }}
        >
          {ROLES.map((role, i) => {
            const tint = TINT[role.accent];
            // Row 1: four cards (3 grid columns each). Row 2: three wider
            // cards (4 grid columns each), flush to the same outer edges.
            const span = i < 4 ? 3 : 4;
            const col = i < 4 ? i * 3 + 1 : (i - 4) * 4 + 1;
            return (
              <FadeIn
                key={role.key}
                delay={28 + i * 6}
                style={{ gridColumn: `${col} / span ${span}` }}
              >
                <div
                  style={{
                    background: SURFACE.panel,
                    border: `1px solid ${SURFACE.hairlineSoft}`,
                    borderRadius: LAYOUT.radius,
                    padding: "24px 26px",
                    height: 182,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 18,
                        fontWeight: 700,
                        color: SURFACE.textFaint,
                        fontVariantNumeric: "tabular-nums",
                        letterSpacing: 1.5,
                      }}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: tint.dot,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      fontSize: 27,
                      fontWeight: 800,
                      color: COLORS.white,
                      marginTop: 14,
                    }}
                  >
                    {role.key}
                  </div>
                  <div
                    style={{
                      marginTop: "auto",
                      paddingTop: 12,
                      fontSize: 19,
                      lineHeight: 1.42,
                      color: tint.text,
                      fontWeight: 500,
                    }}
                  >
                    {role.who}
                  </div>
                </div>
              </FadeIn>
            );
          })}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
