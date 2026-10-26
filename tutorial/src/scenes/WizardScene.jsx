import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  BrowserChrome,
} from "../components/Ui.jsx";
import { WIZARD_STEPS, WIZARD_HIGHLIGHTS, EXTENSION_TYPES } from "../content.js";

// Which highlight step is active at a given frame.
const SWITCH_FRAMES = [40, 92, 144, 196, 248];

const useActiveStep = (frame) => {
  let idx = 0;
  for (let i = 0; i < SWITCH_FRAMES.length; i++) {
    if (frame >= SWITCH_FRAMES[i]) idx = i;
  }
  return WIZARD_HIGHLIGHTS[idx];
};

const StepperRow = ({ no, label, state }) => {
  const done = state === "done";
  const current = state === "current";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "7px 12px",
        borderRadius: 10,
        background: current ? "#dfead3" : "transparent",
      }}
    >
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: "50%",
          flexShrink: 0,
          fontSize: 15,
          fontWeight: 800,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: done ? COLORS.primary : current ? COLORS.accent : COLORS.white,
          color: done ? COLORS.white : current ? COLORS.primary : COLORS.muted,
          border: `1.5px solid ${done || current ? "transparent" : COLORS.line}`,
        }}
      >
        {done ? "✓" : no}
      </div>
      <div
        style={{
          fontSize: 16.5,
          fontWeight: current ? 800 : 500,
          color: done ? COLORS.primary : current ? COLORS.ink : COLORS.muted,
          lineHeight: 1.2,
        }}
      >
        {label}
      </div>
    </div>
  );
};

const Field = ({ label, wide = false, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 18 } });
  return (
    <div style={{ flex: wide ? "1 1 100%" : 1, opacity: s, transform: `translateY(${(1 - s) * 16}px)` }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: COLORS.ink, marginBottom: 8 }}>{label}</div>
      <div
        style={{
          height: 52,
          borderRadius: 12,
          background: COLORS.white,
          border: `1.5px solid ${COLORS.line}`,
        }}
      />
    </div>
  );
};

