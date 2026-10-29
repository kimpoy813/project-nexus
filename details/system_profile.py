"""Single source of truth for the system's own profile, architecture, and help data.

Facts about NExUS itself — what the acronym stands for, who built it, which
office runs it, what technology stack it runs on, how its three workflow
phases and seven institutional roles fit together, and what every tracker
stage means — are kept in code rather than in the page database so they stay
accurate, version-controlled, and synchronized with ``proposals.models`` and
``accounts.models``.
"""

from django.db.models import Q

SYSTEM_NAME = "NExUS"
SYSTEM_LONG_NAME = "Networked Extension Unified System"
SYSTEM_TAGLINE = (
    "The Extension Services portal of Ilocos Sur Polytechnic State College"
)

#: Credit shown on the About page. Kept structured so templates can render the
#: name, role, and optional link cleanly without scraping HTML.
DEVELOPER = {
    "name": "Kim Dave Rafael",
    "role": "System developer",
}

INSTITUTION = "Ilocos Sur Polytechnic State College (ISPSC)"
OFFICE = "ISPSC-RDEI Extension Office"

#: Major pieces the application actually runs on (checked against
#: ``requirements.txt``, ``conf/settings.py``, and ``templates/base.html``).
#: Kept as ``(label, value)`` 2-tuples so callers and tests can unpack cleanly.
STACK = (
    ("Framework", "Django 5 · Python 3.12"),
    ("Database", "PostgreSQL (SQLite for local work)"),
    ("Files", "Supabase Storage, local storage in development"),
    ("Interface", "Tailwind CSS · Alpine.js"),
    ("Documents", "python-docx · openpyxl"),
    ("Security", "Django Axes · Role RBAC · Idle-session guard"),
    ("Serving", "Gunicorn · WhiteNoise"),
)

STACK_NOTES = {
    "Framework": "Server-rendered views, role-scoped permissions, and transactional state transitions.",
    "Database": "Relational core storing proposals, review rounds, audit logs, targets, and CMS blocks.",
    "Files": "Versioned document vault streaming signed PDFs, DOCX drafts, Excel sheets, and photos.",
    "Interface": "Precompiled utility styles, progressive disclosure interactions, and accessible contrast.",
    "Documents": "Automated Memorandum of Agreement (.docx) assembly and structured Excel workbooks.",
    "Security": "Email verification, brute-force protection, campus/role scoping, and 10-minute idle logout.",
    "Serving": "Production WSGI application serving with compressed, cache-busted static assets.",
}

#: Three-layer architectural blueprint rendered on the About page.
ARCHITECTURE_LAYERS = (
    {
        "tier": "Layer 01",
        "name": "Experience & Role Workspaces",
        "summary": "Dedicated interfaces tailored to public visitors, faculty proponents, reviewers, office staff, and administrators.",
        "accent": "primary",
        "icon_path": "M4 6.5L12 3l8 3.5-8 3.5-8-3.5zm0 5.5l8 3.5 8-3.5M4 17.5L12 21l8-3.5",
        "nodes": (
            "Public Transparency Portal (Home, Services, Programs, Gallery, Help)",
            "7 Role-Scoped Dashboards with Speedometer Gauge & Table Views",
            "Guided 20-Step Collaborative Proposal Wizard with Autosave & Presence",
            "No-Code Admin Studios (Wizard Steps, Processes, Templates, CMS Pages)",
        ),
    },
    {
        "tier": "Layer 02",
        "name": "Workflow, Review & Document Engine",
        "summary": "Enforces institutional rules across the three lifecycle trackers while generating and versioning official paperwork.",
        "accent": "secondary",
        "icon_path": "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
        "nodes": (
            "Weighted 3-Phase State Machine (Proposal, MOA, Implementation)",
            "Multi-Round Evaluation, Section Comments & Revision Unlock Loop",
            "Guided MOA (.docx) Builder, Excel Template Sync & Document Release",
            "Quarterly Accomplishment Windows, Annual Targets & Audit Trails",
        ),
    },
    {
        "tier": "Layer 03",
        "name": "Unified Data & Storage Vault",
        "summary": "Single source of truth where internal workflow records power public reporting without duplicate manual entry.",
        "accent": "gold",
        "icon_path": "M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4-3.582 4-8 4-8-1.79-8-4zm0 5c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7",
        "nodes": (
            "PostgreSQL Relational Schema (Proposals, Proponents, Rounds, Campuses)",
            "Proposal Storage Vault (Supabase S3 / Media Streaming via Django)",
            "Historical Legacy Proposal Archive Unified with Live Approved Work",
            "Session Guard, Brute-Force Lockout (Axes) & Verification Tokens",
        ),
    },
)

