"""What NExUS is made of — one place to update the system's own profile and help data.

Facts about NExUS itself — the developer's name, the office it was built for,
the stack it runs on, the workflow statuses in ``proposals.models``, and the
common help questions — live here in code so they stay accurate and aligned
with the models.
"""

SYSTEM_NAME = "NExUS"
SYSTEM_LONG_NAME = "Networked Extension Unified System"
SYSTEM_TAGLINE = "Extension work, from proposal to terminal report, in one system."

DEVELOPER = {
    "name": "Kim Dave Rafael",
    "role": "Developer",
}

INSTITUTION = "Ilocos Sur Polytechnic State College (ISPSC)"
OFFICE = "ISPSC-RDEI Extension Office"

#: Dependencies and services the application actually runs on.
STACK = (
    ("Framework", "Django 5 · Python 3.12"),
    ("Database", "PostgreSQL (SQLite for local work)"),
    ("Files", "Supabase Storage, local storage in development"),
    ("Interface", "Tailwind CSS · Alpine.js"),
    ("Documents", "python-docx · openpyxl"),
    ("Serving", "Gunicorn · WhiteNoise"),
)

_PROPOSAL_STAGE_MEANING = {
    "DRAFTING": (
        "Still yours to write. You and your co-proponents can edit steps, "
        "autosave drafts, and upload templates; nobody outside your team sees it yet."
    ),
    "SUBMITTED_FOR_REVIEW": (
        "Sent to the Extension Office. Wizard editing locks so reviewers read "
        "the exact version you submitted."
    ),
    "IN_REVIEW": (
        "Department and campus coordinators, assigned evaluators, and the "
        "Director are reviewing sections and recording comments."
    ),
    "REVIEW_SUMMARY_ISSUED": (
        "Reviewer comments have been compiled into a Comment Summary on your "
        "proposal record."
    ),
    "FOR_REVISION": (
        "Returned with comments to address. Editing reopens so you can update "
        "the flagged steps and resubmit."
    ),
    "READY_FOR_PRINTING": (
        "Content passed review. Generate the formatted document and print it "
        "for institutional signatures."
    ),
    "FOR_SUBMISSION_AND_UPLOAD": (
        "Submit the signed copies to the Extension Office and upload the "
        "scanned signed PDF."
    ),
    "APPROVED": (
        "Approved. Staff release the Letter of Award, Endorsement for Approval, "
        "and Extension Agreement for claiming."
    ),
    "COMPLETED": (
        "Proposal phase complete. The approved program appears in Programs and "
        "work continues in the MOA and Implementation trackers."
    ),
}

_MOA_STAGE_MEANING = {
    "NOT_REQUIRED": (
        "No partner agreement is needed. Its progress weight is automatically "
        "shared across Proposal and Implementation."
    ),
    "NOT_STARTED": "Waiting for proposal approval before MOA drafting begins.",
    "DRAFT": (
        "Complete the 4-step guided MOA form to generate a formatted .docx "
        "agreement draft."
    ),
    "LEGAL_REVIEW": "Partner terms, dates, and obligations are under review.",
    "FOR_REVISION": "Returned for adjustments to the MOA form or uploaded draft.",
    "CERTIFICATION_READY": "Cleared review and ready for institutional certification.",
    "AGENDA_AND_PRESENTATION": "Scheduled for agenda brief, presentation, and signing.",
    "COMPLETED": "Signed MOA is stored and Implementation opens.",
}

_IMPLEMENTATION_STAGE_MEANING = {
    "NOT_STARTED": "Waiting for Proposal (and MOA, if required) to finish.",
    "PREPARATION": "Pre-activity preparation (retained for earlier records).",
    "IMPLEMENTATION": "Approved extension activity is underway with beneficiaries.",
    "POST_ACTIVITY_REPORT": "Submit the Post-Extension Activity Report.",
    "TERMINAL_REPORT": "Submit the Extension Progress / Terminal Report and activity photos.",
    "MONITORING": "Extension Office conducts monitoring and evaluation.",
    "REVISION": "Submit the Summary of Comments and Actions Taken if requested.",
    "COMPLETED": (
        "Final evaluation and documentation are complete; captioned photos "
        "appear in the Gallery."
    ),
}

