import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { SceneShell, Eyebrow, Heading, Body } from "../components/Ui.jsx";
import { SlideIn, PopIn } from "../components/Motion.jsx";
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
        style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
      >
        <SlideIn delay={6} from="up">
          <Eyebrow>Who uses NExUS?</Eyebrow>
        </SlideIn>
        <SlideIn delay={12} from="up" distance={24}>
          <Heading size={46}>
            Seven roles, each with its{" "}
            <span style={{ color: COLORS.accent }}>own dashboard</span>
          </Heading>
        </SlideIn>
        <SlideIn delay={20} from="up" distance={18}>
          <Body style={{ marginTop: 16, maxWidth: 1450, fontSize: 26 }}>
            After login you land on the dashboard built for your role. Here is
            who everyone is — the next seven scenes show exactly what each one
            can do.
          </Body>
        </SlideIn>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(12, 1fr)",
            gap: LAYOUT.gutter,
            marginTop: 38,
          }}
        >
          {ROLES.map((role, i) => {
            const tint = TINT[role.accent];
            const span = i < 4 ? 3 : 4;
            const col = i < 4 ? i * 3 + 1 : (i - 4) * 4 + 1;
            // Row 1 begins at frame 30, row 2 at 92.
            const delay = (i < 4 ? 30 : 92) + (i % 4) * 9;
            return (
              <SlideIn
                key={role.key}
                delay={delay}
                from={i < 4 ? "left" : "right"}
                distance={40}
                style={{ gridColumn: `${col} / span ${span}` }}
              >
                <div
                  style={{
                    background: SURFACE.panel,
                    border: `1px solid ${SURFACE.hairlineSoft}`,
                    borderRadius: LAYOUT.radius,
                    padding: "24px 26px",
                    height: 176,
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
                        fontSize: 17,
                        fontWeight: 700,
                        color: SURFACE.textFaint,
                        fontVariantNumeric: "tabular-nums",
                        letterSpacing: 1.5,
                      }}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <PopIn delay={delay + 12}>
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          background: tint.dot,
                          display: "block",
                        }}
                      />
                    </PopIn>
                  </div>
                  <div
                    style={{
                      fontSize: 26,
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
                      fontSize: 18.5,
                      lineHeight: 1.42,
                      color: tint.text,
                      fontWeight: 500,
                    }}
                  >
                    {role.who}
                  </div>
                </div>
              </SlideIn>
            );
          })}
        </div>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