#: End-to-end record pipeline showing how one proposal travels through NExUS.
LIFECYCLE_PIPELINE = (
    {
        "step": "01",
        "title": "Guided Authoring",
        "badge": "Wizard + Co-Proponents",
        "icon_path": "M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z",
        "detail": "Faculty proponents draft across structured wizard steps, invite co-proponents, and attach Work Plan, Gantt, Funding, and research files.",
    },
    {
        "step": "02",
        "title": "Multi-Tier Review",
        "badge": "Coordinators & Evaluators",
        "icon_path": "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
        "detail": "Coordinators, assigned evaluators, and the Director record section-by-section feedback; revisions reopen editing cleanly across rounds.",
    },
    {
        "step": "03",
        "title": "Release & MOA",
        "badge": "Official Paperwork",
        "icon_path": "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
        "detail": "Signed proposals are uploaded, official award/endorsement documents are released, and partner MOAs move from guided .docx draft to completion.",
    },
    {
        "step": "04",
        "title": "Implementation",
        "badge": "Field Execution",
        "icon_path": "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z",
        "detail": "Teams carry out approved activities, file post-activity and progress reports, complete monitoring & evaluation, and upload captioned photos.",
    },
    {
        "step": "05",
        "title": "Public Transparency",
        "badge": "Zero Re-Entry",
        "icon_path": "M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9",
        "detail": "Approved proposals and legacy records automatically populate the Programs directory, while terminal report photos appear in the public Gallery.",
    },
)

#: The seven institutional roles defined in ``accounts.models.Profile.ROLE_CHOICES``.
ROLE_ECOSYSTEM = (
    {
        "code": "FACULTY",
        "name": "Faculty / Proponent",
        "group": "Authoring & Delivery",
        "icon_path": "M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",
        "summary": "Creates extension proposals, collaborates as lead or co-proponent, uploads signed copies and MOA files, and submits implementation & terminal reports.",
        "touchpoints": ("20-Step Wizard", "MOA Drafting", "Terminal Reports & Photos"),
    },
    {
        "code": "DEPARTMENT_COORDINATOR",
        "name": "Department Coordinator",
        "group": "Unit Coordination",
        "icon_path": "M4 6h16M4 12h16M4 18h10",
        "summary": "Conducts department-level proposal review, coordinates department extension initiatives, submits quarterly accomplishment reports, and can author proposals.",
        "touchpoints": ("Department Review", "Quarterly Reports", "Proposal Authoring"),
    },
    {
        "code": "CAMPUS_COORDINATOR",
        "name": "Campus Coordinator",
        "group": "Campus Oversight",
        "icon_path": "M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6",
        "summary": "Oversees extension proposals across a campus, performs campus-level review, tracks campus accomplishments against annual targets, and supports proponents.",
        "touchpoints": ("Campus Review", "Campus KPI Tracking", "Accomplishment Filing"),
    },
    {
        "code": "EVALUATOR",
        "name": "Evaluator",
        "group": "Technical Review",
        "icon_path": "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
        "summary": "Assigned to submitted proposals during review rounds to inspect each wizard step and record structured section-anchored comments and recommendations.",
        "touchpoints": ("Assigned Review Queue", "Section Comments", "Round Assessments"),
    },
    {
        "code": "STAFF",
        "name": "Extension Office Staff",
        "group": "Office Operations",
        "icon_path": "M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
        "summary": "Manages daily intake queues, verifies signed submissions, releases official award and endorsement documents, advances MOA & implementation stages, and opens report windows.",
        "touchpoints": ("Document Release", "MOA & Implementation", "Quarterly Requests"),
    },
    {
        "code": "DIRECTOR",
        "name": "Extension Director",
        "group": "Institutional Approval",
        "icon_path": "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
        "summary": "Assigns evaluators, issues review summaries, grants institutional approval, and monitors institution-wide extension performance across all campuses.",
        "touchpoints": ("Evaluator Assignment", "Final Approval", "Executive Analytics"),
    },
    {
        "code": "ADMIN",
        "name": "System Administrator",
        "group": "Governance & Builders",
        "icon_path": "M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4",
        "summary": "Configures accounts, roles, campuses/colleges/departments, wizard steps, workflow phase weights, processes, templates, signatories, legacy uploads, and public CMS pages.",
        "touchpoints": ("Wizard & Process Builders", "Accounts & Roles", "Public Page CMS"),
    },
)

