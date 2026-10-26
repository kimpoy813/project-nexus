import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { COLORS, LAYOUT } from "../theme.js";
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

const easeOut = Easing.out(Easing.cubic);

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
    <div
      style={{
        color: COLORS.white,
        fontWeight: 800,
        fontSize: 23,
        letterSpacing: -0.4,
      }}
    >
      NExUS
    </div>
  </div>
);

const KpiCard = ({ label, value, delay }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return (
    <div
      style={{
        flex: 1,
        background: COLORS.white,
        border: `1px solid ${COLORS.line}`,
        borderRadius: 14,
        padding: "22px 24px",
        opacity: t,
        transform: `translateY(${(1 - t) * 12}px)`,
      }}
    >
      <div style={{ fontSize: 19, color: COLORS.muted, fontWeight: 600 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 44,
          fontWeight: 800,
          color: COLORS.ink,
          marginTop: 4,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
    </div>
  );
};

const ProposalRow = ({ title, meta, badge, tone, delay }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return (
    <div
      style={{
        background: COLORS.white,
        border: `1px solid ${COLORS.line}`,
        borderRadius: 14,
        padding: "20px 26px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        opacity: t,
      }}
    >
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.ink }}>
          {title}
        </div>
        <div style={{ fontSize: 18, color: COLORS.muted, marginTop: 3 }}>
          {meta}
        </div>
      </div>
      <StatusBadge label={badge} tone={tone} />
    </div>
  );
};

export const DashboardScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={11}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={4}>
          <Eyebrow>Step 1 — Sign in</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={48}>
            Your dashboard shows every proposal you own
          </Heading>
        </Rise>

        <Rise delay={20} style={{ marginTop: 36 }}>
          <BrowserChrome url="nexus.example/dashboard/faculty/">
            {/* app top nav */}
            <div
              style={{
                height: 64,
                background: COLORS.primary,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0 30px",
              }}
            >
              <MiniBrand />
              <div
                style={{
                  display: "flex",
                  gap: 30,
                  color: "rgba(255,255,255,0.75)",
                  fontSize: 19,
                  fontWeight: 600,
                }}
              >
                <span style={{ color: COLORS.white }}>Dashboard</span>
                <span>Proposals</span>
                <span>Documents</span>
                <span>Reports</span>
              </div>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: "50%",
                  background: COLORS.accent,
                }}
              />
            </div>

            <div style={{ display: "flex", minHeight: 540 }}>
              {/* side rail */}
              <div
                style={{
                  width: 240,
                  background: "#eef2e7",
                  borderRight: `1px solid ${COLORS.line}`,
                  padding: "24px 18px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {[
                  "Dashboard",
                  "My Proposals",
                  "MOA Tracker",
                  "Implementation",
                  "Templates",
                  "Profile",
                ].map((item, i) => (
                  <div
                    key={item}
                    style={{
                      fontSize: 19,
                      fontWeight: i === 0 ? 700 : 500,
                      color: i === 0 ? COLORS.primary : COLORS.muted,
                      background: i === 0 ? "#dfead3" : "transparent",
                      borderRadius: 10,
                      padding: "12px 16px",
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>

              {/* main column */}
              <div style={{ flex: 1, padding: "28px 32px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div
                    style={{ fontSize: 30, fontWeight: 800, color: COLORS.ink }}
                  >
                    Faculty Dashboard
                  </div>
                  <div
                    style={{
                      background: COLORS.primary,
                      color: COLORS.white,
                      fontSize: 21,
                      fontWeight: 700,
                      borderRadius: 10,
                      padding: "13px 24px",
                    }}
                  >
                    + New Proposal
                  </div>
                </div>

                <div style={{ display: "flex", gap: 18, marginTop: 22 }}>
                  <KpiCard label="Drafts" value={3} delay={36} />
                  <KpiCard label="In Review" value={2} delay={44} />
                  <KpiCard label="Approved" value={1} delay={52} />
                  <div
                    style={{
                      background: COLORS.white,
                      border: `1px solid ${COLORS.line}`,
                      borderRadius: 14,
                      padding: "18px 24px",
                      display: "flex",
                      alignItems: "center",
                      gap: 18,
                    }}
                  >
                    <Ring value={0.64} delay={60} label="overall" />
                    <div>
                      <div
                        style={{
                          fontSize: 18,
                          color: COLORS.muted,
                          fontWeight: 600,
                        }}
                      >
                        Active proposal
                      </div>
                      <div
                        style={{
                          fontSize: 20,
                          fontWeight: 700,
                          color: COLORS.ink,
                          marginTop: 4,
                          maxWidth: 280,
                          lineHeight: 1.3,
                        }}
                      >
                        Community Tree-Growing Workshop
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                    marginTop: 20,
                  }}
                >
                  <ProposalRow
                    title="Digital Literacy for Barangay Staff"
                    meta="Request-based · Updated 2 days ago"
                    badge="In Review"
                    tone="yellow"
                    delay={72}
                  />
                  <ProposalRow
                    title="Coastal Clean-Up and Waste Segregation Drive"
                    meta="Community-based · Updated yesterday"
                    badge="For Revision"
                    tone="rose"
                    delay={82}
                  />
                </div>
              </div>
            </div>

            {/* cursor glides to New Proposal and clicks once, quietly */}
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