export const WizardScene = () => {
  const frame = useCurrentFrame();
  const active = useActiveStep(frame);
  const pct = interpolate(frame, [40, 290], [0.05, 0.85], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Background />
      <SceneShell sceneIndex={12}>
        <AbsoluteFill style={{ padding: "130px 120px 80px" }}>
          <Rise delay={4}>
            <Eyebrow>Step 2 — Build the proposal</Eyebrow>
          </Rise>
          <Rise delay={10}>
            <Heading size={52}>
              The guided wizard walks you through <span style={{ color: COLORS.accent }}>20 sections</span>
            </Heading>
          </Rise>

          <Rise delay={22} style={{ marginTop: 38 }}>
            <BrowserChrome url={`nexus.example/proposals/id/edit/step/${active.no}/`}>
              <div style={{ display: "flex", minHeight: 540, background: COLORS.paper }}>
                {/* left: full 20-step stepper */}
                <div
                  style={{
                    width: 340,
                    flexShrink: 0,
                    background: "#eef2e7",
                    borderRight: `1px solid ${COLORS.line}`,
                    padding: "20px 16px",
                    overflow: "hidden",
                  }}
                >
                  <div style={{ fontSize: 18, fontWeight: 800, color: COLORS.primary, padding: "0 12px 12px" }}>
                    Proposal steps
                  </div>
                  {WIZARD_STEPS.map((label, i) => {
                    const no = i + 1;
                    const state = no < active.no ? "done" : no === active.no ? "current" : "todo";
                    return <StepperRow key={label} no={no} label={label} state={state} />;
                  })}
                </div>

                {/* middle: the form for the active step */}
                <div style={{ flex: 1, padding: "34px 40px" }} key={active.no}>
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <div
                      style={{
                        fontSize: 19,
                        fontWeight: 800,
                        color: COLORS.primary,
                        background: "#dfead3",
                        borderRadius: 10,
                        padding: "8px 16px",
                      }}
                    >
                      Step {active.no} of 20
                    </div>
                    <div style={{ fontSize: 30, fontWeight: 800, color: COLORS.ink }}>
                      {active.title}
                    </div>
                  </div>
                  <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 10 }}>{active.hint}</div>

                  {/* step-specific mock content */}
                  {active.no === 1 && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 28 }}>
                      {EXTENSION_TYPES.map((t, i) => (
                        <div
                          key={t}
                          style={{
                            border: `2px solid ${i === 2 ? COLORS.primary : COLORS.line}`,
                            background: i === 2 ? "#dfead3" : COLORS.white,
                            borderRadius: 14,
                            padding: "20px 22px",
                            fontSize: 20,
                            fontWeight: i === 2 ? 800 : 600,
                            color: COLORS.ink,
                            display: "flex",
                            alignItems: "center",
                            gap: 12,
                          }}
                        >
                          <span
                            style={{
                              width: 22,
                              height: 22,
                              borderRadius: "50%",
                              border: `2px solid ${i === 2 ? COLORS.primary : COLORS.muted}`,
                              background: i === 2 ? COLORS.primary : "transparent",
                            }}
                          />
                          {t}
                        </div>
                      ))}
                    </div>
                  )}

                  {active.no !== 1 && active.no !== 17 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 22, marginTop: 30 }}>
                      <Field label="Title / name" wide delay={30} />
                      <Field label="Primary detail" delay={40} />
                      <Field label="Supporting detail" delay={48} />
                      <Field label="Notes" wide delay={56} />
                    </div>
                  )}

                  {active.no === 17 && (
                    <div style={{ marginTop: 28, display: "flex", flexDirection: "column", gap: 14 }}>
                      {["Work plan and schedule (DOCX)", "Gantt chart (XLSX)", "Supporting attachments"].map(
                        (f, i) => (
                          <div
                            key={f}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 16,
                              border: `1.5px solid ${COLORS.line}`,
                              background: COLORS.white,
                              borderRadius: 14,
                              padding: "18px 22px",
                              fontSize: 20,
                              fontWeight: 600,
                              color: COLORS.ink,
                            }}
                          >
                            <div
                              style={{
                                width: 44,
                                height: 44,
                                borderRadius: 10,
                                background: "#dfead3",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                color: COLORS.primary,
                                fontWeight: 800,
                              }}
                            >
                              {i === 1 ? "XLS" : "DOC"}
                            </div>
                            {f}
                          </div>
                        )
                      )}
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 16, marginTop: 34 }}>
                    <div
                      style={{
                        fontSize: 21,
                        fontWeight: 700,
                        color: COLORS.primary,
                        border: `1.5px solid ${COLORS.primary}`,
                        borderRadius: 12,
                        padding: "13px 26px",
                      }}
                    >
                      Save draft
                    </div>
                    <div
                      style={{
                        fontSize: 21,
                        fontWeight: 700,
                        color: COLORS.white,
                        background: COLORS.primary,
                        borderRadius: 12,
                        padding: "13px 30px",
                      }}
                    >
                      Save &amp; Next →
                    </div>
                  </div>
                </div>

                {/* right: context rail */}
                <div
                  style={{
                    width: 290,
                    flexShrink: 0,
                    background: COLORS.white,
                    borderLeft: `1px solid ${COLORS.line}`,
                    padding: "30px 26px",
                  }}
                >
                  <div style={{ fontSize: 18, fontWeight: 800, color: COLORS.ink }}>Completion</div>
                  <div
                    style={{
                      height: 12,
                      borderRadius: 8,
                      background: COLORS.line,
                      marginTop: 14,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${pct * 100}%`,
                        height: "100%",
                        background: `linear-gradient(90deg, ${COLORS.primaryBright}, ${COLORS.primary})`,
                        borderRadius: 8,
                      }}
                    />
                  </div>
                  <div style={{ fontSize: 18, color: COLORS.muted, marginTop: 8, fontWeight: 600 }}>
                    {Math.round(pct * 100)}% complete
                  </div>

                  <div
                    style={{
                      marginTop: 28,
                      fontSize: 17,
                      lineHeight: 1.55,
                      color: COLORS.muted,
                      background: COLORS.paper,
                      border: `1px solid ${COLORS.line}`,
                      borderRadius: 14,
                      padding: 18,
                    }}
                  >
                    <b style={{ color: COLORS.ink }}>Tip:</b> drafts save as you go. You can skip
                    sections, return any time, and only submit when every required step is complete.
                  </div>

                  <div
                    style={{
                      marginTop: 22,
                      fontSize: 17,
                      fontWeight: 700,
                      color: COLORS.secondary,
                      background: "#f3dede",
                      borderRadius: 14,
                      padding: 16,
                    }}
                  >
                    Steps 19–20 require research abstract &amp; certificate uploads for
                    research-based proposals.
                  </div>
                </div>
              </div>
            </BrowserChrome>
          </Rise>
        </AbsoluteFill>
      </SceneShell>
    </AbsoluteFill>
  );
};