#: Core capability modules highlighted on the About page. Every ``href`` must
#: resolve with HTTP 200 for anonymous visitors.
CAPABILITY_MODULES = (
    {
        "title": "Guided 20-Step Proposal Wizard",
        "icon_path": "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01",
        "summary": "Structured step-by-step authoring for Programs, Projects, and Activities across Extension Proposal and Training Design formats, with co-proponent presence and autosave.",
        "link_label": "Explore workflow on Services",
        "link_href": "/proposals/",
    },
    {
        "title": "Multi-Round Review & Revision",
        "icon_path": "M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z",
        "summary": "Department, campus, evaluator, and director reviews anchor feedback directly to proposal sections, compile comment summaries, and track every revision round.",
        "link_label": "Read status guide in Help",
        "link_href": "/help/",
    },
    {
        "title": "Guided MOA & Document Vault",
        "icon_path": "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
        "summary": "Generates formatted .docx Memoranda of Agreement from guided inputs, manages legal review stages, and stores signed proposals alongside released office documents.",
        "link_label": "Document rules in Help",
        "link_href": "/help/",
    },
    {
        "title": "Implementation & Progress Gauges",
        "icon_path": "M13 10V3L4 14h7v7l9-11h-7z",
        "summary": "Tracks field implementation, post-activity and progress reports, monitoring & evaluation, and weighted completion rings across every role dashboard.",
        "link_label": "See phase weights on Services",
        "link_href": "/proposals/",
    },
    {
        "title": "Quarterly Reports & Campus Targets",
        "icon_path": "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
        "summary": "Extension Staff open quarterly reporting windows while coordinators file accomplishments measured directly against annual institutional target indicators.",
        "link_label": "Learn how reporting works",
        "link_href": "/help/",
    },
    {
        "title": "Self-Updating Public Directory & Gallery",
        "icon_path": "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
        "summary": "Approved proposals, imported legacy records, and captioned terminal-report photographs automatically power the public Programs directory and Gallery.",
        "link_label": "Browse Extension Programs",
        "link_href": "/programs/",
    },
)

#: Detailed human explanations for each ProposalStatus code (Phase 01).
_PROPOSAL_STAGE_META = {
    "DRAFTING": {
        "editable": True,
        "actor": "Proponent & Co-Proponents",
        "meaning": "You are filling in the 20-step wizard. All steps can be edited freely, autosaved, and worked on with co-proponents.",
    },
    "SUBMITTED_FOR_REVIEW": {
        "editable": False,
        "actor": "Extension Office / Coordinators",
        "meaning": "You sent the proposal in. Wizard fields lock so reviewers evaluate a stable version while intake routes it.",
    },
    "IN_REVIEW": {
        "editable": False,
        "actor": "Coordinators, Evaluators & Director",
        "meaning": "Coordinators, assigned evaluators, and the Director are inspecting sections and recording comments.",
    },
    "REVIEW_SUMMARY_ISSUED": {
        "editable": False,
        "actor": "Director / Extension Office",
        "meaning": "Feedback from reviewers has been compiled into a structured Comment Summary on your proposal record.",
    },
    "FOR_REVISION": {
        "editable": True,
        "actor": "Proponent & Co-Proponents",
        "meaning": "Changes were requested. Editing reopens so you can address each section comment and resubmit for the next round.",
    },
    "READY_FOR_PRINTING": {
        "editable": False,
        "actor": "Proponent",
        "meaning": "Content passed review. Generate and print the formatted proposal so institutional signatories can sign it.",
    },
    "FOR_SUBMISSION_AND_UPLOAD": {
        "editable": False,
        "actor": "Proponent & Extension Staff",
        "meaning": "Submit the signed physical copy to the Extension Office and upload the scanned signed PDF to your record.",
    },
    "APPROVED": {
        "editable": False,
        "actor": "Extension Staff & Proponent",
        "meaning": "The proposal is approved and official documents (Letter of Award, Endorsement, Extension Agreement) are released for claiming.",
    },
    "COMPLETED": {
        "editable": False,
        "actor": "System / Extension Office",
        "meaning": "The proposal phase is complete, published to the Programs directory, and handed off to MOA or Implementation.",
    },
}

