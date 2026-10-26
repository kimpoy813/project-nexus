import React from "react";
import { Composition, Sequence } from "remotion";
import { VIDEO } from "./theme.js";
import { Fonts } from "./components/Fonts.jsx";
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

// Scene manifest — edit durations here (30 fps => 30 frames per second).
const roleScenes = ROLES.map((role, i) => ({
  id: `Role-${role.key}`,
  component: RoleDetailScene,
  durationInFrames: 210,
  componentProps: { roleIndex: i, sceneIndex: 4 + i },
}));

export const SCENES = [
  { id: "Intro", component: IntroScene, durationInFrames: 150 },
  { id: "About", component: AboutScene, durationInFrames: 210 },
  { id: "Glossary", component: GlossaryScene, durationInFrames: 300 },
  { id: "Roles", component: RolesScene, durationInFrames: 210 },
  ...roleScenes,
  { id: "Dashboard", component: DashboardScene, durationInFrames: 180 },
  { id: "Wizard", component: WizardScene, durationInFrames: 270 },
  { id: "Collaboration", component: CollaborationScene, durationInFrames: 240 },
  { id: "MOA", component: MoaScene, durationInFrames: 210 },
  { id: "Reports", component: ReportScene, durationInFrames: 240 },
  { id: "PublicSite", component: PublicSiteScene, durationInFrames: 210 },
  { id: "Security", component: SecurityScene, durationInFrames: 180 },
  { id: "Outro", component: OutroScene, durationInFrames: 180 },
];

export const TOTAL_DURATION = SCENES.reduce((sum, s) => sum + s.durationInFrames, 0);
export const SCENE_COUNT = SCENES.length;

const NexusTutorial = () => (
  <>
    <Fonts />
    {SCENES.map((scene, i) => {
      const from = SCENES.slice(0, i).reduce((sum, s) => sum + s.durationInFrames, 0);
      const Scene = scene.component;
      return (
        <Sequence
          key={scene.id}
          from={from}
          durationInFrames={scene.durationInFrames}
          layout="none"
        >
          <Scene {...(scene.componentProps ?? {})} />
        </Sequence>
      );
    })}
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
