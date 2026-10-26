// Voiceover script, one entry per scene in Root.jsx SCENES order.
// Timing budget: the TTS voice delivers ~3 spoken words per second including
// clause pauses (measured from generated clips), so each line is capped at
// about 2.8 words per second of scene length to leave a safety margin.
//   5s scene <= 13 words | 6s <= 16 | 7s <= 19 | 8s <= 22 | 9s <= 25 | 10s <= 28
// Generated clips live in public/narration/scene-XX.{mp3,wav};
// scripts/sync-narration.mjs scans that folder and Root.jsx only mounts clips
// listed in the manifest.

// Scene durations in seconds, index-aligned with NARRATION (mirrors the
// SCENES manifest in Root.jsx). The offline fallback generator verifies each
// clip fits before its sequence boundary.
export const NARRATION_BUDGETS = [
  5, 7, 10, 7, 7, 7, 7, 7, 7, 7, 7, 6, 9, 8, 7, 8, 7, 6, 6,
];

export const NARRATION = [
  // 01 Intro — 150f / 5s — 11 words
  "Welcome to NExUS, a plain-language guide to the system.",
  // 02 About — 210f / 7s — 16 words
  "NExUS keeps every document a project needs on one record, from idea to completion.",
  // 03 Glossary — 300f / 10s — 25 words
  "A few key words: a proposal is the written plan, the proponent owns it, evaluators review it, and an MOA is the signed partnership agreement.",
  // 04 Roles — 210f / 7s — 12 words
  "Seven roles use NExUS, each landing on its own dashboard.",
  // 05 Faculty — 210f / 7s — 11 words
  "Faculty create proposals, answer reviews, and file activity reports.",
  // 06 Staff — 210f / 7s — 14 words
  "Office staff track every proposal, move agreements along, and request quarterly reports.",
  // 07 Evaluator — 210f / 7s — 17 words
  "Evaluators get a review queue, comment on the exact section, and return or approve each proposal.",
  // 08 Department Coordinator — 210f / 7s — 13 words
  "Department coordinators endorse their department's proposals and file its quarterly reports.",
  // 09 Campus Coordinator — 210f / 7s — 14 words
  "Campus coordinators route work across every department and monitor the campus's proposals.",
  // 10 Director — 210f / 7s — 14 words
  "The Director assigns evaluators, gives final approval, and watches the office's targets.",
  // 11 Admin — 210f / 7s — 16 words
  "Admins manage accounts, the public website, templates, and security — but never your proposal.",
  // 12 Dashboard — 180f / 6s — 11 words
  "After signing in, your dashboard shows every proposal you own.",
  // 13 Wizard — 270f / 9s — 19 words
  "Building a proposal means walking through twenty guided sections. Drafts save automatically, so return anytime and submit when complete.",
  // 14 Collaboration — 240f / 8s — 16 words
  "Reviewers comment on the exact section, and every revision stays on the same record.",
  // 15 MOA — 210f / 7s — 13 words
  "The MOA tracker carries each partnership agreement through six stages to signing.",
  // 16 Reports — 240f / 8s — 17 words
  "Once approved, activities run through six stages, with reports and paperwork from the same record.",
  // 17 PublicSite — 210f / 7s — 13 words
  "The public website is edited without code, and every change is logged.",
  // 18 Security — 180f / 6s — 13 words
  "Every account gets verified email, auto-logout, login protection, and secure storage.",
  // 19 Outro — 180f / 6s — 13 words
  "That's NExUS. Log in, open your dashboard, and start your first proposal.",
];
