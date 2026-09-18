"""
The office's default proposal wizard: which built-in *section* each step
starts out with.

A *section* is a reusable, self-contained part of the proposal form (the
title input, the proponent roster, the SDG picker, the budget field, ...).
The behaviour of each section - its inputs, how it saves, and when it counts
as complete - lives in ``proposals.views.sections``. This module only says
how the wizard is laid out on a fresh database, so that the ``details`` app
(models and migrations) never has to import the proposal views.

Admins own the layout after that: through *Admin -> Wizard Steps* they can
rename a step, point it at a different section, reorder steps, hide or
un-require them, add steps that carry only admin-built fields, and add or
edit the fields shown on any step. Nothing in the codebase keys behaviour off
a step's number any more; it keys off the section a step is configured with.
"""

#: ``(step_no, section_key, title, description)`` for the built-in wizard.
#: ``section_key`` values are the keys of ``proposals.views.sections.SECTIONS``.
DEFAULT_WIZARD_STEPS = [
    (1, "extension_type", "Extension Type and Scope", "Type of extension and proposal scope"),
    (2, "title", "Title", "Program, project, or activity title"),
    (3, "proponents", "Proponents", "Proponent details and assigned roles"),
    (4, "implementing_agency", "Implementing Agency/Unit", "Office, agency, or unit responsible"),
    (5, "beneficiaries", "Collaborators/Beneficiaries", "Beneficiary count and target group"),
    (6, "sdg_thrust", "SDGs / Extension Agenda", "SDGs covered and extension thrust"),
    (7, "budget", "Budgetary Requirement", "Funding source and budget"),
    (8, "participants", "Participants / Proposed Clients", "Participant profiling and counts"),
    (9, "gender_issues", "Gender Issues / Mandates Addressed", "Applicable GAD mandates"),
    (10, "schedule_venue", "Date and Venue / Extension Site", "Schedule and implementation site"),
    (11, "rationale", "Rationale / Background", "Context and alignment with SDG / thrust / GAD"),
    (12, "significance", "Significance", "Importance of the proposed extension"),
    (13, "objectives", "Objectives", "General and specific SMART objectives"),
    (14, "methodology", "Methodology / Mechanics", "Implementation approach"),
    (15, "outputs", "Output / Outcome", "Expected outputs and outcomes"),
    (16, "activities", "Details of Activities", "Work plan, Gantt chart, and related files"),
    (17, "funding", "Funding Strategy", "Funding strategy template and related supporting files"),
    (18, "research_abstract", "Research Abstract Upload", "Required for research-based proposals"),
    (19, "certificate", "Certificate of Completion Upload", "Required for research-based proposals"),
]

#: Section key of the step that owns the proposal's proponent roster.
PROPONENTS_SECTION_KEY = "proponents"


def default_section_for_step(step_no):
    """The section a built-in step number shipped with (``""`` if none)."""
    for no, section_key, _title, _desc in DEFAULT_WIZARD_STEPS:
        if no == step_no:
            return section_key
    return ""


def default_step_dicts():
    """The defaults as ``{"no", "section", "title", "desc"}`` dicts."""
    return [
        {"no": no, "section": section_key, "title": title, "desc": desc}
        for no, section_key, title, desc in DEFAULT_WIZARD_STEPS
    ]
