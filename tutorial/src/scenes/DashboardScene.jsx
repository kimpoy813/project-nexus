import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  BrowserChrome,
  Ring,
  Cursor,
  StatusBadge,
} from "../components/Ui.jsx";
import { LogoRaw } from "../components/BrandMark.jsx";

const MiniBrand = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
    <div
      style={{
        width: 40,
        height: 40,
        borderRadius: 10,
        background: COLORS.white,
        padding: 5,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <LogoRaw size={30} />
    </div>
    <div style={{ color: COLORS.white, fontWeight: 800, fontSize: 23, letterSpacing: -0.4 }}>
      NExUS
    </div>
  </div>
);

const KpiCard = ({ label, value, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 16 } });
  return (
    <div
      style={{
        flex: 1,
        background: COLORS.white,
        border: `1px solid ${COLORS.line}`,
        borderRadius: 16,
        padding: "24px 26px",
        transform: `translateY(${(1 - s) * 24}px)`,
        opacity: s,
      }}
    >
      <div style={{ fontSize: 20, color: COLORS.muted, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 46, fontWeight: 800, color: COLORS.ink, marginTop: 6 }}>{value}</div>
    </div>
  );
};

export const DashboardScene = () => {
  const frame = useCurrentFrame();
  const btnPulse = spring({
    frame: frame - 95,
    fps: 30,
    config: { damping: 12, stiffness: 90 },
  });

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={11}>
        <AbsoluteFill style={{ padding: "130px 120px 90px" }}>
          <Rise delay={4}>
            <Eyebrow>Step 1 — Sign in</Eyebrow>
          </Rise>
          <Rise delay={10}>
            <Heading size={52}>Your dashboard shows every proposal you own</Heading>
          </Rise>

          <Rise delay={22} style={{ marginTop: 44 }}>
            <BrowserChrome url="nexus.example/dashboard/faculty/">
              {/* app top nav */}
              <div
                style={{
                  height: 66,
                  background: COLORS.primary,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0 30px",
                }}
              >
                <MiniBrand />
                <div style={{ display: "flex", gap: 30, color: "rgba(255,255,255,0.75)", fontSize: 20, fontWeight: 600 }}>
                  <span>Dashboard</span>
                  <span>Proposals</span>
                  <span>Documents</span>
                  <span>Reports</span>
                </div>
                <div style={{ width: 40, height: 40, borderRadius: "50%", background: COLORS.accent }} />
              </div>

              <div style={{ display: "flex", minHeight: 470 }}>
                {/* side rail */}
                <div
                  style={{
                    width: 250,
                    background: "#eef2e7",
                    borderRight: `1px solid ${COLORS.line}`,
                    padding: "26px 20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 14,
                  }}
                >
                  {["Dashboard", "My Proposals", "MOA Tracker", "Implementation", "Templates", "Profile"].map(
                    (item, i) => (
                      <div
                        key={item}
                        style={{
                          fontSize: 20,
                          fontWeight: i === 0 ? 700 : 500,
                          color: i === 0 ? COLORS.primary : COLORS.muted,
                          background: i === 0 ? "#dfead3" : "transparent",
                          borderRadius: 12,
                          padding: "13px 16px",
                        }}
                      >
                        {item}
                      </div>
                    )
                  )}
                </div>

                {/* main column */}
                <div style={{ flex: 1, padding: "30px 34px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ fontSize: 32, fontWeight: 800, color: COLORS.ink }}>
                      Faculty Dashboard
                    </div>
                    <div
                      style={{
                        background: COLORS.primary,
                        color: COLORS.white,
                        fontSize: 22,
                        fontWeight: 700,
                        borderRadius: 12,
                        padding: "14px 26px",
                        transform: `scale(${1 + btnPulse * 0.08})`,
                        boxShadow: btnPulse ? `0 0 0 ${8 + btnPulse * 14}px rgba(16,59,7,0.18)` : "none",
                      }}
                    >
                      + New Proposal
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 20, marginTop: 26 }}>
                    <KpiCard label="Drafts" value={3} delay={40} />
                    <KpiCard label="In Review" value={2} delay={50} />
                    <KpiCard label="Approved" value={1} delay={60} />
                    <div
                      style={{
                        background: COLORS.white,
                        border: `1px solid ${COLORS.line}`,
                        borderRadius: 16,
                        padding: "20px 26px",
                        display: "flex",
                        alignItems: "center",
                        gap: 20,
                      }}
                    >
                      <Ring value={0.64} delay={70} label="overall" />
                      <div>
                        <div style={{ fontSize: 20, color: COLORS.muted, fontWeight: 600 }}>
                          Active proposal
                        </div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.ink, marginTop: 4 }}>
                          Community Tree-Growing Workshop
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* proposal row */}
                  <div
                    style={{
                      marginTop: 26,
                      background: COLORS.white,
                      border: `1px solid ${COLORS.line}`,
                      borderRadius: 16,
                      padding: "22px 28px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 23, fontWeight: 700, color: COLORS.ink }}>
                        Digital Literacy for Barangay Staff
                      </div>
                      <div style={{ fontSize: 19, color: COLORS.muted, marginTop: 4 }}>
                        Request-based · Updated 2 days ago
                      </div>
                    </div>
                    <StatusBadge label="In Review" tone="yellow" />
                  </div>
                </div>
              </div>

              {/* cursor clicks New Proposal */}
              <Cursor
                keyframes={[
                  { frame: 30, x: 300, y: 120 },
                  { frame: 75, x: 1180, y: 115 },
                  { frame: 95, x: 1230, y: 140, click: true },
                  { frame: 165, x: 1230, y: 140 },
                ]}
              />
            </BrowserChrome>
          </Rise>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
