"""
Step labels and reference lists shared across the proposal views.
"""

from django.contrib.auth import get_user_model


User = get_user_model()


# Step 1 is answered by every proposal: it is where the extension type is
# chosen, which then decides which form's wizard flow follows.
SHARED_STEP_LABELS = [
    {"no": 1, "title": "Extension Type and Scope", "desc": "Type of extension and proposal scope"},
]

# Research-based (faculty/student) proposals answer the Extension Proposal
# form (static/templates/form1.docx). Steps 2-22 follow its sections I-XVIII,
# plus the office's two research-only uploads.
INITIAL_RESEARCH_STEPS = [
    {"no": 2, "title": "Title", "desc": "Program, project, or activity title"},
    {"no": 3, "title": "Proponents", "desc": "Proponent details and assigned roles"},
    {"no": 4, "title": "Implementing Agency/Unit", "desc": "Office, agency, or unit responsible"},
    {"no": 5, "title": "Collaborators/Beneficiaries", "desc": "Beneficiary count and target group"},
    {"no": 6, "title": "SDGs Covered", "desc": "SDGs covered (check all that apply)"},
    {"no": 7, "title": "ISPSC Extension Agenda", "desc": ""},
    {"no": 8, "title": "Utility Model", "desc": "", "required": False},
    {"no": 9, "title": "Budgetary Requirement", "desc": "Funding source and budget"},
    {"no": 10, "title": "Participants / Proposed Clients", "desc": "Participant profiling and counts"},
    {"no": 11, "title": "Gender Issues / Mandates Addressed", "desc": "Applicable GAD mandates"},
    {"no": 12, "title": "Date and Venue / Extension Site", "desc": "Schedule and implementation site"},
    {"no": 13, "title": "Rationale / Background", "desc": "Context and alignment with SDG / thrust / GAD"},
    {"no": 14, "title": "Significance", "desc": "Importance of the proposed extension"},
    {"no": 15, "title": "Objectives", "desc": "General and specific SMART objectives"},
    {"no": 16, "title": "Methodology / Mechanics", "desc": "Implementation approach"},
    {"no": 17, "title": "Output / Outcome", "desc": "Expected outputs and outcomes"},
    {"no": 18, "title": "Details of Activities", "desc": "Work plan, Gantt chart, and related files"},
    {"no": 19, "title": "Funding Strategy", "desc": "Funding strategy template and related supporting files"},
    {"no": 20, "title": "Monitoring and Evaluation Mechanics", "desc": "M&E mechanics attachment"},
    {"no": 21, "title": "Research Abstract Upload", "desc": "Required for research-based proposals"},
    {"no": 22, "title": "Certificate of Completion Upload", "desc": "Required for research-based proposals"},
]

# Community-based and request-based proposals answer the Extension Training
# Design form (static/templates/FORM 2 TRAINING DESIGN FORM.docx).
INITIAL_TRAINING_STEPS = [
    {"no": 2, "title": "Title", "desc": "Training design title"},
    {"no": 3, "title": "Proponents", "desc": "Proponent details and assigned roles"},
    {"no": 4, "title": "Implementing Unit", "desc": "Unit responsible for implementing the training"},
    {"no": 5, "title": "Coordinating Units", "desc": "Coordinating units / beneficiaries"},
    {"no": 6, "title": "Sustainable Development Goals (SDG)", "desc": "SDGs covered (check all that apply)"},
    {"no": 7, "title": "ISPSC Extension Agenda", "desc": "Extension agenda covered (check all that apply)"},
    {"no": 8, "title": "Duration", "desc": "Duration of the training design"},
    {"no": 9, "title": "Extension Site", "desc": "Venue / extension site"},
    {"no": 10, "title": "Funding Source", "desc": "Source of funds for the training"},
    {"no": 11, "title": "Budget", "desc": "Total budget of the training design"},
    {"no": 12, "title": "Participants / Proposed Clientele", "desc": "Sex-disaggregated participant profiling"},
    {"no": 13, "title": "Gender Issues / Mandates Addressed", "desc": "Applicable GAD mandates"},
    {"no": 14, "title": "Rationale", "desc": "Rationale of the training design"},
    {"no": 15, "title": "Objectives", "desc": "General and specific objectives"},
    {"no": 16, "title": "Methodology", "desc": "Methodology of the training"},
    {"no": 17, "title": "Schedule of Activities", "desc": "Work plan / schedule of activities"},
    {"no": 18, "title": "Budgetary Requirements", "desc": "Line-item budget"},
    {"no": 19, "title": "Expected Outputs / Deliverables", "desc": "Expected outputs and deliverables"},
]

