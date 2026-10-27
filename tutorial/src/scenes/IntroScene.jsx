import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import { LogoBadge, Wordmark } from "../components/BrandMark.jsx";
import { SlideIn, PopIn, AnimatedNumber, easeOut } from "../components/Motion.jsx";

const STATS = [
  { figure: 7, label: "User roles, each with its own dashboard" },
  { figure: 20, label: "Guided sections in the proposal form" },
  { figure: 1, label: "Record that follows the work from idea to close" },
];

export const IntroScene = () => {
  const frame = useCurrentFrame();
  const lineGrow = interpolate(frame, [26, 56], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  const chipOpacity = interpolate(frame, [40, 56], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
        }}
      >
        <PopIn delay={2}>
          <LogoBadge size={148} animate />
        </PopIn>

        <div style={{ height: 30 }} />

        <SlideIn delay={14} from="up" distance={26}>
          <Wordmark fontSize={82} tagline />
        </SlideIn>

        <div
          style={{
            opacity: chipOpacity,
            marginTop: 14,
            fontSize: 21,
            fontWeight: 600,
            letterSpacing: 1.5,
            color: COLORS.accent,
            background: "rgba(245,229,135,0.10)",
            border: "1px solid rgba(245,229,135,0.35)",
            borderRadius: 999,
            padding: "8px 22px",
          }}
        >
          pronounced “nexus”
        </div>

        <div
          style={{
            height: 3,
            width: 360 * lineGrow,
            borderRadius: 2,
            background: COLORS.accent,
            margin: "26px 0 24px",
          }}
        />

        <SlideIn delay={60} from="up" distance={22}>
          <div
            style={{
              fontSize: 50,
              fontWeight: 800,
              color: COLORS.white,
              letterSpacing: -0.6,
              textAlign: "center",
            }}
          >
            A Plain-Language Guide to NExUS
          </div>
        </SlideIn>
        <SlideIn delay={74} from="up" distance={18}>
          <div
            style={{
              fontSize: 27,
              color: SURFACE.textSoft,
              marginTop: 16,
              textAlign: "center",
              maxWidth: 1140,
              lineHeight: 1.5,
            }}
          >
            What it does, what every role can do, and how a proposal travels
            from an idea to a finished, documented activity
          </div>
        </SlideIn>

        <div style={{ height: 58 }} />

        <div style={{ display: "flex", alignItems: "stretch" }}>
          {STATS.map((s, i) => (
            <React.Fragment key={s.label}>
              {i > 0 && (
                <div
                  style={{
                    width: 1,
                    background: "rgba(255,255,255,0.22)",
                    margin: "6px 44px",
                  }}
                />
              )}
              <SlideIn
                delay={100 + i * 12}
                from="up"
                distance={24}
                style={{
                  width: 360,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  textAlign: "center",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    fontSize: 52,
                    fontWeight: 800,
                    color: COLORS.accent,
                    lineHeight: 1,
                  }}
                >
                  <AnimatedNumber value={s.figure} delay={104 + i * 12} duration={38} />
                </div>
                <div
                  style={{
                    fontSize: 20,
                    lineHeight: 1.45,
                    color: SURFACE.textSoft,
                  }}
                >
                  {s.label}
                </div>
              </SlideIn>
            </React.Fragment>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
