// Voiceover script, rebuilt as TIMED SEGMENTS so the spoken line matches the
// exact visual beat on screen. Each scene lists segments in playback order;
// `at` is the frame (local to the scene, 30 fps) where the line begins.
//
// Pronunciation: the product is written NExUS but spoken "nexus", so every
// spoken line uses the lowercase word — never the letter-by-letter spelling.
//
// Natural-voice clips live at public/narration/sXX-YY.mp3; the offline
// meSpeak fallback writes .wav with the same names. Segment start frames are
// spaced so measured clip lengths never overlap or run past their scene
// (each scene keeps a 12-frame tail for the transition).
export const NARRATION_BUDGETS = [
  7, 8, 11, 8, 7.5, 7.5, 7.5, 7.5, 7.5, 7.5, 7.5, 7, 10, 9, 8, 9, 8, 7, 7,
];

export const NARRATION = [
  // 01 Intro — 210f
  {
    segments: [
      { at: 10, text: "Welcome to nexus." },
      {
        at: 66,
        text: "It's the online home for all extension paperwork.",
      },
    ],
  },
  // 02 About — 240f
  {
    segments: [
      {
        at: 12,
        text: "Extension means training and outreach projects run with outside communities.",
      },
      {
        at: 155,
        text: "One record follows the whole journey.",
      },
    ],
  },
  // 03 Glossary — 330f
  {
    segments: [
      {
        at: 12,
        text: "A proponent owns the proposal; evaluators review it; coordinators endorse it.",
      },
      {
        at: 174,
        text: "An MOA is the signed partnership agreement. A tracker shows its stage.",
      },
    ],
  },
  // 04 Roles — 240f
  {
    segments: [
      {
        at: 12,
        text: "Seven roles use nexus, each with a dashboard for its work.",
      },
      { at: 150, text: "Next, what each role can do." },
    ],
  },
  // 05 Faculty — 225f
  {
    segments: [
      {
        at: 12,
        text: "Faculty create proposals, answer reviewer comments, run the activity, and file its reports.",
      },
    ],
  },
  // 06 Staff — 225f
  {
    segments: [
      {
        at: 12,
        text: "Office staff see every proposal, move agreements along, and request quarterly reports.",
      },
    ],
  },
  // 07 Evaluator — 225f
  {
    segments: [
      {
        at: 12,
        text: "Evaluators work a review queue, comment on exact sections, and return or approve proposals.",
      },
    ],
  },
  // 08 Department Coordinator — 225f
  {
    segments: [
      {
        at: 12,
        text: "Department coordinators endorse their department's proposals and file its quarterly reports.",
      },
    ],
  },
  // 09 Campus Coordinator — 225f
  {
    segments: [
      {
        at: 12,
        text: "Campus coordinators route work across departments and monitor all campus proposals.",
      },
    ],
  },
  // 10 Director — 225f
  {
    segments: [
      {
        at: 12,
        text: "The Director assigns evaluators, gives final approval, and watches the office's targets.",
      },
    ],
  },
  // 11 Admin — 225f
  {
    segments: [
      {
        at: 8,
        text: "Admins run the system — accounts, website, templates, security — but never your proposal.",
      },
    ],
  },
  // 12 Dashboard — 210f
  {
    segments: [
      {
        at: 10,
        text: "Your dashboard shows your proposals and where each stands.",
      },
      { at: 132, text: "Start one with a single click." },
    ],
  },
  // 13 Wizard — 300f
  {
    segments: [
      {
        at: 12,
        text: "Building a proposal means walking through twenty guided sections, one question at a time.",
      },
      {
        at: 176,
        text: "Drafts save automatically, so return and submit when complete.",
      },
    ],
  },
  // 14 Collaboration — 270f
  {
    segments: [
      {
        at: 12,
        text: "Reviewers comment on the exact section, not vague email threads.",
      },
      {
        at: 150,
        text: "Every revision stays on the record through seven statuses.",
      },
    ],
  },
  // 15 MOA — 240f
  {
    segments: [
      {
        at: 12,
        text: "With a partner, the MOA tracker moves through six stages to signing.",
      },
      { at: 168, text: "No partner? Skip." },
    ],
  },
  // 16 Reports — 270f
  {
    segments: [
      {
        at: 12,
        text: "The activity then runs through six stages to final documents.",
      },
      {
        at: 150,
        text: "Reports and paperwork come from the same record, ready to print.",
      },
    ],
  },
  // 17 PublicSite — 240f
  {
    segments: [
      {
        at: 12,
        text: "The public website is edited without code, using reusable blocks.",
      },
      { at: 150, text: "Every change is logged, with the editor named." },
    ],
  },
  // 18 Security — 210f
  {
    segments: [
      {
        at: 12,
        text: "Every account has verified email, auto-logout, login lockouts, and secure storage.",
      },
    ],
  },
  // 19 Outro — 210f
  {
    segments: [
      { at: 8, text: "That's nexus — one record, from idea to finish." },
      { at: 125, text: "Log in and start your first proposal." },
    ],
  },
];
