import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";
import { COLORS, LAYOUT } from "../theme.js";
import { Background } from "../components/Background.jsx";
import {
  Rise,
  SceneShell,
  Eyebrow,
  Heading,
  BrowserChrome,
} from "../components/Ui.jsx";
import { WIZARD_STEPS, WIZARD_HIGHLIGHTS, EXTENSION_TYPES } from "../content.js";

const easeOut = Easing.out(Easing.cubic);

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
        gap: 9,
        padding: "5px 10px",
        borderRadius: 8,
        background: current ? "#dfead3" : "transparent",
      }}
    >
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          flexShrink: 0,
          fontSize: 12.5,
          fontWeight: 800,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: done
            ? COLORS.primary
            : current
            ? COLORS.accent
            : COLORS.white,
          color: done ? COLORS.white : current ? COLORS.primary : COLORS.muted,
          border: `1.5px solid ${
            done || current ? "transparent" : COLORS.line
          }`,
        }}
      >
        {done ? "✓" : no}
      </div>
      <div
        style={{
          fontSize: 14,
          fontWeight: current ? 800 : 500,
          color: done ? COLORS.primary : current ? COLORS.ink : COLORS.muted,
          lineHeight: 1.25,
        }}
      >
        {label}
      </div>
    </div>
  );
};

