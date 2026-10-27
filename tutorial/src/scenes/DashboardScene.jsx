import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { COLORS, LAYOUT } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  SceneShell,
  Eyebrow,
  Heading,
  BrowserChrome,
  Ring,
  Cursor,
  StatusBadge,
} from "../components/Ui.jsx";
import { SlideIn, AnimatedNumber, easeOut } from "../components/Motion.jsx";
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

const KpiCard = ({ label, value, delay }) => (
  <SlideIn delay={delay} from="up" distance={22} style={{ flex: 1 }}>
    <div
      style={{
        background: COLORS.white,
        border: `1px solid ${COLORS.line}`,
        borderRadius: 14,
        padding: "22px 24px",
        height: "100%",
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
        }}
      >
        <AnimatedNumber value={value} delay={delay + 6} duration={30} />
      </div>
    </div>
  </SlideIn>
);

const ProposalRow = ({ title, meta, badge, tone, delay, from = "right" }) => (
  <SlideIn delay={delay} from={from} distance={44}>
    <div
      style={{
        background: COLORS.white,
        border: `1px solid ${COLORS.line}`,
        borderRadius: 14,
        padding: "18px 26px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div>
        <div style={{ fontSize: 21, fontWeight: 700, color: COLORS.ink }}>
          {title}
        </div>
        <div style={{ fontSize: 17.5, color: COLORS.muted, marginTop: 3 }}>
          {meta}
        </div>
      </div>
      <StatusBadge label={badge} tone={tone} />
    </div>
  </SlideIn>
);

export const DashboardScene = () => {
  const frame = useCurrentFrame();
  const barSlide = interpolate(frame, [14, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={11}>
        <AbsoluteFill
          style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
        >
          <SlideIn delay={4} from="up" distance={18}>
            <Eyebrow>Step 1 — Sign in</Eyebrow>
          </SlideIn>
          <SlideIn delay={10} from="up" distance={22}>
            <Heading size={46}>
              Your dashboard shows every proposal you own
            </Heading>
          </SlideIn>

          <SlideIn delay={18} from="up" distance={30} style={{ marginTop: 30 }}>
            <BrowserChrome url="nexus.example/dashboard/faculty/">
              {/* app top nav slides down */}
              <div
                style={{
                  height: 64,
                  background: COLORS.primary,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0 30px",
                  transform: `translateY(${(1 - barSlide) * -64}px)`,
                  opacity: barSlide,
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

              <div style={{ display: "flex", minHeight: 520 }}>
                {/* side rail slides in from the left */}
                <SlideIn delay={24} from="left" distance={70}>
                  <div
                    style={{
                      width: 240,
                      minHeight: 520,
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
                </SlideIn>

                {/* main column */}
                <div style={{ flex: 1, padding: "26px 30px" }}>
                  <SlideIn delay={32} from="up" distance={16}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 29,
                          fontWeight: 800,
                          color: COLORS.ink,
                        }}
                      >
                        Faculty Dashboard
                      </div>
                      <div
                        style={{
                          background: COLORS.primary,
                          color: COLORS.white,
                          fontSize: 20,
                          fontWeight: 700,
                          borderRadius: 10,
                          padding: "12px 22px",
                        }}
                      >
                        + New Proposal
                      </div>
                    </div>
                  </SlideIn>

                  <div style={{ display: "flex", gap: 16, marginTop: 20 }}>
                    <KpiCard label="Drafts" value={3} delay={42} />
                    <KpiCard label="In Review" value={2} delay={52} />
                    <KpiCard label="Approved" value={1} delay={62} />
                    <SlideIn delay={72} from="up" distance={22} style={{ flex: 1.35 }}>
                      <div
                        style={{
                          background: COLORS.white,
                          border: `1px solid ${COLORS.line}`,
                          borderRadius: 14,
                          padding: "16px 22px",
                          display: "flex",
                          alignItems: "center",
                          gap: 16,
                          height: "100%",
                        }}
                      >
                        <Ring value={0.64} delay={78} label="overall" size={128} stroke={13} />
                        <div>
                          <div
                            style={{
                              fontSize: 17,
                              color: COLORS.muted,
                              fontWeight: 600,
                            }}
                          >
                            Active proposal
                          </div>
                          <div
                            style={{
                              fontSize: 19,
                              fontWeight: 700,
                              color: COLORS.ink,
                              marginTop: 4,
                              maxWidth: 270,
                              lineHeight: 1.3,
                            }}
                          >
                            Community Tree-Growing Workshop
                          </div>
                        </div>
                      </div>
                    </SlideIn>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 11,
                      marginTop: 18,
                    }}
                  >
                    <ProposalRow
                      title="Digital Literacy for Barangay Staff"
                      meta="Request-based · Updated 2 days ago"
                      badge="In Review"
                      tone="yellow"
                      delay={104}
                    />
                    <ProposalRow
                      title="Coastal Clean-Up and Waste Segregation Drive"
                      meta="Community-based · Updated yesterday"
                      badge="For Revision"
                      tone="rose"
                      delay={120}
                    />
                  </div>
                </div>
              </div>

              {/* cursor glides in and clicks as the VO says "single click" */}
              <Cursor
                keyframes={[
                  { frame: 24, x: 280, y: 110 },
                  { frame: 90, x: 1160, y: 112 },
                  { frame: 148, x: 1218, y: 136, click: true },
                  { frame: 196, x: 1218, y: 136 },
                ]}
              />
            </BrowserChrome>
          </SlideIn>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