CONDITIONAL_UPLOAD_MATRIX = (
    {
        "classification": "Research-based (Faculty)",
        "code": "RESEARCH_FACULTY",
        "uploads": (
            "Work Plan, Gantt Chart & Budget (.xlsx on Steps 17–18); "
            "Research Abstract + Complete Research on Step 19 (or Utility Model "
            "number & certificate); Certificate of Completion on Step 20."
        ),
    },
    {
        "classification": "Research-based (Student)",
        "code": "RESEARCH_STUDENT",
        "uploads": (
            "Work Plan, Gantt Chart & Budget (.xlsx on Steps 17–18); "
            "Research Abstract + Complete Research on Step 19 (or Utility Model "
            "number & certificate). Step 20 Certificate of Completion is not required."
        ),
    },
    {
        "classification": "Request-based / Community-based",
        "code": "COMMUNITY_BASED",
        "uploads": (
            "Work Plan, Gantt Chart & Budget (.xlsx on Steps 17–18). "
            "Research-only upload steps are hidden automatically."
        ),
    },
)

ROLES_SUMMARY = (
    ("Faculty", "Author proposals, collaborate as co-proponents, generate MOAs, and file activity & terminal reports."),
    ("Coordinators", "Department and Campus Coordinators review unit proposals and submit quarterly accomplishment reports."),
    ("Evaluators", "Assigned during review rounds to inspect wizard steps and write section comments."),
    ("Staff", "Manage office queues, release award/endorsement documents, track MOAs & implementation, and open quarterly report windows."),
    ("Director", "Assigns evaluators, issues review summaries, approves proposals, and oversees institutional targets."),
    ("Admin", "Manages accounts, roles, campuses/departments, wizard steps, processes, templates, legacy records, and public page content."),
)

HELP_FAQS = (
    {
        "id": "faq-locked-proposal",
        "question": "Why can't I edit my proposal right now?",
        "answer": (
            "Wizard fields are editable only in Drafting and For Revision. "
            "While a proposal is Submitted for Review or In Review, fields lock "
            "so reviewers read a single stable version. If changes are needed, "
            "status moves to For Revision and editing reopens."
        ),
    },
    {
        "id": "faq-collaborators",
        "question": "How do co-proponents work on the same proposal?",
        "answer": (
            "Add registered colleagues on Step 3 (Proponents). Everyone listed "
            "sees the proposal on their dashboard, can edit unlocked steps, and "
            "sees which step teammates are currently viewing."
        ),
    },
    {
        "id": "faq-research-uploads",
        "question": "Which research files are required on Steps 19 and 20?",
        "answer": (
            "Both Research-based (Faculty) and Research-based (Student) proposals "
            "require the Research Abstract and Complete Research on Step 19 "
            "(unless using a Utility Model). Only Research-based (Faculty) "
            "requires the Certificate of Completion on Step 20."
        ),
    },
    {
        "id": "faq-templates",
        "question": "Where do I get the Work Plan, Gantt Chart, and Budget templates?",
        "answer": (
            "Download the official .xlsx workbooks directly inside Steps 17 and 18 "
            "of the wizard or from the Template Library on the Services page, "
            "complete them, and upload the saved files back into the step."
        ),
    },
    {
        "id": "faq-moa",
        "question": "What if my activity does not require a MOA?",
        "answer": (
            "Staff mark the MOA tracker as Not Required, and NExUS automatically "
            "redistributes that progress share across Proposal and Implementation "
            "so overall completion still totals 100%."
        ),
    },
    {
        "id": "faq-storage",
        "question": "Where are signed proposals, released awards, and MOA files kept?",
        "answer": (
            "Open Proposal Storage from your proposal record to access every "
            "uploaded attachment, signed PDF version, generated .docx MOA, "
            "released office document, and report photo in one place."
        ),
    },
    {
        "id": "faq-public-pages",
        "question": "How do programs and photos appear on Programs and Gallery?",
        "answer": (
            "Approved proposals (plus admin-imported legacy records) appear "
            "automatically in Programs, and captioned photos uploaded with a "
            "terminal report appear automatically in Gallery."
        ),
    },
    {
        "id": "faq-idle-session",
        "question": "Why was I signed out automatically while idle?",
        "answer": (
            "Sessions end after 10 minutes of inactivity to protect shared "
            "computers. A banner warns you during the final 60 seconds — click "
            "Stay logged in to keep working."
        ),
    },
)