const Field = ({ label, wide = false, delay, lines = 1 }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOut,
  });
  return (
    <div
      style={{
        flex: wide ? "1 1 100%" : 1,
        opacity: t,
        transform: `translateY(${(1 - t) * 10}px)`,
      }}
    >
      <div
        style={{
          fontSize: 17,
          fontWeight: 700,
          color: COLORS.ink,
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div
        style={{
          height: lines === 1 ? 50 : 118,
          borderRadius: 10,
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
        <AbsoluteFill
          style={{
            padding: `0 ${LAYOUT.marginX}px`,
            justifyContent: "center",
          }}
        >
          <Rise delay={4}>
            <Eyebrow>Step 2 — Build the proposal</Eyebrow>
          </Rise>
          <Rise delay={10}>
            <Heading size={48}>
              The guided wizard walks you through{" "}
              <span style={{ color: COLORS.accent }}>20 sections</span>
            </Heading>
          </Rise>

          <Rise delay={20} style={{ marginTop: 32 }}>
            <BrowserChrome
              url={`nexus.example/proposals/id/edit/step/${active.no}/`}
            >
              <div
                style={{
                  display: "flex",
                  minHeight: 560,
                  background: COLORS.paper,
                }}
              >
                {/* left: full 20-step stepper, every step visible */}
                <div
                  style={{
                    width: 320,
                    flexShrink: 0,
                    background: "#eef2e7",
                    borderRight: `1px solid ${COLORS.line}`,
                    padding: "16px 12px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      fontSize: 16,
                      fontWeight: 800,
                      color: COLORS.primary,
                      padding: "0 10px 10px",
                    }}
                  >
                    Proposal steps
                  </div>
                  {WIZARD_STEPS.map((label, i) => {
                    const no = i + 1;
                    const state =
                      no < active.no
                        ? "done"
                        : no === active.no
                        ? "current"
                        : "todo";
                    return (
                      <StepperRow
                        key={label}
                        no={no}
                        label={label}
                        state={state}
                      />
                    );
                  })}
                </div>

                {/* middle: the form for the active step */}
                <div
                  style={{ flex: 1, padding: "30px 36px" }}
                  key={active.no}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 17,
                        fontWeight: 800,
                        color: COLORS.primary,
                        background: "#dfead3",
                        borderRadius: 8,
                        padding: "7px 14px",
                      }}
                    >
                      Step {active.no} of 20
                    </div>
                    <div
                      style={{
                        fontSize: 28,
                        fontWeight: 800,
                        color: COLORS.ink,
                      }}
                    >
                      {active.title}
                    </div>
                  </div>
                  <div
                    style={{
                      fontSize: 18,
                      color: COLORS.muted,
                      marginTop: 8,
                    }}
                  >
                    {active.hint}
                  </div>

                  {/* step-specific mock content */}
                  {active.no === 1 && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 16,
                        marginTop: 24,
                      }}
                    >
                      {EXTENSION_TYPES.map((t, i) => (
                        <div
                          key={t}
                          style={{
                            border: `2px solid ${
                              i === 2 ? COLORS.primary : COLORS.line
                            }`,
                            background: i === 2 ? "#dfead3" : COLORS.white,
                            borderRadius: 12,
                            padding: "18px 20px",
                            fontSize: 18,
                            fontWeight: i === 2 ? 800 : 600,
                            color: COLORS.ink,
                            display: "flex",
                            alignItems: "center",
                            gap: 12,
                          }}
                        >
                          <span
                            style={{
                              width: 20,
                              height: 20,
                              borderRadius: "50%",
                              border: `2px solid ${
                                i === 2 ? COLORS.primary : COLORS.muted
                              }`,
                              background:
                                i === 2 ? COLORS.primary : "transparent",
                            }}
                          />
                          {t}
                        </div>
                      ))}
                    </div>
                  )}

                  {active.no !== 1 && active.no !== 17 && (
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 20,
                        marginTop: 26,
                      }}
                    >
                      <Field label="Title / name" wide delay={28} />
                      <Field label="Primary detail" delay={36} />
                      <Field label="Supporting detail" delay={42} />
                      <Field label="Background and notes" wide delay={48} lines={2} />
                    </div>
                  )}

                  {active.no === 17 && (
                    <div
                      style={{
                        marginTop: 24,
                        display: "flex",
                        flexDirection: "column",
                        gap: 12,
                      }}
                    >
                      {[
                        "Work plan and schedule (DOCX)",
                        "Gantt chart (XLSX)",
                        "Supporting attachments",
                      ].map((f, i) => (
                        <div
                          key={f}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 14,
                            border: `1.5px solid ${COLORS.line}`,
                            background: COLORS.white,
                            borderRadius: 12,
                            padding: "16px 20px",
                            fontSize: 18,
                            fontWeight: 600,
                            color: COLORS.ink,
                          }}
                        >
                          <div
                            style={{
                              width: 42,
                              height: 42,
                              borderRadius: 9,
                              background: "#dfead3",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: COLORS.primary,
                              fontWeight: 800,
                              fontSize: 14,
                            }}
                          >
                            {i === 1 ? "XLS" : "DOC"}
                          </div>
                          {f}
                        </div>
                      ))}
                    </div>
                  )}

                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      gap: 14,
                      marginTop: 28,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 19,
                        fontWeight: 700,
                        color: COLORS.primary,
                        border: `1.5px solid ${COLORS.primary}`,
                        borderRadius: 10,
                        padding: "12px 24px",
                      }}
                    >
                      Save draft
                    </div>
                    <div
                      style={{
                        fontSize: 19,
                        fontWeight: 700,
                        color: COLORS.white,
                        background: COLORS.primary,
                        borderRadius: 10,
                        padding: "12px 28px",
                      }}
                    >
                      Save &amp; Next →
                    </div>
                  </div>
                </div>

                {/* right: context rail */}
                <div
                  style={{
                    width: 272,
                    flexShrink: 0,
                    background: COLORS.white,
                    borderLeft: `1px solid ${COLORS.line}`,
                    padding: "26px 22px",
                  }}
                >
                  <div
                    style={{
                      fontSize: 17,
                      fontWeight: 800,
                      color: COLORS.ink,
                    }}
                  >
                    Completion
                  </div>
                  <div
                    style={{
                      height: 10,
                      borderRadius: 8,
                      background: COLORS.line,
                      marginTop: 12,
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
                  <div
                    style={{
                      fontSize: 16,
                      color: COLORS.muted,
                      marginTop: 8,
                      fontWeight: 600,
                    }}
                  >
                    {Math.round(pct * 100)}% complete
                  </div>

                  <div
                    style={{
                      marginTop: 24,
                      fontSize: 15.5,
                      lineHeight: 1.55,
                      color: COLORS.muted,
                      background: COLORS.paper,
                      border: `1px solid ${COLORS.line}`,
                      borderRadius: 12,
                      padding: 16,
                    }}
                  >
                    <b style={{ color: COLORS.ink }}>Tip:</b> drafts save as
                    you go. Skip sections, return any time, and only submit
                    when every required step is complete.
                  </div>

                  <div
                    style={{
                      marginTop: 18,
                      fontSize: 15.5,
                      fontWeight: 700,
                      lineHeight: 1.5,
                      color: COLORS.secondary,
                      background: "#f3dede",
                      borderRadius: 12,
                      padding: 14,
                    }}
                  >
                    Steps 19–20 require research abstract &amp; certificate
                    uploads for research-based proposals.
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