#: Detailed human explanations for each MOAStatus code (Phase 02).
_MOA_STAGE_META = {
    "NOT_REQUIRED": {
        "actor": "Extension Staff",
        "meaning": "No external partner agreement is needed; the MOA weight is automatically redistributed to Proposal and Implementation.",
    },
    "NOT_STARTED": {
        "actor": "Proponent",
        "meaning": "Waiting for proposal approval before Memorandum of Agreement preparation begins.",
    },
    "DRAFT": {
        "actor": "Proponent",
        "meaning": "Fill out the 4-step guided MOA wizard to generate a formatted institutional .docx draft and submit it.",
    },
    "LEGAL_REVIEW": {
        "actor": "Legal / Extension Office",
        "meaning": "Partner obligations, dates, signatories, and terms are undergoing institutional and legal review.",
    },
    "FOR_REVISION": {
        "actor": "Proponent",
        "meaning": "Adjustments were requested on the draft MOA; update the guided form or upload the revised document.",
    },
    "CERTIFICATION_READY": {
        "actor": "Extension Staff",
        "meaning": "Cleared legal review and ready for institutional certification and endorsement.",
    },
    "AGENDA_AND_PRESENTATION": {
        "actor": "Extension Office / Board",
        "meaning": "Scheduled for agenda brief, board presentation, and executive signing with the partner organization.",
    },
    "COMPLETED": {
        "actor": "Extension Staff & Proponent",
        "meaning": "Signed Memorandum of Agreement is archived in Proposal Storage and Phase 03 (Implementation) opens.",
    },
}

#: Detailed human explanations for each ImplementationStatus code (Phase 03).
_IMPLEMENTATION_STAGE_META = {
    "NOT_STARTED": {
        "actor": "System",
        "meaning": "Waiting for the Proposal (and MOA, when required) to finish before field execution begins.",
    },
    "PREPARATION": {
        "actor": "Proponent Team",
        "meaning": "Pre-activity logistics and coordination stage (retained for earlier records prior to field launch).",
    },
    "IMPLEMENTATION": {
        "actor": "Proponent Team",
        "meaning": "Approved extension activity is actively being delivered with the partner community or beneficiaries.",
    },
    "POST_ACTIVITY_REPORT": {
        "actor": "Proponent",
        "meaning": "Upload the Post-Extension Activity Report documenting attendance, delivery outputs, and immediate results.",
    },
    "TERMINAL_REPORT": {
        "actor": "Proponent",
        "meaning": "Submit the Extension Progress / Terminal Report and captioned activity photographs.",
    },
    "MONITORING": {
        "actor": "Extension Office",
        "meaning": "Extension Staff and coordinators conduct monitoring, outcome verification, and evaluation.",
    },
    "REVISION": {
        "actor": "Proponent",
        "meaning": "Respond to evaluation findings via the Summary of Comments and Actions Taken.",
    },
    "COMPLETED": {
        "actor": "Extension Office",
        "meaning": "Final evaluation and documentation are complete; overall status becomes Extension Completed and photos publish to Gallery.",
    },
}

#: Conditional document rules in the 20-step Proposal Wizard, synchronized with
#: ``proposals/views/wizard.py`` and Steps 17–20.
CONDITIONAL_UPLOAD_MATRIX = (
    {
        "classification": "Research-based (Faculty)",
        "code": "RESEARCH_FACULTY",
        "work_plan_budget": "Required (Steps 17–18 Excel uploads)",
        "research_files": "Required on Step 19: Research Abstract + Complete Research (or Utility Model No. & Certificate)",
        "completion_cert": "Required on Step 20: Certificate of Completion",
    },
    {
        "classification": "Research-based (Student)",
        "code": "RESEARCH_STUDENT",
        "work_plan_budget": "Required (Steps 17–18 Excel uploads)",
        "research_files": "Required on Step 19: Research Abstract + Complete Research (or Utility Model No. & Certificate)",
        "completion_cert": "Not required (Step 20 skipped automatically)",
    },
    {
        "classification": "Request-based",
        "code": "REQUEST_BASED",
        "work_plan_budget": "Required (Steps 17–18 Excel uploads)",
        "research_files": "Not required (research-only fields hidden)",
        "completion_cert": "Not required",
    },
    {
        "classification": "Community-based",
        "code": "COMMUNITY_BASED",
        "work_plan_budget": "Required (Steps 17–18 Excel uploads)",
        "research_files": "Not required (research-only fields hidden)",
        "completion_cert": "Not required",
    },
)

