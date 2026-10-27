import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, LAYOUT } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  SceneShell,
  Eyebrow,
  Heading,
  BrowserChrome,
} from "../components/Ui.jsx";
import { SlideIn, PopIn, easeOut } from "../components/Motion.jsx";
import { PUBLIC_PAGES, CONTENT_BLOCKS } from "../content.js";

const FLY_AT = [152, 168, 184, 200];

// Geometry inside the browser content area (excludes the 60px chrome bar).
const PALETTE_X = 954;
const SLOT_CENTERS = [
  { x: 248, y: 256 },
  { x: 710, y: 256 },
  { x: 248, y: 410 },
  { x: 710, y: 410 },
];
const PALETTE_STARTS = [232, 276, 320, 364];

// One content block chip that glides from the palette into a page slot,
// dissolving as the slot's own content pops in (FLY_AT + 18).
const FlyingBlock = ({ name, i }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - FLY_AT[i], [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  const target = SLOT_CENTERS[i];
  const startX = PALETTE_X + 40;
  const startY = PALETTE_STARTS[i] + 18;
  const x = startX + (target.x - startX) * t;
  const y = startY + (target.y - startY) * t - Math.sin(t * Math.PI) * 26;
  const scale = 1 - 0.15 * t;
  const opacity =
    frame < FLY_AT[i]
      ? 0
      : interpolate(t, [0, 0.8, 1], [1, 1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        background: COLORS.primary,
        color: COLORS.white,
        fontSize: 15,
        fontWeight: 700,
        borderRadius: 9,
        padding: "10px 16px",
        opacity,
        zIndex: 8,
        whiteSpace: "nowrap",
        boxShadow: "0 6px 18px rgba(0,0,0,0.25)",
      }}
    >
      {name}
    </div>
  );
};

export const PublicSiteScene = () => {
  const frame = useCurrentFrame();
  const blocks = CONTENT_BLOCKS.slice(0, 4);

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={16} total={19}>
        <AbsoluteFill
          style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
        >
          <SlideIn delay={4} from="up" distance={18}>
            <Eyebrow>The public website, edited without code</Eyebrow>
          </SlideIn>
          <SlideIn delay={10} from="up" distance={22}>
            <Heading size={44}>
              Pages the public sees,{" "}
              <span style={{ color: COLORS.accent }}>built inside NExUS</span>
            </Heading>
          </SlideIn>

          <div style={{ display: "flex", gap: 30, marginTop: 30 }}>
            {/* left: the four public pages */}
            <div
              style={{
                width: 400,
                flexShrink: 0,
                display: "flex",
                flexDirection: "column",
                gap: 14,
              }}
            >
              {PUBLIC_PAGES.map((page, i) => (
                <SlideIn
                  key={page.name}
                  delay={26 + i * 14}
                  from="left"
                  distance={44}
                >
                  <div
                    style={{
                      background: "rgba(255,255,255,0.045)",
                      border: `1px solid rgba(255,255,255,0.10)`,
                      borderRadius: LAYOUT.radius,
                      padding: "18px 22px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 23,
                        fontWeight: 800,
                        color: COLORS.white,
                        marginBottom: 5,
                      }}
                    >
                      {page.name}
                    </div>
                    <div
                      style={{
                        fontSize: 17.5,
                        lineHeight: 1.4,
                        color: "rgba(255,255,255,0.62)",
                      }}
                    >
                      {page.text}
                    </div>
                  </div>
                </SlideIn>
              ))}
            </div>

            {/* right: browser mock with blocks flying in */}
            <SlideIn
              delay={36}
              from="up"
              distance={26}
              style={{ flex: 1, minWidth: 0 }}
            >
              <BrowserChrome
                url="nexus.example/public-site/"
                style={{ width: "100%" }}
              >
                <div
                  style={{
                    position: "relative",
                    minHeight: 524,
                    background: COLORS.paper,
                  }}
                >
                  {/* mini site nav + hero */}
                  <div
                    style={{
                      background: COLORS.primary,
                      height: 58,
                      display: "flex",
                      alignItems: "center",
                      padding: "0 26px",
                      color: COLORS.white,
                      fontWeight: 800,
                      fontSize: 20,
                      gap: 26,
                    }}
                  >
                    NExUS Public Site
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 16,
                        fontWeight: 600,
                        opacity: 0.75,
                      }}
                    >
                      Home · Services · Reports · Achievements
                    </span>
                  </div>
                  <div
                    style={{
                      margin: "22px 26px 0",
                      height: 86,
                      borderRadius: 14,
                      background: "linear-gradient(120deg, #dfead3, #eef2e7)",
                      display: "flex",
                      alignItems: "center",
                      padding: "0 28px",
                      fontSize: 24,
                      fontWeight: 800,
                      color: COLORS.primary,
                    }}
                  >
                    Extension thrusts and priorities
                  </div>

                  <div
                    style={{
                      display: "flex",
                      gap: 20,
                      padding: "22px 26px 26px",
                    }}
                  >
                    {/* destination slots */}
                    <div
                      style={{
                        flex: 1,
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 18,
                      }}
                    >
                      {blocks.map((block, i) => {
                        const filled = frame >= FLY_AT[i] + 18;
                        return (
                          <div
                            key={block.name}
                            style={{
                              height: 136,
                              borderRadius: 14,
                              border: `2px dashed ${
                                filled ? "transparent" : COLORS.line
                              }`,
                              background: filled ? COLORS.white : "transparent",
                              display: "flex",
                              flexDirection: "column",
                              justifyContent: "center",
                              padding: "0 22px",
                              boxShadow: filled
                                ? "0 4px 14px rgba(0,0,0,0.08)"
                                : "none",
                            }}
                          >
                            {filled && (
                              <PopIn delay={FLY_AT[i] + 18}>
                                <div
                                  style={{
                                    fontSize: 18,
                                    fontWeight: 800,
                                    color: COLORS.ink,
                                    marginBottom: 5,
                                  }}
                                >
                                  {block.name}
                                </div>
                                <div
                                  style={{
                                    fontSize: 14.5,
                                    color: COLORS.muted,
                                    lineHeight: 1.35,
                                  }}
                                >
                                  {block.text}
                                </div>
                              </PopIn>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* palette in its own reserved column */}
                    <div
                      style={{
                        width: 270,
                        flexShrink: 0,
                        background: COLORS.white,
                        border: `1px solid ${COLORS.line}`,
                        borderRadius: 14,
                        padding: 14,
                        boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
                        alignSelf: "start",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 800,
                          color: COLORS.muted,
                          textTransform: "uppercase",
                          letterSpacing: 1.2,
                          marginBottom: 10,
                        }}
                      >
                        Block palette
                      </div>
                      {blocks.map((block, i) => (
                        <div
                          key={block.name}
                          style={{
                            fontSize: 15,
                            fontWeight: 600,
                            color: COLORS.primary,
                            background: "#eef2e7",
                            borderRadius: 9,
                            padding: "9px 13px",
                            marginBottom: i < 3 ? 8 : 0,
                            opacity:
                              frame >= FLY_AT[i] + 18 ? 0.25 : 1,
                          }}
                        >
                          {block.name}
                        </div>
                      ))}
                    </div>
                  </div>

                  {blocks.map((block, i) => (
                    <FlyingBlock key={block.name} name={block.name} i={i} />
                  ))}
                </div>
              </BrowserChrome>
            </SlideIn>
          </div>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
