import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, LAYOUT, SURFACE } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  SceneShell,
  Eyebrow,
  Heading,
  Body,
  Panel,
  IndexNumeral,
} from "../components/Ui.jsx";
import { SlideIn, FlowToken, DrawPath } from "../components/Motion.jsx";

const CARDS = [
  {
    title: "The proposal",
    text: "The written plan for an extension activity, filled in through a guided 20-section form and checked by reviewers.",
  },
  {
    title: "The agreement",
    text: "If partners are involved, the Memorandum of Agreement — the MOA — is drafted, reviewed legally, and signed.",
  },
  {
    title: "The delivery",
    text: "The activity is carried out, reports are filed, and final documentation closes the record.",
  },
];

export const AboutScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={1}>
      <AbsoluteFill
        style={{ padding: `0 ${LAYOUT.marginX}px`, justifyContent: "center" }}
      >
        <SlideIn delay={6} from="up">
          <Eyebrow>What is NExUS?</Eyebrow>
        </SlideIn>
        <SlideIn delay={12} from="up" distance={26}>
          <Heading style={{ maxWidth: 1280 }}>
            The online home for the Extension Office&apos;s paperwork
          </Heading>
        </SlideIn>
        <SlideIn delay={24} from="up" distance={20}>
          <Body style={{ maxWidth: 1500, marginTop: 22 }}>
            <b style={{ color: COLORS.white, fontWeight: 700 }}>Extension</b>{" "}
            means the training, workshops and outreach projects the institution
            runs with communities. NExUS — the{" "}
            <b style={{ color: COLORS.white, fontWeight: 700 }}>
              Networked Extension Unified System
            </b>{" "}
            — holds every document one of those projects needs.
          </Body>
        </SlideIn>

        {/* Stage cards with a connector the record travels along */}
        <div style={{ position: "relative", marginTop: 46 }}>
          <svg
            width={LAYOUT.contentWidth}
            height={6}
            style={{ position: "absolute", top: 40, left: 0, overflow: "visible" }}
          >
            <line
              x1={0}
              y1={3}
              x2={LAYOUT.contentWidth}
              y2={3}
              stroke="rgba(255,255,255,0.12)"
              strokeWidth={2}
            />
            <DrawPath
              d={`M0 3 H${LAYOUT.contentWidth}`}
              length={LAYOUT.contentWidth}
              delay={56}
              duration={110}
              stroke={COLORS.accent}
              strokeWidth={2.5}
            />
          </svg>
          <FlowToken
            fadeAfterLast={12}
            keyframes={[
              { frame: 60, x: 60, y: 43 },
              { frame: 110, x: LAYOUT.contentWidth / 2, y: 43 },
              { frame: 175, x: LAYOUT.contentWidth - 60, y: 43 },
            ]}
          />
          <div style={{ display: "flex", gap: LAYOUT.gutter }}>
            {CARDS.map((card, i) => (
              <SlideIn
                key={card.title}
                delay={60 + i * 20}
                from="left"
                distance={48}
                style={{ flex: 1 }}
              >
                <Panel
                  style={{
                    height: 318,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <IndexNumeral value={i + 1} />
                  <div
                    style={{
                      fontSize: 32,
                      fontWeight: 800,
                      color: COLORS.white,
                      margin: "20px 0 14px",
                    }}
                  >
                    {card.title}
                  </div>
                  <div
                    style={{
                      fontSize: 23,
                      lineHeight: 1.52,
                      color: SURFACE.textSoft,
                    }}
                  >
                    {card.text}
                  </div>
                </Panel>
              </SlideIn>
            ))}
          </div>
        </div>

        <SlideIn delay={186} from="up" distance={16}>
          <div
            style={{
              marginTop: 38,
              paddingTop: 24,
              borderTop: `1px solid ${SURFACE.hairlineSoft}`,
              fontSize: 24,
              color: SURFACE.textSoft,
            }}
          >
            Nothing is passed between offices by email — the same record follows
            the work the whole way.
          </div>
        </SlideIn>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
