import React from "react";
import {
  Audio,
  Composition,
  Sequence,
  interpolate,
  staticFile,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { VIDEO } from "./theme.js";
import { Fonts } from "./components/Fonts.jsx";
import { Caption } from "./components/Motion.jsx";
import { IntroScene } from "./scenes/IntroScene.jsx";
import { AboutScene } from "./scenes/AboutScene.jsx";
import { GlossaryScene } from "./scenes/GlossaryScene.jsx";
import { RolesScene } from "./scenes/RolesScene.jsx";
import { RoleDetailScene } from "./scenes/RoleDetailScene.jsx";
import { DashboardScene } from "./scenes/DashboardScene.jsx";
import { WizardScene } from "./scenes/WizardScene.jsx";
import { CollaborationScene } from "./scenes/CollaborationScene.jsx";
import { MoaScene } from "./scenes/MoaScene.jsx";
import { ReportScene } from "./scenes/ReportScene.jsx";
import { PublicSiteScene } from "./scenes/PublicSiteScene.jsx";
import { SecurityScene } from "./scenes/SecurityScene.jsx";
import { OutroScene } from "./scenes/OutroScene.jsx";
import { ROLES } from "./content.js";
import narrationManifest from "./narration-manifest.json";

// Scene manifest — durations in frames (30 fps).
const roleScenes = ROLES.map((role, i) => ({
  id: `Role-${role.key}`,
  component: RoleDetailScene,
  durationInFrames: 225,
  componentProps: { roleIndex: i, sceneIndex: 4 + i },
}));

export const SCENES = [
  { id: "Intro", component: IntroScene, durationInFrames: 210 },
  { id: "About", component: AboutScene, durationInFrames: 240 },
  { id: "Glossary", component: GlossaryScene, durationInFrames: 330 },
  { id: "Roles", component: RolesScene, durationInFrames: 240 },
  ...roleScenes,
  { id: "Dashboard", component: DashboardScene, durationInFrames: 210 },
  { id: "Wizard", component: WizardScene, durationInFrames: 300 },
  { id: "Collaboration", component: CollaborationScene, durationInFrames: 270 },
  { id: "MOA", component: MoaScene, durationInFrames: 240 },
  { id: "Reports", component: ReportScene, durationInFrames: 270 },
  { id: "PublicSite", component: PublicSiteScene, durationInFrames: 240 },
  { id: "Security", component: SecurityScene, durationInFrames: 210 },
  { id: "Outro", component: OutroScene, durationInFrames: 210 },
];

export const SCENE_COUNT = SCENES.length;
const TRANSITION_FRAMES = 12;

// Which presentation each boundary uses: slides for the product-demo act,
// wipes for the flow/tracker act, gentle fades everywhere else.
const SLIDE_BOUNDARIES = new Set([10, 11]);
const WIPE_BOUNDARIES = new Set([13, 14]);
const presentationFor = (boundary) => {
  if (SLIDE_BOUNDARIES.has(boundary)) return slide({ direction: "from-right" });
  if (WIPE_BOUNDARIES.has(boundary)) return wipe({ direction: "from-left" });
  return fade();
};

// Absolute start frame of each scene (transitions overlap by TRANSITION_FRAMES,
// but the offset is small and only used for music ducking).
const SCENE_STARTS = SCENES.map((_, i) =>
  SCENES.slice(0, i).reduce((sum, s) => sum + s.durationInFrames, 0)
);
export const TOTAL_DURATION =
  SCENES.reduce((sum, s) => sum + s.durationInFrames, 0) -
  (SCENES.length - 1) * TRANSITION_FRAMES;

// Music ducking intervals, derived from the measured narration segments.
const OPEN = 0.22;
const DUCKED = 0.08;
const RAMP = 8;
const volumeKeyframes = (() => {
  const intervals = [];
  for (const entry of narrationManifest.scenes ?? []) {
    const sceneStart = SCENE_STARTS[entry.scene - 1];
    for (const seg of entry.segments) {
      intervals.push([
        sceneStart + seg.at - RAMP,
        sceneStart + seg.at + seg.frames + 6,
      ]);
    }
  }
  intervals.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [a, b] of intervals) {
    const last = merged[merged.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b);
    else merged.push([a, b]);
  }
  const pairs = [{ f: 0, v: OPEN }];
  const push = (f, v) => {
    const ff = Math.min(Math.max(f, 0), TOTAL_DURATION);
    const prev = pairs[pairs.length - 1];
    if (ff <= prev.f) return;
    pairs.push({ f: ff, v });
  };
  for (const [a, b] of merged) {
    push(a, OPEN);
    push(a + RAMP, DUCKED);
    push(b, DUCKED);
    push(b + RAMP, OPEN);
  }
  push(TOTAL_DURATION, OPEN);
  return {
    frames: pairs.map((p) => p.f),
    values: pairs.map((p) => p.v),
  };
})();

const MusicBed = () => (
  <Audio
    src={staticFile("music/nexus-bed.wav")}
    volume={(f) =>
      interpolate(f, volumeKeyframes.frames, volumeKeyframes.values, {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    }
  />
);

const SceneAudio = ({ sceneIndex }) => {
  const entry = narrationManifest.scenes?.find((s) => s.scene === sceneIndex + 1);
  if (!entry) return null;
  return (
    <>
      {entry.segments.map((seg) => (
        <Sequence
          key={seg.file}
          from={seg.at}
          durationInFrames={seg.frames + 8}
          layout="none"
        >
          <Audio src={staticFile(seg.file)} volume={1} />
        </Sequence>
      ))}
    </>
  );
};

const NexusTutorial = () => (
  <>
    <Fonts />
    <MusicBed />
    <TransitionSeries>
      {SCENES.map((scene, i) => {
        const Scene = scene.component;
        const children = (
          <>
            <Scene {...(scene.componentProps ?? {})} />
            <SceneAudio sceneIndex={i} />
            <Caption sceneIndex={i} />
          </>
        );
        return (
          <React.Fragment key={scene.id}>
            <TransitionSeries.Sequence durationInFrames={scene.durationInFrames}>
              {children}
            </TransitionSeries.Sequence>
            {i < SCENES.length - 1 && (
              <TransitionSeries.Transition
                presentation={presentationFor(i)}
                timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
              />
            )}
          </React.Fragment>
        );
      })}
    </TransitionSeries>
  </>
);

export const RemotionRoot = () => (
  <Composition
    id="NexusTutorial"
    component={NexusTutorial}
    durationInFrames={TOTAL_DURATION}
    fps={VIDEO.fps}
    width={VIDEO.width}
    height={VIDEO.height}
  />
);