#: Categorized Frequently Asked Questions rendered on ``/help/``.
HELP_FAQS = (
    {
        "id": "faq-locked-proposal",
        "category": "Review & Revisions",
        "question": "Why can't I edit my proposal right now?",
        "answer": (
            "Proposals are editable only when their Proposal Status is Drafting or For Revision. "
            "Once you click Submit for Review, wizard fields lock so coordinators, evaluators, and "
            "the Director all inspect the exact same snapshot. If reviewers request changes, the "
            "status switches to For Revision and editing unlocks automatically."
        ),
    },
    {
        "id": "faq-collaborators",
        "category": "Proposal Wizard",
        "question": "How do co-proponents collaborate on the same proposal?",
        "answer": (
            "On Step 3 (Proponents) of the Proposal Wizard, search and add registered faculty or "
            "staff colleagues as co-proponents. Added co-proponents see the shared proposal on their "
            "own dashboard, can edit unlocked wizard steps, and see live presence indicators showing "
            "which step each teammate is currently viewing or editing."
        ),
    },
    {
        "id": "faq-research-uploads",
        "category": "Proposal Wizard",
        "question": "What is the difference between Research-based (Faculty) and Research-based (Student) uploads?",
        "answer": (
            "Both Research-based (Faculty) and Research-based (Student) proposals require uploading "
            "the Research Abstract and Complete Research on Step 19 (unless anchored on a Utility Model, "
            "which asks for the Registration Number and Certificate). Only Research-based (Faculty) "
            "proposals require uploading the Certificate of Completion on Step 20."
        ),
    },
    {
        "id": "faq-excel-templates",
        "category": "Proposal Wizard",
        "question": "Where do I download the Work Plan, Gantt Chart, and Funding / Budget Excel templates?",
        "answer": (
            "Download links are built right into Step 17 (Work and Financial Plan / Gantt Chart) and "
            "Step 18 (Funding / Budgetary Requirements) of the Proposal Wizard, and are also listed in "
            "the Template Library on the public Services page. Fill out the official workbook without "
            "renaming its structure and upload the saved .xlsx file back into the step."
        ),
    },
    {
        "id": "faq-for-revision",
        "category": "Review & Revisions",
        "question": "What happens when my proposal is marked For Revision?",
        "answer": (
            "Open your proposal's Comment Summary to read the compiled feedback anchored to specific "
            "wizard steps. Open the wizard, update the flagged sections, save your changes, and submit "
            "again. NExUS preserves previous review rounds so reviewers can compare your updates against "
            "earlier feedback."
        ),
    },
    {
        "id": "faq-moa-not-required",
        "category": "MOA & Documents",
        "question": "What if my extension activity does not need a Memorandum of Agreement (MOA)?",
        "answer": (
            "When an activity has no external partner agreement, Extension Staff mark the MOA tracker "
            "as Not Required. NExUS automatically redistributes the MOA percentage weight across the "
            "Proposal and Implementation phases so your overall completion gauge still reaches 100%."
        ),
    },
    {
        "id": "faq-guided-moa",
        "category": "MOA & Documents",
        "question": "How does the guided MOA generator work?",
        "answer": (
            "Once your proposal reaches the MOA phase, open the MOA tracker to fill in the 4-step "
            "guided form covering partner details, project purpose, mutual obligations, and signatories. "
            "NExUS compiles your entries into a formatted .docx Memorandum of Agreement that you can "
            "download, review, and re-generate if revisions are needed."
        ),
    },
    {
        "id": "faq-progress-gauge",
        "category": "Implementation & Reports",
        "question": "How is the overall percentage gauge on my dashboard calculated?",
        "answer": (
            "Overall progress combines the three workflow phases using the Extension Office's configured "
            "weights (by default: Proposal 50%, MOA 20%, Implementation 30%). Each tracker records the "
            "highest milestone reached so temporary revision loops do not erase your earlier progress."
        ),
    },
    {
        "id": "faq-dashboard-views",
        "category": "Implementation & Reports",
        "question": "Can I switch my dashboard between Gauge Cards and a compact Table View?",
        "answer": (
            "Yes. Proposal panels on role dashboards include a view toggle in the top-right corner "
            "that switches between visual speedometer gauge cards and a dense sortable table, and "
            "remembers your preference in your browser."
        ),
    },
    {
        "id": "faq-proposal-storage",
        "category": "MOA & Documents",
        "question": "Where can I find all uploaded files and released office documents for my proposal?",
        "answer": (
            "Open Proposal Storage from your proposal record. It groups every attachment in one place — "
            "wizard uploads, signed proposal versions, released documents (Letter of Award, Endorsement "
            "for Approval, Extension Agreement), MOA drafts, implementation reports, and activity photos."
        ),
    },
    {
        "id": "faq-public-directory-gallery",
        "category": "Implementation & Reports",
        "question": "How do approved programs and photos appear on the public Programs and Gallery pages?",
        "answer": (
            "There is no separate form to fill out. Approved proposals (plus historical records imported "
            "by Admins via Legacy Upload) automatically populate the public Programs directory, while "
            "captioned photos uploaded during final documentation appear in the public Gallery."
        ),
    },
    {
        "id": "faq-verify-email",
        "category": "Accounts & Access",
        "question": "My email verification link expired or didn't arrive. How do I get a new one?",
        "answer": (
            "Go to the Sign In page and attempt to sign in with your registered email and password, "
            "or use the resend verification option shown on screen. NExUS will send a fresh verification "
            "link; check your spam or junk folder if it does not appear within a minute."
        ),
    },
    {
        "id": "faq-idle-timeout",
        "category": "Accounts & Access",
        "question": "Why did NExUS sign me out after a period of inactivity?",
        "answer": (
            "To protect institutional records on shared computers, NExUS automatically ends sessions "
            "after 10 minutes of inactivity. A warning banner counts down the final 60 seconds — click "
            "Stay logged in (or continue working in any open NExUS tab) to extend your session immediately."
        ),
    },
    {
        "id": "faq-role-campus-change",
        "category": "Accounts & Access",
        "question": "How do I update my campus, college, department, or assigned system role?",
        "answer": (
            "New accounts start as Faculty so proponents can draft right away. Campus, college, "
            "department assignments, and elevated roles (Coordinator, Evaluator, Staff, Director, Admin) "
            "are managed by System Administrators through the Extension Office."
        ),
    },
)


