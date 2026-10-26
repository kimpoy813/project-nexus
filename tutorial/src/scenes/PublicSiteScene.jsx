import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Body,
  Glyph,
  Panel,
  FadeIn,
} from "../components/Ui.jsx";
import { CONTENT_BLOCKS, PUBLIC_PAGES } from "../content.js";

export const PublicSiteScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={16} total={19}>
      <AbsoluteFill
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={4}>
          <Eyebrow>The public website, edited without code</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={46}>
            Admins publish content by{" "}
            <span style={{ color: COLORS.accent }}>
              dragging blocks onto pages
            </span>
          </Heading>
        </Rise>

        {/* No fixed heights: panels stretch to the taller column, so the
            fourth page card can never cross the panel border. */}
        <div style={{ display: "flex", gap: 28, marginTop: 34, alignItems: "stretch" }}>
          {/* public pages */}
          <Rise delay={18} style={{ width: 480, flexShrink: 0 }}>
            <Panel style={{ height: "100%", padding: "28px 26px" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 18,
                }}
              >
                <Glyph name="globe" size={30} />
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 800,
                    color: COLORS.white,
                  }}
                >
                  Four public pages
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {PUBLIC_PAGES.map((p, i) => (
                  <div
                    key={p.name}
                    style={{
                      background: SURFACE.panelStrong,
                      border: `1px solid ${SURFACE.hairlineSoft}`,
                      borderRadius: 14,
                      padding: "15px 18px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 22,
                        fontWeight: 800,
                        color: COLORS.accent,
                      }}
                    >
                      {String(i + 1).padStart(2, "0")} · {p.name}
                    </div>
                    <div
                      style={{
                        fontSize: 18,
                        lineHeight: 1.42,
                        color: SURFACE.textSoft,
                        marginTop: 5,
                      }}
                    >
                      {p.text}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </Rise>

          {/* content blocks */}
          <Rise delay={28} style={{ flex: 1, display: "flex" }}>
            <Panel
              style={{
                height: "100%",
                flex: 1,
                padding: "28px 26px",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 18,
                }}
              >
                <Glyph name="folder" size={30} />
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 800,
                    color: COLORS.white,
                  }}
                >
                  Reusable building blocks
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gridAutoRows: "1fr",
                  gap: 12,
                  flex: 1,
                }}
              >
                {CONTENT_BLOCKS.map((b) => (
                  <div
                    key={b.name}
                    style={{
                      background: SURFACE.panelStrong,
                      border: `1px solid ${SURFACE.hairlineSoft}`,
                      borderRadius: 14,
                      padding: "15px 18px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 19.5,
                        fontWeight: 800,
                        color: COLORS.white,
                      }}
                    >
                      {b.name}
                    </div>
                    <div
                      style={{
                        fontSize: 16.5,
                        lineHeight: 1.42,
                        color: SURFACE.textSoft,
                        marginTop: 5,
                      }}
                    >
                      {b.text}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </Rise>
        </div>

        <FadeIn delay={70}>
          <Body style={{ marginTop: 28, fontSize: 23 }}>
            Edit once and it updates everywhere the block appears — no
            developer, no redeploy, with a full change log of who edited what.
          </Body>
        </FadeIn>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
