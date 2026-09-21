"""
Step labels and reference lists shared across the proposal views.
"""

from django.contrib.auth import get_user_model


User = get_user_model()


INITIAL_STEP_LABELS = [
    {"no": 1, "title": "Extension Type and Scope", "desc": "Type of extension and proposal scope"},
    {"no": 2, "title": "Title", "desc": "Program, project, or activity title"},
    {"no": 3, "title": "Proponents", "desc": "Proponent details and assigned roles"},
    {"no": 4, "title": "Implementing Agency/Unit", "desc": "Office, agency, or unit responsible"},
    {"no": 5, "title": "Collaborators/Beneficiaries", "desc": "Beneficiary count and target group"},
    {"no": 6, "title": "SDGs / Extension Agenda", "desc": "SDGs covered and extension agenda"},
    {"no": 7, "title": "Utility Model", "desc": "Title of technology, registration number, and description (N/A if not applicable)"},
    {"no": 8, "title": "Budgetary Requirement", "desc": "Funding source and budget"},
    {"no": 9, "title": "Participants / Proposed Clients", "desc": "Sex-disaggregated participant counts"},
    {"no": 10, "title": "Gender Issues / Mandates Addressed", "desc": "Type the GAD issues or mandates addressed"},
    {"no": 11, "title": "Date and Venue / Extension Site", "desc": "Schedule and implementation site"},
    {"no": 12, "title": "Rationale / Background", "desc": "Context and alignment with SDG / thrust / GAD"},
    {"no": 13, "title": "Significance", "desc": "Importance of the proposed extension"},
    {"no": 14, "title": "Objectives", "desc": "General and specific SMART objectives"},
    {"no": 15, "title": "Methodology / Mechanics", "desc": "Implementation approach"},
    {"no": 16, "title": "Output / Outcome", "desc": "Expected outputs and outcomes"},
    {"no": 17, "title": "Details of Activities", "desc": "Work plan, Gantt chart, and related files"},
    {"no": 18, "title": "Funding Strategy", "desc": "Funding strategy template and related supporting files"},
    {"no": 19, "title": "Research Abstract Upload", "desc": "Required for research-based proposals"},
    {"no": 20, "title": "Certificate of Completion Upload", "desc": "Required for research-based proposals"},
]

#: Step number of the Utility Model section, and the last built-in step. The
#: wizard's native step pages are keyed by number, so these are the anchors
#: the views and the data migrations agree on.
UTILITY_MODEL_STEP_NO = 7
LAST_BUILTIN_STEP_NO = INITIAL_STEP_LABELS[-1]["no"]