def live_metrics():
    """Query lightweight live counts for the About & Help visual cards."""
    from accounts.models import Campus, Profile
    from details.models import ProposalWizardStepConfig, WorkflowPhase
    from details.program_directory import APPROVED_PROPOSAL_STATUSES
    from proposals.models import DocumentationPhoto, Proposal

    wizard_steps = ProposalWizardStepConfig.objects.filter(is_visible=True).count() or 20
    phases_count = WorkflowPhase.objects.filter(is_visible=True).count() or 3
    roles_count = len(Profile.ROLE_CHOICES)
    campuses_count = Campus.objects.count()
    published_programs = Proposal.objects.filter(
        Q(is_legacy=True) | Q(proposal_status__in=APPROVED_PROPOSAL_STATUSES)
    ).count()
    gallery_photos = DocumentationPhoto.objects.count()

    return {
        "wizard_steps": wizard_steps,
        "phases_count": phases_count,
        "roles_count": roles_count,
        "campuses_count": campuses_count,
        "published_programs": published_programs,
        "gallery_photos": gallery_photos,
    }


def workflow_phases_overview():
    """Return visible workflow phases enriched with model-backed status ladders."""
    from details.models import WorkflowPhase
    from proposals.models import Proposal

    phase_configs = {
        "proposal": (
            Proposal.ProposalStatus.choices,
            Proposal.PROPOSAL_PROGRESS_MAP,
            _PROPOSAL_STAGE_META,
        ),
        "moa": (
            Proposal.MOAStatus.choices,
            Proposal.MOA_PROGRESS_MAP,
            _MOA_STAGE_META,
        ),
        "implementation": (
            Proposal.ImplementationStatus.choices,
            Proposal.IMPLEMENTATION_PROGRESS_MAP,
            _IMPLEMENTATION_STAGE_META,
        ),
    }

    phases = []
    weight_total = 0
    for phase in WorkflowPhase.ordered_visible():
        weight_total += phase.weight_percent
        choices, progress_map, meta_map = phase_configs.get(phase.key, ((), {}, {}))
        statuses = []
        for code, label in choices:
            meta = meta_map.get(code, {})
            statuses.append(
                {
                    "code": code,
                    "label": label,
                    "progress": progress_map.get(code, 0),
                    "editable": meta.get("editable"),
                    "actor": meta.get("actor", "Extension Office"),
                    "meaning": meta.get("meaning", ""),
                }
            )
        phases.append(
            {
                "key": phase.key,
                "label": phase.label,
                "summary": phase.summary,
                "weight_label": phase.weight_label,
                "weight_percent": phase.weight_percent,
                "ring_label": f"{phase.label}: {phase.weight_percent}% of overall progress",
                "statuses": statuses,
            }
        )
    return phases, weight_total


