"""
Step labels and reference lists shared across the proposal views.
"""

from django.contrib.auth import get_user_model


User = get_user_model()


TOTAL_STEPS = 19


STEP_LABELS = [
    {"no": 1, "title": "Extension Type and Scope", "desc": "Type of extension and proposal scope"},
    {"no": 2, "title": "Title", "desc": "Program, project, or activity title"},
    {"no": 3, "title": "Proponents", "desc": "Proponent details and assigned roles"},
    {"no": 4, "title": "Implementing Agency/Unit", "desc": "Office, agency, or unit responsible"},
    {"no": 5, "title": "Collaborators/Beneficiaries", "desc": "Beneficiary count and target group"},
    {"no": 6, "title": "SDGs / Extension Agenda", "desc": "SDGs covered and extension thrust"},
    {"no": 7, "title": "Budgetary Requirement", "desc": "Funding source and budget"},
    {"no": 8, "title": "Participants / Proposed Clients", "desc": "Participant profiling and counts"},
    {"no": 9, "title": "Gender Issues / Mandates Addressed", "desc": "Applicable GAD mandates"},
    {"no": 10, "title": "Date and Venue / Extension Site", "desc": "Schedule and implementation site"},
    {"no": 11, "title": "Rationale / Background", "desc": "Context and alignment with SDG / thrust / GAD"},
    {"no": 12, "title": "Significance", "desc": "Importance of the proposed extension"},
    {"no": 13, "title": "Objectives", "desc": "General and specific SMART objectives"},
    {"no": 14, "title": "Methodology / Mechanics", "desc": "Implementation approach"},
    {"no": 15, "title": "Output / Outcome", "desc": "Expected outputs and outcomes"},
    {"no": 16, "title": "Details of Activities", "desc": "Work plan, Gantt chart, and related files"},
    {"no": 17, "title": "Funding Strategy", "desc": "Funding strategy template and related supporting files"},
    {"no": 18, "title": "Research Abstract Upload", "desc": "Required for research-based proposals"},
    {"no": 19, "title": "Certificate of Completion Upload", "desc": "Required for research-based proposals"},
]


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
