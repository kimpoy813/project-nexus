import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { SceneShell, Eyebrow, Heading } from "../components/Ui.jsx";
import { SlideIn, DrawCheck } from "../components/Motion.jsx";
import { SAFETY_FEATURES } from "../content.js";

export const SecurityScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={17} total={19}>
      <AbsoluteFill
        style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
      >
        <SlideIn delay={4} from="up" distance={18}>
          <Eyebrow>Safe, tidy and easy to come back to</Eyebrow>
        </SlideIn>
        <SlideIn delay={10} from="up" distance={22}>
          <Heading size={46}>
            Safeguards built into{" "}
            <span style={{ color: COLORS.accent }}>every account</span>
          </Heading>
        </SlideIn>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 20,
            marginTop: 38,
          }}
        >
          {SAFETY_FEATURES.map((item, i) => {
            const row = Math.floor(i / 4);
            const delay = (row === 0 ? 22 : 88) + (i % 4) * 8;
            return (
              <SlideIn key={item.title} delay={delay} from="up" distance={26}>
                <div
                  style={{
                    background: SURFACE.panel,
                    border: `1px solid ${SURFACE.hairlineSoft}`,
                    borderRadius: LAYOUT.radius,
                    padding: "22px 22px 24px",
                    height: 236,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div
                    style={{
                      width: 46,
                      height: 46,
                      borderRadius: 12,
                      background: "rgba(245,229,135,0.12)",
                      border: "1px solid rgba(245,229,135,0.3)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: 16,
                    }}
                  >
                    <DrawCheck delay={delay + 14} size={24} />
                  </div>
                  <div
                    style={{
                      fontSize: 21.5,
                      fontWeight: 800,
                      color: COLORS.white,
                      marginBottom: 9,
                      lineHeight: 1.25,
                    }}
                  >
                    {item.title}
                  </div>
                  <div
                    style={{
                      fontSize: 17,
                      lineHeight: 1.45,
                      color: SURFACE.textSoft,
                    }}
                  >
                    {item.text}
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
