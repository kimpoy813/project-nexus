// Every label in the tutorial is sourced from the real NExUS codebase:
//  - roles: accounts/models.py User.ROLE_CHOICES + accounts/permissions.py
//  - wizard steps: proposals/views/constants.py INITIAL_STEP_LABELS
//  - statuses/flows: proposals/models.py (ProposalStatus, MOA_FLOW, IMPLEMENTATION_FLOW)
//  - admin/no-code features: accounts/urls.py + details/content_sources.py
// Wording is deliberately plain: every office term is explained when first used.

// ---------------------------------------------------------------- glossary
export const GLOSSARY = [
  {
    term: "Extension",
    meaning: "School-run projects and activities that share knowledge with outside communities — training, workshops, outreach.",
  },
  {
    term: "Proposal",
    meaning: "The written plan for an extension activity, prepared before the activity happens.",
  },
  {
    term: "Proponent",
    meaning: "The person or team who proposes an activity and owns the proposal.",
  },
  {
    term: "Evaluator",
    meaning: "A reviewer assigned to check a proposal and write comments on it.",
  },
  {
    term: "Coordinator",
    meaning: "A leader who endorses work at the department or campus level.",
  },
  {
    term: "Review round",
    meaning: "One complete pass of checking. A proposal can be returned, revised, and checked again.",
  },
  {
    term: "MOA",
    meaning: "Memorandum of Agreement — the signed document that makes a partnership official.",
  },
  {
    term: "GAD",
    meaning: "Gender and Development — showing the activity fairly addresses different people's needs.",
  },
  {
    term: "SDG",
    meaning: "Sustainable Development Goals — the United Nations' 17 global goals an activity can support.",
  },
  {
    term: "Extension Thrust",
    meaning: "The office's priority themes; activities should line up with at least one.",
  },
  {
    term: "Tracker",
    meaning: "The on-screen progress path showing exactly which stage a document is in.",
  },
  {
    term: "Accomplishment Report",
    meaning: "A quarterly summary of what a campus or department actually delivered.",
  },
];

// ---------------------------------------------------------------- roles
// `who` is the plain-language job description; `functions` are what the role
// can actually do in NExUS, translated from the permission predicates and URLs.
export const ROLES = [
  {
    key: "Faculty",
    who: "Teachers and staff who run extension activities",
    accent: "yellow",
    functions: [
      "Start a proposal and work through the 20-section guided form, saving drafts at any time",
      "Add co-proponents and collaborators who can help fill it in",
      "Attach work plans, Gantt charts, research abstracts and certificates",
      "Submit for review, answer comments, and re-submit revisions",
      "Download ready-to-print documents and upload the signed copy",
      "Run the approved activity and file its reports",
    ],
  },
  {
    key: "Staff",
    who: "The Extension Office team that keeps everything moving",
    accent: "green",
    functions: [
      "See every proposal in the system, not only one person's",
      "Move each MOA through its six stages, from drafting to signing",
      "Move activities through implementation, reporting and monitoring",
      "Release official approval documents and comment summaries as Word files",
      "Ask campuses for quarterly reports and follow up on their answers",
      "Check campus targets and office-wide analytics",
    ],
  },
  {
    key: "Evaluator",
    who: "Reviewers who check proposals before approval",
    accent: "maroon",
    functions: [
      "Receive a personal review queue of proposals assigned to them",
      "Open any of the 20 sections and attach comments right where changes are needed",
      "Issue a review summary of all comments",
      "Send a proposal back for revision, or recommend it for approval",
      "Keep track of which reviews are pending and which are finished",
    ],
  },
  {
    key: "Department Coordinator",
    who: "Endorses proposals from one department",
    accent: "yellow",
    functions: [
      "Review and endorse proposals coming from their own department",
      "Return department proposals that still need work",
      "File the department's quarterly accomplishment reports with attachments",
      "Compare department targets against what was actually delivered",
    ],
  },
  {
    key: "Campus Coordinator",
    who: "Routes extension work for a whole campus",
    accent: "green",
    functions: [
      "Endorse proposals across every department on the campus",
      "Answer quarterly report requests from the Extension Office",
      "Upload the campus report and the figures that update its targets",
      "Monitor all campus proposals in one review queue",
    ],
  },
  {
    key: "Director",
    who: "The office head who oversees the whole program",
    accent: "maroon",
    functions: [
      "See the full pipeline across all campuses, with search and filters",
      "Assign evaluators to proposals — and remove them when needed",
      "Give the final approval once reviews are settled",
      "Oversee the MOA and implementation trackers",
      "Request quarterly accomplishment reports from campuses",
      "Read office-wide analytics and target progress",
    ],
  },
  {
    key: "Admin",
    who: "Runs the system itself, not the extension work",
    accent: "yellow",
    functions: [
      "Create accounts, assign roles, and manage email verification",
      "Set what each role is allowed to do",
      "Edit the public website with drag-and-drop, no-code builders",
      "Manage campuses, colleges, departments and document signatories",
      "Maintain the Template Library and the 20 wizard sections",
      "Control branding colors, maintenance mode and security timeouts",
    ],
    boundary:
      "Admin cannot rewrite someone else's proposal or file an accomplishment report on their behalf — those stay with the people who own the work.",
  },
];

