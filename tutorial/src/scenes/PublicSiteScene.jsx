import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  Body,
  Glyph,
  GlassCard,
} from "../components/Ui.jsx";
import { CONTENT_BLOCKS, PUBLIC_PAGES } from "../content.js";

export const PublicSiteScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={16} total={19}>
      <AbsoluteFill style={{ padding: "148px 120px 95px" }}>
        <Rise delay={4}>
          <Eyebrow>The public website, edited without code</Eyebrow>
        </Rise>
        <Rise delay={10}>
          <Heading size={48}>
            Admins publish content by <span style={{ color: COLORS.accent }}>dragging blocks onto pages</span>
          </Heading>
        </Rise>

        <div style={{ display: "flex", gap: 30, marginTop: 40 }}>
          {/* public pages */}
          <Rise delay={20} style={{ width: 480, flexShrink: 0 }}>
            <GlassCard style={{ height: 560 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 22 }}>
                <Glyph name="globe" size={34} />
                <div style={{ fontSize: 28, fontWeight: 800, color: COLORS.white }}>
                  Four public pages
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {PUBLIC_PAGES.map((p, i) => (
                  <div
                    key={p.name}
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: `1.5px solid ${COLORS.primaryLine}`,
                      borderRadius: 16,
                      padding: "18px 20px",
                    }}
                  >
                    <div style={{ fontSize: 24, fontWeight: 800, color: COLORS.accent }}>
                      {i + 1}. {p.name}
                    </div>
                    <div style={{ fontSize: 19, lineHeight: 1.4, color: "rgba(255,255,255,0.72)", marginTop: 6 }}>
                      {p.text}
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </Rise>

          {/* content blocks */}
          <Rise delay={32} style={{ flex: 1 }}>
            <GlassCard style={{ height: 560 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 22 }}>
                <Glyph name="folder" size={34} />
                <div style={{ fontSize: 28, fontWeight: 800, color: COLORS.white }}>
                  Reusable building blocks
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {CONTENT_BLOCKS.map((b, i) => (
                  <div
                    key={b.name}
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: `1.5px solid ${COLORS.primaryLine}`,
                      borderRadius: 16,
                      padding: "18px 20px",
                    }}
                  >
                    <div style={{ fontSize: 21.5, fontWeight: 800, color: COLORS.white }}>
                      {b.name}
                    </div>
                    <div style={{ fontSize: 17.5, lineHeight: 1.4, color: "rgba(255,255,255,0.68)", marginTop: 6 }}>
                      {b.text}
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </Rise>
        </div>

        <Rise delay={95}>
          <Body style={{ marginTop: 32, fontSize: 24 }}>
            Edit once and it updates everywhere the block appears — no developer,
            no redeploy, with a full change log of who edited what.
          </Body>
        </Rise>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