FLOW_STEP_LISTS = {
    "RESEARCH": INITIAL_RESEARCH_STEPS,
    "TRAINING": INITIAL_TRAINING_STEPS,
}

# Backwards-compatible name: the old shared list mirrored the Extension
# Proposal form, so it maps to the research flow.
INITIAL_STEP_LABELS = SHARED_STEP_LABELS + INITIAL_RESEARCH_STEPS


def _flow_steps_from_db(flow):
    """Step rows for one flow as ``{"no", "title", "desc"}`` dicts.

    Falls back to the bundled lists when the admin step table has not been
    seeded yet (fresh database before the first wizard request).
    """
    try:
        from details.models import ProposalWizardStepConfig
        rows = ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("step_no")
        shared = [
            {"no": row.step_no, "title": row.title, "desc": row.description}
            for row in rows
            if row.flow == "ALL"
        ]
        flow_rows = [
            {"no": row.step_no, "title": row.title, "desc": row.description}
            for row in rows
            if row.flow == flow
        ]
        if flow_rows or flow == "ALL":
            return shared + flow_rows
    except Exception:
        pass
    return SHARED_STEP_LABELS + FLOW_STEP_LISTS.get(flow, [])


def step_labels_for_flow(flow):
    """Step list for a wizard flow ("ALL", "RESEARCH", or "TRAINING")."""
    if flow not in ("ALL", "RESEARCH", "TRAINING"):
        flow = "RESEARCH"
    return _flow_steps_from_db(flow)


class _FlowStepLabels:
    """Reads the step list for one flow from the admin step table.

    Behaves like the list of ``{"no", "title", "desc"}`` dicts it replaces so
    call sites can keep iterating it.
    """

    def __init__(self, flow):
        self._flow = flow

    def _get_steps(self):
        return step_labels_for_flow(self._flow)

    def __iter__(self):
        return iter(self._get_steps())

    def __len__(self):
        return len(self._get_steps())

    def __getitem__(self, index):
        return self._get_steps()[index]

    def __setitem__(self, index, value):
        pass

    def __delitem__(self, index, value=None):
        pass

    def __contains__(self, item):
        return item in self._get_steps()

    def __repr__(self):
        return repr(self._get_steps())

    def __str__(self):
        return str(self._get_steps())


# The legacy module-level label lists. New code should use
# ``step_labels_for_flow(flow)`` (or ``step_labels_for(proposal)`` in
# proposals.views.helpers) so the steps always match the proposal's form.
STEP_LABELS = _FlowStepLabels("RESEARCH")
TRAINING_STEP_LABELS = _FlowStepLabels("TRAINING")


