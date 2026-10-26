import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  CheckRow,
  Glyph,
} from "../components/Ui.jsx";
import { ROLES } from "../content.js";

const ACCENT = {
  yellow: COLORS.accent,
  green: "#7ed063",
  maroon: "#e09a9c",
};

const ROLE_ICONS = ["users", "folder", "check", "shield", "shield", "sign", "lock"];

export const RoleDetailScene = ({ roleIndex, sceneIndex }) => {
  const role = ROLES[roleIndex];
  const accent = ACCENT[role.accent];

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={sceneIndex} total={19}>
        <AbsoluteFill style={{ padding: "150px 120px 100px" }}>
          <Rise delay={4}>
            <Eyebrow>Role {roleIndex + 1} of 7 — what they can do</Eyebrow>
          </Rise>

          <div style={{ display: "flex", gap: 48, marginTop: 10 }}>
            {/* left: identity */}
            <Rise delay={10} style={{ width: 520, flexShrink: 0 }}>
              <div
                style={{
                  width: 110,
                  height: 110,
                  borderRadius: 26,
                  background: "rgba(245,229,135,0.12)",
                  border: "1.5px solid rgba(245,229,135,0.4)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 28,
                }}
              >
                <Glyph name={ROLE_ICONS[roleIndex]} size={52} />
              </div>
              <div style={{ fontSize: 62, fontWeight: 800, color: COLORS.white, lineHeight: 1.05 }}>
                {role.key}
              </div>
              <div style={{ fontSize: 27, lineHeight: 1.45, color: accent, fontWeight: 600, marginTop: 20 }}>
                {role.who}
              </div>

              {role.boundary && (
                <div
                  style={{
                    marginTop: 30,
                    background: "rgba(90,17,19,0.35)",
                    border: "1.5px solid rgba(240,195,197,0.4)",
                    borderRadius: 18,
                    padding: "20px 22px",
                    fontSize: 20,
                    lineHeight: 1.45,
                    color: "rgba(255,255,255,0.85)",
                  }}
                >
                  <b style={{ color: "#f0c3c5" }}>A deliberate limit:</b> {role.boundary}
                </div>
              )}
            </Rise>

            {/* right: functions */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 22 }}>
              {role.functions.map((fn, i) => (
                <CheckRow key={fn} delay={24 + i * 14} size={26}>
                  {fn}
                </CheckRow>
              ))}
            </div>
          </div>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
