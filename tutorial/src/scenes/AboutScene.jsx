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

const CARDS = [
  {
    glyph: "doc",
    title: "1. The proposal",
    text: "The written plan for an extension activity, filled in through a guided 20-section form and checked by reviewers.",
  },
  {
    glyph: "sign",
    title: "2. The agreement",
    text: "If partners are involved, the Memorandum of Agreement — the MOA — is drafted, reviewed legally, and signed.",
  },
  {
    glyph: "flag",
    title: "3. The delivery",
    text: "The activity is carried out, reports are filed, and final documentation closes the record.",
  },
];

export const AboutScene = () => (
  <AbsoluteFill>
    <Background />
    <SceneShell sceneIndex={1}>
      <AbsoluteFill style={{ padding: "150px 120px 110px" }}>
        <Rise delay={6}>
          <Eyebrow>What is NExUS?</Eyebrow>
        </Rise>
        <Rise delay={12}>
          <Heading style={{ maxWidth: 1300 }}>
            The online home for the Extension Office&apos;s paperwork
          </Heading>
        </Rise>
        <Rise delay={22}>
          <Body style={{ maxWidth: 1560, marginTop: 24 }}>
            <b style={{ color: COLORS.white }}>Extension</b> means the training,
            workshops and outreach projects the institution runs with communities.
            NExUS — the <b style={{ color: COLORS.white }}>Networked Extension
            Unified System</b> — holds every document one of those projects needs,
            on a single record that moves through three stages:
          </Body>
        </Rise>

        <div style={{ display: "flex", gap: 32, marginTop: 56 }}>
          {CARDS.map((card, i) => (
            <Rise key={card.title} delay={36 + i * 12} style={{ flex: 1 }}>
              <GlassCard style={{ height: 380, display: "flex", flexDirection: "column" }}>
                <div
                  style={{
                    width: 84,
                    height: 84,
                    borderRadius: 20,
                    background: "rgba(245,229,135,0.12)",
                    border: "1.5px solid rgba(245,229,135,0.35)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 26,
                  }}
                >
                  <Glyph name={card.glyph} size={42} />
                </div>
                <div style={{ fontSize: 38, fontWeight: 800, color: COLORS.white, marginBottom: 16 }}>
                  {card.title}
                </div>
                <div style={{ fontSize: 25, lineHeight: 1.5, color: "rgba(255,255,255,0.72)" }}>
                  {card.text}
                </div>
              </GlassCard>
            </Rise>
          ))}
        </div>

        <Rise delay={90}>
          <Body style={{ marginTop: 44, fontSize: 27, color: "rgba(255,255,255,0.7)" }}>
            Nothing is passed between offices by email or lost on someone&apos;s
            computer — the same record follows the work the whole way.
          </Body>
        </Rise>
      </AbsoluteFill>
    </SceneShell>
  </AbsoluteFill>
);