// ---------------------------------------------------------------- wizard
// The full 20-step proposal wizard (INITIAL_STEP_LABELS), grouped into plain
// chapters so a first-time viewer understands what the form actually asks.
export const WIZARD_CHAPTERS = [
  {
    chapter: "What the activity is",
    steps: ["Extension type & scope", "Title", "Proponents", "Implementing office", "Beneficiaries", "SDGs & thrusts", "Utility model"],
  },
  {
    chapter: "What it costs and who joins",
    steps: ["Budget & funding", "Participants by sex", "Gender (GAD) issues addressed"],
  },
  {
    chapter: "When, where and why",
    steps: ["Date, venue & site", "Rationale & background", "Significance", "Objectives", "Methodology", "Expected output & outcome"],
  },
  {
    chapter: "Files and supporting papers",
    steps: ["Work plan & Gantt chart", "Funding strategy", "Research abstract", "Completion certificate"],
  },
];

// Stepper labels shown in the animated browser mock (the full 20).
export const WIZARD_STEPS = [
  "Extension Type and Scope",
  "Title",
  "Proponents",
  "Implementing Agency/Unit",
  "Collaborators/Beneficiaries",
  "SDGs / Extension Agenda",
  "Utility Model",
  "Budgetary Requirement",
  "Participants / Proposed Clients",
  "Gender Issues / Mandates",
  "Date and Venue / Site",
  "Rationale / Background",
  "Significance",
  "Objectives",
  "Methodology / Mechanics",
  "Output / Outcome",
  "Details of Activities",
  "Funding Strategy",
  "Research Abstract Upload",
  "Certificate of Completion",
];

export const WIZARD_HIGHLIGHTS = [
  { no: 1, title: "Extension Type and Scope", hint: "Research-based · Request-based · Community-based" },
  { no: 3, title: "Proponents", hint: "Add the people behind the activity and their roles" },
  { no: 8, title: "Budgetary Requirement", hint: "Funding source and how the money is spent" },
  { no: 14, title: "Objectives", hint: "Specific, measurable goals the activity promises" },
  { no: 17, title: "Details of Activities", hint: "Work plan, Gantt chart and supporting files" },
];

export const EXTENSION_TYPES = [
  "Research-based (Faculty)",
  "Research-based (Student)",
  "Request-based",
  "Community-based",
];

// ------------------------------------------------------- end-to-end journey
export const JOURNEY_STEPS = [
  { title: "Create", text: "Start from your dashboard and choose the extension type" },
  { title: "Draft", text: "Fill the 20 guided sections in any order; drafts save automatically" },
  { title: "Submit", text: "Send the finished proposal into the review pipeline" },
  { title: "Review", text: "Evaluators and coordinators comment, endorse, or return it" },
  { title: "Approve", text: "The Director gives final approval after all rounds are settled" },
  { title: "Sign", text: "Print, sign, upload the signed copy, and route the MOA if needed" },
  { title: "Deliver", text: "Run the activity and move the tracker through each report" },
  { title: "Close", text: "Final evaluation and documentation complete the record" },
];

