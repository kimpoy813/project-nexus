import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { LogoBadge, Wordmark } from "../components/BrandMark.jsx";
import {
  SlideIn,
  PopIn,
  DrawPath,
  FlowToken,
  DrawCheck,
} from "../components/Motion.jsx";
import { JOURNEY_STEPS } from "../content.js";

const INSET = 44;
const nodeX = (i) =>
  INSET + (i * (LAYOUT.contentWidth - INSET * 2)) / (JOURNEY_STEPS.length - 1);
const ACTIVATE_AT = JOURNEY_STEPS.map((_, i) => 30 + i * 12);

export const OutroScene = () => (
  <AbsoluteFill>
    <Background />
    <AbsoluteFill
      style={{
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        padding: `0 ${LAYOUT.marginX}px`,
      }}
    >
      <PopIn delay={2}>
        <LogoBadge size={112} animate />
      </PopIn>
      <div style={{ height: 20 }} />
      <SlideIn delay={12} from="up" distance={20}>
        <Wordmark fontSize={54} tagline />
      </SlideIn>

      {/* the whole journey, one line */}
      <div
        style={{
          position: "relative",
          width: LAYOUT.contentWidth,
          height: 200,
          marginTop: 56,
        }}
      >
        <svg
          width={LAYOUT.contentWidth}
          height={6}
          style={{ position: "absolute", top: 26, left: 0, overflow: "visible" }}
        >
          <line
            x1={INSET}
            y1={3}
            x2={LAYOUT.contentWidth - INSET}
            y2={3}
            stroke="rgba(255,255,255,0.12)"
            strokeWidth={2}
          />
          <DrawPath
            d={`M${INSET} 3 H${LAYOUT.contentWidth - INSET}`}
            length={LAYOUT.contentWidth - INSET * 2}
            delay={24}
            duration={92}
            stroke={COLORS.accent}
            strokeWidth={2.5}
          />
        </svg>
        <FlowToken
          size={18}
          fadeAfterLast={10}
          keyframes={ACTIVATE_AT.map((f, i) => ({ frame: f + 2, x: nodeX(i), y: 29 }))}
        />
        {JOURNEY_STEPS.map((step, i) => (
          <div
            key={step.title}
            style={{
              position: "absolute",
              left: nodeX(i),
              top: 0,
              transform: "translateX(-50%)",
              width: 188,
              textAlign: "center",
            }}
          >
            <PopIn delay={ACTIVATE_AT[i]}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  margin: "0 auto",
                  background: COLORS.accent,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <DrawCheck delay={ACTIVATE_AT[i] + 5} size={24} color={COLORS.primary} />
              </div>
            </PopIn>
            <div
              style={{
                marginTop: 12,
                fontSize: 19,
                fontWeight: 800,
                color: COLORS.white,
              }}
            >
              {step.title}
            </div>
            <div
              style={{
                marginTop: 5,
                fontSize: 14.5,
                lineHeight: 1.35,
                color: SURFACE.textSoft,
              }}
            >
              {step.text}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 22, marginTop: 44 }}>
        <SlideIn delay={132} from="up" distance={22}>
          <div
            style={{
              background: COLORS.accent,
              color: COLORS.primary,
              fontSize: 23,
              fontWeight: 800,
              borderRadius: 999,
              padding: "16px 38px",
            }}
          >
            Sign in and open your dashboard
          </div>
        </SlideIn>
        <SlideIn delay={144} from="up" distance={22}>
          <div
            style={{
              background: "transparent",
              color: COLORS.white,
              fontSize: 23,
              fontWeight: 700,
              borderRadius: 999,
              padding: "16px 38px",
              border: `1.5px solid rgba(255,255,255,0.4)`,
            }}
          >
            Visit the public site
          </div>
        </SlideIn>
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);