def profile():
    """The About page's "at a glance" card data."""
    from accounts.models import SiteConfiguration

    try:
        contact_email = SiteConfiguration.get_solo().contact_email
    except Exception:  # un-migrated database, or settings not ready
        contact_email = ""

    return {
        "name": SYSTEM_NAME,
        "system_name": SYSTEM_NAME,
        "long_name": SYSTEM_LONG_NAME,
        "system_long_name": SYSTEM_LONG_NAME,
        "tagline": SYSTEM_TAGLINE,
        "developer": dict(DEVELOPER),
        "institution": INSTITUTION,
        "office": OFFICE,
        "stack": [
            {"label": label, "value": value, "note": STACK_NOTES.get(label, "")}
            for label, value in STACK
        ],
        "contact_email": contact_email,
        "metrics": live_metrics(),
    }


def about_context():
    """Extra template context for the About page visualizations."""
    phases, weight_total = workflow_phases_overview()
    return {
        "system_profile": profile(),
        "architecture_layers": ARCHITECTURE_LAYERS,
        "lifecycle_pipeline": LIFECYCLE_PIPELINE,
        "role_ecosystem": ROLE_ECOSYSTEM,
        "capability_modules": CAPABILITY_MODULES,
        "workflow_phases": phases,
        "workflow_weight_total": weight_total,
    }


def help_context():
    """Structured workflow, upload rules, role guide, and FAQ data for ``/help/``."""
    from proposals.models import Proposal

    phases, weight_total = workflow_phases_overview()
    phase_by_key = {p["key"]: p for p in phases}

    # Build proposal statuses directly from Proposal.ProposalStatus.choices so
    # every status choice in the model is guaranteed to appear on /help/.
    proposal_statuses = [
        {
            "code": code,
            "label": label,
            "progress": Proposal.PROPOSAL_PROGRESS_MAP.get(code, 0),
            "editable": _PROPOSAL_STAGE_META.get(code, {}).get("editable", False),
            "actor": _PROPOSAL_STAGE_META.get(code, {}).get("actor", "Extension Office"),
            "meaning": _PROPOSAL_STAGE_META.get(code, {}).get("meaning", ""),
        }
        for code, label in Proposal.ProposalStatus.choices
    ]
    moa_statuses = [
        {
            "code": code,
            "label": label,
            "progress": Proposal.MOA_PROGRESS_MAP.get(code, 0),
            "actor": _MOA_STAGE_META.get(code, {}).get("actor", "Extension Office"),
            "meaning": _MOA_STAGE_META.get(code, {}).get("meaning", ""),
        }
        for code, label in Proposal.MOAStatus.choices
    ]
    implementation_statuses = [
        {
            "code": code,
            "label": label,
            "progress": Proposal.IMPLEMENTATION_PROGRESS_MAP.get(code, 0),
            "actor": _IMPLEMENTATION_STAGE_META.get(code, {}).get("actor", "Extension Office"),
            "meaning": _IMPLEMENTATION_STAGE_META.get(code, {}).get("meaning", ""),
        }
        for code, label in Proposal.ImplementationStatus.choices
    ]

    faq_categories = []
    for item in HELP_FAQS:
        if item["category"] not in faq_categories:
            faq_categories.append(item["category"])

    return {
        "metrics": live_metrics(),
        "workflow_phases": phases,
        "workflow_weight_total": weight_total,
        "phase_by_key": phase_by_key,
        "proposal_statuses": proposal_statuses,
        "moa_statuses": moa_statuses,
        "implementation_statuses": implementation_statuses,
        "conditional_uploads": CONDITIONAL_UPLOAD_MATRIX,
        "role_ecosystem": ROLE_ECOSYSTEM,
        "faqs": HELP_FAQS,
        "faq_categories": faq_categories,
    }