#: What each built-in step already asks for and how it decides it is complete.
#:
#: Shown in the admin's step editor so the office edits the *existing*
#: hardcoded inputs (via a field whose Key matches ``editable_keys``) instead
#: of unknowingly adding a duplicate input that asks the proponent for the
#: same thing twice. ``editable_keys`` mirrors
#: ``proposals.views.dynamic_fields.NATIVE_STEP_FIELDS``; the completion text
#: mirrors ``proposals.views.wizard.is_step_complete``.
BUILTIN_STEP_LOGIC = {
    1: {
        "inputs": [
            "Extension Type (choice chips: Research-based Faculty/Student, Request-based, Community-based)",
            "Scope (choice chips: Program / Project / Activity)",
            "Research Title (text — only shown for research-based types)",
            "Proposal Format (choice chips: Training Design / Extension Proposal — only shown for request-based type)",
        ],
        "completion": "Complete when an Extension Type and a Scope are chosen; research-based types also need a Research Title. The proposal format is derived from the type (community-based → Training Design, research-based → Extension Proposal).",
        "editable_keys": ["extension_type", "scope_type", "research_title"],
    },
    2: {
        "inputs": [
            "Title of the Program / Project / Activity (text)",
            "Project phases list (only when Scope is Program)",
        ],
        "completion": "Complete when a title is saved; a Program-scoped proposal also needs at least one project phase.",
        "editable_keys": ["title"],
    },
    3: {
        "inputs": [
            "Proponents repeatable group (Name, Designation, Specialization, Role, CP Number, Email by default — fully admin-editable below)",
            "Project leader assignment (only when Scope is Program)",
        ],
        "completion": "Complete when at least one proponent exists and the repeatable group's required columns and minimum row count are satisfied.",
        "editable_keys": [],
    },
    4: {
        "inputs": ["Implementing Agency / Unit (text)"],
        "completion": "Complete when the implementing agency is filled in.",
        "editable_keys": ["implementing_agency"],
    },
    5: {
        "inputs": [
            "Number of Beneficiaries (number)",
            "Who are the beneficiaries? (text)",
        ],
        "completion": "Complete when both the count and the description are filled in.",
        "editable_keys": ["beneficiaries_count", "beneficiaries_who"],
    },
    6: {
        "inputs": [
            "SDGs Covered (chip checklist from the fixed SDG list)",
            "ISPSC Extension Agenda (chip checklist from the fixed agenda list)",
        ],
        "completion": "Complete when at least one SDG or one Extension Agenda item is selected.",
        "editable_keys": [],
    },
    7: {
        "inputs": [
            "Title of Technology (text)",
            "Utility Model Registration Number (text)",
            "Utility Model Description (long text)",
        ],
        "completion": "Complete when all three are answered — “N/A” is a valid answer when the proposal has no technology or utility model behind it.",
        "editable_keys": [
            "technology_title",
            "utility_model_registration_number",
            "utility_model_description",
        ],
    },
    8: {
        "inputs": ["Budgetary Requirement (long text)"],
        "completion": "Complete when the budgetary requirement is filled in.",
        "editable_keys": ["budgetary_requirement"],
    },
    9: {
        "inputs": ["Male count (number)", "Female count (number)", "Auto-computed total"],
        "completion": "Complete when the male + female total is greater than zero.",
        "editable_keys": [],
    },
    10: {
        "inputs": ["Gender issues / mandates (free-text rows, add as many as needed)"],
        "completion": "Complete when at least one gender issue or mandate is entered. Entries matching a canonical mandate wording tick that mandate's row in the generated DOCX.",
        "editable_keys": [],
    },
    11: {
        "inputs": [
            "Estimated Month (dropdown)",
            "Estimated Year (number)",
            "Venue / Extension Site (text)",
        ],
        "completion": "Complete when the venue / extension site is filled in.",
        "editable_keys": ["extension_venue", "estimated_month", "estimated_year"],
    },
    12: {
        "inputs": ["Rationale / Background (long text)"],
        "completion": "Complete when the rationale / background is filled in.",
        "editable_keys": ["rationale_background"],
    },
    13: {
        "inputs": ["Significance (long text)"],
        "completion": "Complete when the significance is filled in.",
        "editable_keys": ["significance"],
    },
    14: {
        "inputs": [
            "General Objective (long text)",
            "Specific objectives (rows; grouped per project phase when Scope is Program)",
        ],
        "completion": "Complete when the general objective is saved and there is at least one specific objective (one per project phase for Program-scoped proposals).",
        "editable_keys": ["general_objective"],
    },
    15: {
        "inputs": ["Methodology / mechanics items (free-text rows)"],
        "completion": "Complete when at least one methodology item is entered.",
        "editable_keys": [],
    },
    16: {
        "inputs": ["Output / outcome items (free-text rows)"],
        "completion": "Complete when at least one output / outcome is entered.",
        "editable_keys": [],
    },
    17: {
        "inputs": [
            "Work Plan file upload",
            "Gantt Chart file upload",
            "Additional supporting attachments (optional, multiple)",
        ],
        "completion": "Complete when both the work plan and the Gantt chart files are uploaded.",
        "editable_keys": [],
    },
    18: {
        "inputs": ["Funding Strategy file upload"],
        "completion": "Complete when the funding strategy file is uploaded.",
        "editable_keys": [],
    },
    19: {
        "inputs": ["Research Abstract file upload"],
        "completion": "Required (and shown) only for research-based proposals; other types pass automatically.",
        "editable_keys": [],
    },
    20: {
        "inputs": ["Certificate of Completion file upload"],
        "completion": "Required (and shown) only for research-based proposals; other types pass automatically.",
        "editable_keys": [],
    },
}


class _DynamicStepLabels:
    def _get_steps(self):
        try:
            from details.models import ProposalWizardStepConfig
            if not ProposalWizardStepConfig.objects.exists():
                to_create = []
                for item in INITIAL_STEP_LABELS:
                    to_create.append(
                        ProposalWizardStepConfig(
                            step_no=item["no"],
                            title=item["title"],
                            description=item["desc"],
                            is_visible=True,
                            is_required=True,
                        )
                    )
                ProposalWizardStepConfig.objects.bulk_create(to_create)
            
            return [
                {"no": config.step_no, "title": config.title, "desc": config.description}
                for config in ProposalWizardStepConfig.objects.all().order_by("step_no")
            ]
        except Exception:
            return INITIAL_STEP_LABELS

    def __iter__(self):
        return iter(self._get_steps())

    def __len__(self):
        return len(self._get_steps())

    def __getitem__(self, index):
        return self._get_steps()[index]

    def __setitem__(self, index, value):
        pass

    def __delitem__(self, index):
        pass

    def __contains__(self, item):
        return item in self._get_steps()

    def __repr__(self):
        return repr(self._get_steps())

    def __str__(self):
        return str(self._get_steps())


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
            max_step = ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("-step_no").first()
            return max_step.step_no if max_step else LAST_BUILTIN_STEP_NO
        except Exception:
            return LAST_BUILTIN_STEP_NO

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


STEP_LABELS = _DynamicStepLabels()
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


#: The mandates the DOCX templates print as fixed rows. The wizard no longer
#: offers them as checkboxes - step 10 is a free-text repeater - but typed text
#: that matches one of these wordings is mapped back to its key so the right
#: row gets ticked off in the generated form (see canonical_gender_issue_key).
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