class _DynamicTotalSteps:
    """Number of wizard steps, read from the admin's step table.

    Behaves like an int in comparisons (see the rich-comparison methods below),
    which is why it needs ``__hash__``: Python drops the inherited one as soon
    as ``__eq__`` is defined, and ``min(step, TOTAL_STEPS)`` can hand this
    object back - it then blew up as a dict key in the wizard view.
    """

    def __int__(self):
        try:
            from details.models import ProposalWizardStepConfig
            max_step = (
                ProposalWizardStepConfig.objects.filter(is_visible=True)
                .order_by("-step_no")
                .first()
            )
            return max_step.step_no if max_step else 22
        except Exception:
            return 22

    def __index__(self):
        return int(self)

    def __hash__(self):
        return hash(int(self))

    def __str__(self):
        return str(int(self))

    def __repr__(self):
        return repr(int(self))

    def __eq__(self, other):
        return int(self) == other

    def __ne__(self, other):
        return int(self) != other

    def __lt__(self, other):
        return int(self) < other

    def __le__(self, other):
        return int(self) <= other

    def __gt__(self, other):
        return int(self) > other

    def __ge__(self, other):
        return int(self) >= other

    def __add__(self, other):
        return int(self) + other

    def __radd__(self, other):
        return other + int(self)

    def __sub__(self, other):
        return int(self) - other

    def __rsub__(self, other):
        return other - int(self)


TOTAL_STEPS = _DynamicTotalSteps()


SDG_LIST = [
    ("01", "No Poverty"),
    ("02", "Zero Hunger"),
    ("03", "Good Health and Well-being"),
    ("04", "Quality Education"),
    ("05", "Gender Equality"),
    ("06", "Clean Water and Sanitation"),
    ("07", "Affordable and Clean Energy"),
    ("08", "Decent Work and Economic Growth"),
    ("09", "Industry, Innovation and Infrastructure"),
    ("10", "Reduced Inequalities"),
    ("11", "Sustainable Cities and Communities"),
    ("12", "Responsible Consumption and Production"),
    ("13", "Climate Action"),
    ("14", "Life Below Water"),
    ("15", "Life on Land"),
    ("16", "Peace, Justice and Strong Institutions"),
    ("17", "Partnerships for the Goals"),
]


THRUST_LIST = [
    "Indigenous Heritage Protection",
    "Environmental Protection",
    "Resource Sharing",
    "Numeracy and Literacy",
    "Governance and Administration",
    "IP-TBM Office Establishment",
    "Trade Fair and Exhibit",
    "Technology Transfer & RD Results Dissemination",
    "Network and Linkage",
    "Adult Education",
    "Calamity & Disaster Rehabilitation",
    "Entrepreneurship & Financial Literacy",
    "Health and Nutrition",
    "Advocacies & Social Justice",
]


GENDER_ISSUE_LIST = [
    (
        "women_role_development",
        "The activity strengthens the advocacy on the significant role of women in development.",
    ),
    (
        "family_welfare_laws",
        "The activity strengthens the understanding of the men and women in barangays on the laws affecting family welfare; decreased incidence of bullying and SH in the barangay.",
    ),
    (
        "lgbtq_acceptance",
        "The activity increases the level of acceptance of the LGBTQ in the society.",
    ),
    (
        "gad_awareness_safe_spaces",
        "The activity enhances the level of awareness on GAD issues and concepts including related laws specifically Safe Space Act.",
    ),
    ("others", "Others"),
]


MOA_STEP_LABELS = [
    {"no": 1, "title": "Agreement Basics", "desc": "Title, reference, dates, and purpose"},
    {"no": 2, "title": "Parties and Signatories", "desc": "Names, representatives, and signers"},
    {"no": 3, "title": "Scope and Terms", "desc": "Responsibilities, deliverables, and rules"},
    {"no": 4, "title": "Attachments and Review", "desc": "Upload files and finalize the draft"},
]


MOA_DRAFT_TEXT_FIELDS = [
    "partner_name", "partner_description", "partner_address", "partner_short_name",
    "partner_rep_name", "partner_rep_title",
    "whereas_clauses", "objectives", "obligations_ispsc", "obligations_partner",
    "ip_ownership_text", "ip_license_years",
    "term_years", "funding_ispsc", "funding_partner",
    "data_privacy_text", "amendments_text", "termination_notice_days", "misc_text",
    "partner_witness1_name", "partner_witness1_title",
    "partner_witness2_name", "partner_witness2_title",
]


MOA_DRAFT_CHECKBOX_FIELDS = [
    "ip_license_royalty_free",
    "ip_license_exclusive",
    "ip_license_irrevocable",
]
