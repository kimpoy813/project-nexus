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
  Panel,
  IndexNumeral,
} from "../components/Ui.jsx";

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
        style={{
          padding: `0 ${LAYOUT.marginX}px`,
          justifyContent: "center",
        }}
      >
        <Rise delay={6}>
          <Eyebrow>What is NExUS?</Eyebrow>
        </Rise>
        <Rise delay={12}>
          <Heading style={{ maxWidth: 1280 }}>
            The online home for the Extension Office&apos;s paperwork
          </Heading>
        </Rise>
        <Rise delay={20}>
          <Body style={{ maxWidth: 1500, marginTop: 22 }}>
            <b style={{ color: COLORS.white, fontWeight: 700 }}>Extension</b>{" "}
            means the training, workshops and outreach projects the institution
            runs with communities. NExUS — the{" "}
            <b style={{ color: COLORS.white, fontWeight: 700 }}>
              Networked Extension Unified System
            </b>{" "}
            — holds every document one of those projects needs, on a single
            record that moves through three stages:
          </Body>
        </Rise>

        <div style={{ display: "flex", gap: LAYOUT.gutter, marginTop: 44 }}>
          {CARDS.map((card, i) => (
            <Rise
              key={card.title}
              delay={30 + i * 8}
              style={{ flex: 1 }}
            >
              <Panel
                style={{
                  height: 330,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <IndexNumeral value={i + 1} />
                <div
                  style={{
                    fontSize: 34,
                    fontWeight: 800,
                    color: COLORS.white,
                    margin: "22px 0 14px",
                  }}
                >
                  {card.title}
                </div>
                <div
                  style={{
                    fontSize: 24,
                    lineHeight: 1.52,
                    color: SURFACE.textSoft,
                  }}
                >
                  {card.text}
                </div>
              </Panel>
            </Rise>
          ))}
        </div>

        <Rise delay={66}>
          <div
            style={{
              marginTop: 40,
              paddingTop: 26,
              borderTop: `1px solid ${SURFACE.hairlineSoft}`,
              fontSize: 25,
              color: SURFACE.textSoft,
            }}
          >
            Nothing is passed between offices by email or lost on
            someone&apos;s computer — the same record follows the work the
            whole way.
          </div>
        </Rise>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