// ---------------------------------------------------------------- review
export const COLLABORATION_FEATURES = [
  {
    title: "Comments on the exact section",
    text: "Reviewers attach notes to the specific part that needs changing — no vague email threads.",
  },
  {
    title: "Review rounds with full history",
    text: "Every return, revision and re-submission is stored as a numbered version on the same record.",
  },
  {
    title: "Several reviewers, one queue",
    text: "The Director assigns evaluators; department and campus coordinators endorse at their own level.",
  },
  {
    title: "Built-in teamwork",
    text: "Add co-proponents and editors, share a read-only link, and see who is editing the proposal live.",
  },
];

export const PROPOSAL_STATUSES = [
  "Drafting",
  "Submitted for Review",
  "In Review",
  "Review Summary Issued",
  "For Revision",
  "Ready to Print",
  "Approved / Claiming",
];

// ---------------------------------------------------------------- MOA
export const MOA_STEPS = [
  "Drafting",
  "Legal Review",
  "Under Revision",
  "Certification Ready",
  "Agenda Brief & Presentation",
  "MOA Completed",
];

// ---------------------------------------------------------------- implementation
export const IMPLEMENTATION_STEPS = [
  "Implementation of Extension Activity",
  "Post-Activity Report Submission",
  "Extension Progress Report",
  "Monitoring and Evaluation",
  "Comments and Actions Taken",
  "Final Evaluation and Documentation",
];

export const IMPLEMENTATION_DESCRIPTIONS = [
  "Proponents conduct the approved extension activities.",
  "Submit the post-activity report with documentation.",
  "File periodic progress reports for ongoing projects.",
  "Monitoring visits and field validation with the Extension Office.",
  "Address findings in the Summary of Comments and Actions Taken.",
  "Terminal report and final documentation close the record.",
];

export const REPORTING_FEATURES = [
  { title: "Auto-generated paperwork", text: "Work plans, Gantt charts, funding templates and approval documents download as Word or Excel, filled in from the record." },
  { title: "Quarterly accomplishment reports", text: "Coordinators file what their department or campus delivered each quarter." },
  { title: "Report requests", text: "The office asks a campus for its quarterly report; the campus uploads it, and targets update automatically." },
  { title: "Comment summaries", text: "Staff export every reviewer comment into one Word document for the proponent." },
];

// ------------------------------------------------------------ public website
export const CONTENT_BLOCKS = [
  { name: "Extension Thrust cards", text: "The office's priority themes shown on the Home page" },
  { name: "Sustainable Development Goals", text: "The global goals the office aligns its work with" },
  { name: "Personnel & Activities", text: "People and featured extension activities" },
  { name: "Extension Processes", text: "Step-by-step process outlines, nested to any depth" },
  { name: "Targets", text: "Quarterly and yearly delivery targets" },
  { name: "Template Library", text: "Ready-to-download Word and Excel forms" },
];

export const PUBLIC_PAGES = [
  { name: "Home", text: "Thrusts, personnel, activities and processes at a glance" },
  { name: "Services", text: "The proposal, MOA and implementation workflow explained" },
  { name: "Reports", text: "Published reports and accomplishments" },
  { name: "Achievements", text: "Results, highlights and documentation" },
];

// --------------------------------------------------------------- conveniences
export const SAFETY_FEATURES = [
  { title: "Verified accounts", text: "New users confirm their email before they can get in." },
  { title: "Self-serve password reset", text: "Reset links arrive by email; no administrator needed." },
  { title: "Idle auto-logout", text: "Walk away and the system signs you out to protect your work." },
  { title: "Login protection", text: "Repeated failed sign-in attempts are locked down automatically." },
  { title: "Maintenance mode", text: "Admins can show a courteous 'back soon' page during updates." },
  { title: "Role-based dashboards", text: "Each login lands on the queue and cards that matter to that role." },
  { title: "Secure file storage", text: "Uploads live in protected cloud storage with in-browser previews." },
  { title: "Visible progress", text: "Progress rings and status badges show where every document stands." },
];

export const LIFECYCLE_LANES = [
  { phase: "Proposal", tint: "green", steps: ["Drafting", "Submitted for Review", "In Review", "Approved / Claiming"] },
  { phase: "MOA", tint: "maroon", steps: ["Drafting", "Legal Review", "Certification Ready", "MOA Completed"] },
  { phase: "Implementation", tint: "yellow", steps: ["Activity", "Reports", "Monitoring", "Final Documentation"] },
];
