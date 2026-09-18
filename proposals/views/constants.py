"""
Step labels and reference lists shared across the proposal views.
"""

from django.contrib.auth import get_user_model

from details.wizard_defaults import default_step_dicts


User = get_user_model()


def _step_labels():
    """The wizard's visible steps as ``{"no", "title", "desc", "section"}``.

    Backed by the admin's ``ProposalWizardStepConfig`` table (seeded from
    ``details.wizard_defaults`` on first use). Kept as a function so callers
    read the current layout, not the one at import time.
    """
    from .wizard_config import step_summaries
    return step_summaries()


def _total_steps():
    from .wizard_config import last_step_number
    return last_step_number()


class _DynamicStepLabels:
    """List-like view of ``_step_labels()`` for older call sites."""

    def __iter__(self):
        return iter(_step_labels())

    def __len__(self):
        return len(_step_labels())

    def __getitem__(self, index):
        return _step_labels()[index]

    def __contains__(self, item):
        return item in _step_labels()

    def __repr__(self):
        return repr(_step_labels())


class _DynamicTotalSteps:
    """Int-like view of ``_total_steps()`` for older call sites.

    ``__hash__`` is defined because ``__eq__`` is: ``min(step, TOTAL_STEPS)``
    can hand this object back and it must remain usable as a dict key.
    """

    def __int__(self):
        return _total_steps()

    __index__ = __int__

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


#: The built-in layout as ``{"no", "section", "title", "desc"}`` dicts. The
#: canonical definition is ``details.wizard_defaults.DEFAULT_WIZARD_STEPS``.
INITIAL_STEP_LABELS = default_step_dicts()


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