def workflow_phases_overview():
    """Visible workflow phases with their status lists and weights."""
    from details.models import WorkflowPhase
    from proposals.models import Proposal

    phase_configs = {
        "proposal": (
            Proposal.ProposalStatus.choices,
            Proposal.PROPOSAL_PROGRESS_MAP,
            _PROPOSAL_STAGE_MEANING,
        ),
        "moa": (
            Proposal.MOAStatus.choices,
            Proposal.MOA_PROGRESS_MAP,
            _MOA_STAGE_MEANING,
        ),
        "implementation": (
            Proposal.ImplementationStatus.choices,
            Proposal.IMPLEMENTATION_PROGRESS_MAP,
            _IMPLEMENTATION_STAGE_MEANING,
        ),
    }

    phases = []
    weight_total = 0
    for phase in WorkflowPhase.ordered_visible():
        weight_total += phase.weight_percent
        choices, progress_map, meaning_map = phase_configs.get(phase.key, ((), {}, {}))
        phases.append(
            {
                "key": phase.key,
                "label": phase.label,
                "summary": phase.summary,
                "weight_label": phase.weight_label,
                "weight_percent": phase.weight_percent,
                "ring_label": f"{phase.label}: {phase.weight_percent}% of overall progress",
                "statuses": [
                    {
                        "code": code,
                        "label": label,
                        "progress": progress_map.get(code, 0),
                        "meaning": meaning_map.get(code, ""),
                    }
                    for code, label in choices
                ],
            }
        )
    return phases, weight_total


def profile():
    """The About page's 'at a glance' block data."""
    from accounts.models import SiteConfiguration

    try:
        contact_email = SiteConfiguration.get_solo().contact_email
    except Exception:
        contact_email = ""

    try:
        workflow_phases, workflow_weight_total = workflow_phases_overview()
    except Exception:
        workflow_phases, workflow_weight_total = [], 0

    return {
        "system_name": SYSTEM_NAME,
        "system_long_name": SYSTEM_LONG_NAME,
        "tagline": SYSTEM_TAGLINE,
        "developer": dict(DEVELOPER),
        "institution": INSTITUTION,
        "office": OFFICE,
        "stack": [{"label": label, "value": value} for label, value in STACK],
        "contact_email": contact_email,
        "workflow_phases": workflow_phases,
        "workflow_weight_total": workflow_weight_total,
    }


def help_context():
    """Structured workflow, document rules, roles, and FAQ data for ``/help/``."""
    from proposals.models import Proposal

    phases, weight_total = workflow_phases_overview()
    proposal_statuses = [
        {
            "code": code,
            "label": label,
            "meaning": _PROPOSAL_STAGE_MEANING.get(code, ""),
        }
        for code, label in Proposal.ProposalStatus.choices
    ]
    moa_statuses = [
        {
            "code": code,
            "label": label,
            "meaning": _MOA_STAGE_MEANING.get(code, ""),
        }
        for code, label in Proposal.MOAStatus.choices
    ]
    implementation_statuses = [
        {
            "code": code,
            "label": label,
            "meaning": _IMPLEMENTATION_STAGE_MEANING.get(code, ""),
        }
        for code, label in Proposal.ImplementationStatus.choices
    ]

    return {
        "workflow_phases": phases,
        "workflow_weight_total": weight_total,
        "proposal_statuses": proposal_statuses,
        "moa_statuses": moa_statuses,
        "implementation_statuses": implementation_statuses,
        "conditional_uploads": CONDITIONAL_UPLOAD_MATRIX,
        "roles_summary": ROLES_SUMMARY,
        "faqs": HELP_FAQS,
    }
