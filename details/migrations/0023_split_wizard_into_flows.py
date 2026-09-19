"""
Split the single 19-step wizard into the office's two proposal forms.

- Steps 2-19 (the old shared list, which mirrored the Extension Proposal
  form) become the RESEARCH flow, renumbered to match the new
  ``static/templates/form1.docx`` sections: SDG (V) and ISPSC Extension
  Thrust (VI) are split into their own steps, Monitoring and Evaluation
  Mechanics (XVIII) becomes its own step, and the research-only uploads move
  to the end.
- A TRAINING flow is seeded from ``static/templates/FORM 2 TRAINING DESIGN
  FORM.docx`` for community-based and request-based proposals.
- Step 1 (Extension Type and Scope) stays shared by every proposal.

Related data (admin-built step forms, per-step reviewer comments, each
proposal's completed/skipped/current step) is renumbered with the same map so
nothing is silently reattached to a different section. Drafts that belong to
the training flow lose their progress above step 6, because the old shared
steps 7+ meant different things there; steps 2-6 mean the same thing in both
flows (title, proponents, implementing unit, collaborators, SDG).

Kept as frozen history after PR #32 was reverted (``0026`` collapses the two
flows again), with one patch: the step-form and reviewer-comment renumbering
used to run upwards, which moved step 7 onto 8 and then moved both onto 9, so
every row from the old steps 7-18 piled onto a single step - and for comments
the pile aborted the migration on
``unique_section_comment_per_reviewer_step_round`` as soon as one reviewer had
commented on two of those steps. It now runs downwards, like the step-table
renumbering below always did, so a database that had not applied this
migration yet - including one where it aborted - reaches exactly the numbering
``0026`` inverts.
"""

from django.db import migrations


# Old shared step number -> new research-flow step number.
RESEARCH_RENUMBER = {
    7: 8,   # Budgetary Requirement
    8: 9,   # Participants / Proposed Clients
    9: 10,  # Gender Issues / Mandates Addressed
    10: 11,  # Date & Venue / Extension Site
    11: 12,  # Rationale / Background
    12: 13,  # Significance
    13: 14,  # Objectives
    14: 15,  # Methodology / Mechanics
    15: 16,  # Output / Outcome
    16: 17,  # Details of Activities
    17: 18,  # Funding Strategy
    18: 20,  # Research Abstract Upload
    19: 21,  # Certificate of Completion Upload
}

NEW_RESEARCH_STEPS = [
    {
        "step_no": 7,
        "title": "ISPSC Extension Thrust",
        "description": "ISPSC extension thrust covered and how it relates",
    },
    {
        "step_no": 19,
        "title": "Monitoring and Evaluation Mechanics",
        "description": "M&E mechanics attachment (Extension Proposal XVIII)",
    },
]

TRAINING_STEPS = [
    (2, "Title", "Training design title"),
    (3, "Proponents", "Proponent details and assigned roles"),
    (4, "Implementing Unit", "Unit responsible for implementing the training"),
    (5, "Coordinating Units", "Coordinating units / beneficiaries"),
    (6, "Sustainable Development Goals (SDG)", "SDGs covered and how each relates"),
    (7, "Extension Thrust", "ISPSC extension thrust and how it relates"),
    (8, "Duration", "Duration of the training design"),
    (9, "Extension Site", "Venue / extension site"),
    (10, "Funding Source", "Source of funds for the training"),
    (11, "Budget", "Total budget of the training design"),
    (12, "Participants / Proposed Clientele", "Sex-disaggregated participant profiling"),
    (13, "Gender Issues / Mandates Addressed", "Applicable GAD mandates"),
    (14, "Rationale", "Rationale of the training design"),
    (15, "Objectives", "General and specific objectives"),
    (16, "Methodology", "Methodology of the training"),
    (17, "Schedule of Activities", "Work plan / schedule of activities"),
    (18, "Budgetary Requirements", "Line-item budget"),
    (19, "Expected Outputs / Deliverables", "Expected outputs and deliverables"),
]

TRAINING_SHARED_STEPS_END = 6


def renumber_research_steps(apps):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")

    StepConfig.objects.filter(step_no=1).update(flow="ALL")
    # Move everything else into the research flow first: the rows are then the
    # only occupants of that flow, so the renumbering below cannot collide.
    StepConfig.objects.filter(step_no__gte=2).update(flow="RESEARCH")

    # Renumber from the top down so a target number is always free.
    for old_no in sorted(RESEARCH_RENUMBER, reverse=True):
        StepConfig.objects.filter(flow="RESEARCH", step_no=old_no).update(
            step_no=RESEARCH_RENUMBER[old_no]
        )

    # Admin-created extras (step_no > 19) also belonged to the old shared
    # list; keep them in the research flow, bumped past the renumbered steps
    # if their number was taken.
    extras = list(
        StepConfig.objects.filter(flow="ALL").exclude(step_no=1).order_by("step_no")
    )
    taken = set(
        StepConfig.objects.filter(flow="RESEARCH").values_list("step_no", flat=True)
    )
    for extra in extras:
        new_no = extra.step_no
        while new_no in taken:
            new_no += 1
        extra.flow = "RESEARCH"
        extra.step_no = new_no
        extra.save(update_fields=["flow", "step_no"])
        taken.add(new_no)

    StepConfig.objects.bulk_create(
        [
            StepConfig(
                step_no=item["step_no"],
                flow="RESEARCH",
                title=item["title"],
                description=item["description"],
                is_visible=True,
                is_required=True,
            )
            for item in NEW_RESEARCH_STEPS
        ]
    )

    StepConfig.objects.filter(flow="RESEARCH", step_no=6).update(
        title="SDGs Covered / Extension Agenda",
        description="SDGs covered and how each relates to the proposal",
    )


def seed_training_steps(apps):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.bulk_create(
        [
            StepConfig(
                step_no=no,
                flow="TRAINING",
                title=title,
                description=desc,
                is_visible=True,
                is_required=True,
            )
            for no, title, desc in TRAINING_STEPS
        ]
    )


def renumber_step_forms_and_comments(apps):
    """Carry admin-built step forms and reviewer comments to the new numbers.

    Downwards, one step number at a time: an ascending in-place UPDATE moves
    the rows on step 7 onto 8 and then moves both sets onto 9, which piles
    every row from the old steps 7-18 onto one step and - for comments, which
    are unique per reviewer and step - aborts the migration as soon as one
    reviewer commented on two of those steps.
    """
    FormTemplate = apps.get_model("details", "DynamicFormTemplate")
    SectionComment = apps.get_model("proposals", "ProposalSectionComment")

    for old_no in sorted(RESEARCH_RENUMBER, reverse=True):
        FormTemplate.objects.filter(
            applies_to="PROPOSAL",
            proposal_wizard_step=old_no,
        ).update(proposal_wizard_step=RESEARCH_RENUMBER[old_no], wizard_flow="RESEARCH")

    for old_no in sorted(RESEARCH_RENUMBER, reverse=True):
        SectionComment.objects.filter(step_no=old_no).update(
            step_no=RESEARCH_RENUMBER[old_no]
        )


def renumber_proposal_progress(apps):
    """Map each draft's step bookkeeping onto the new numbering.

    Research-flow drafts (and anything that never picked a type) keep their
    progress. Training-flow drafts keep steps 1-6 - the sections that mean the
    same thing in both forms - and re-answer the rest, because old steps 7+
    held different sections there.
    """
    Proposal = apps.get_model("proposals", "Proposal")

    for proposal in Proposal.objects.all().iterator():
        old_completed = set(proposal.completed_steps or [])
        old_skipped = set(proposal.skipped_steps or [])

        completed = {RESEARCH_RENUMBER.get(no, no) for no in old_completed}
        skipped = {RESEARCH_RENUMBER.get(no, no) for no in old_skipped}

        if proposal.extension_type in ("REQUEST_BASED", "COMMUNITY_BASED"):
            completed = {no for no in completed if no <= TRAINING_SHARED_STEPS_END}
            skipped = {no for no in skipped if no <= TRAINING_SHARED_STEPS_END}

        proposal.completed_steps = sorted(completed)
        proposal.skipped_steps = sorted(skipped)
        proposal.current_step = RESEARCH_RENUMBER.get(
            proposal.current_step, proposal.current_step
        )
        proposal.save(update_fields=["completed_steps", "skipped_steps", "current_step"])


def sync_fresh_databases(apps, schema_editor):
    """Seed both flows when upgrading an empty/new database.

    The renumbering pass above only touches rows that exist. On a database
    that never had the shared 19-step list (fresh installs migrate straight
    here), seed the full step set instead of relying on first-request sync.
    """
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    if StepConfig.objects.exists():
        return

    StepConfig.objects.create(
        step_no=1,
        flow="ALL",
        title="Extension Type and Scope",
        description="Type of extension and proposal scope",
        is_visible=True,
        is_required=True,
    )

    research = [
        (2, "Title", "Program, project, or activity title"),
        (3, "Proponents", "Proponent details and assigned roles"),
        (4, "Implementing Agency/Unit", "Office, agency, or unit responsible"),
        (5, "Collaborators/Beneficiaries", "Beneficiary count and target group"),
        (6, "SDGs Covered / Extension Agenda", "SDGs covered and how each relates"),
        (7, "ISPSC Extension Thrust", "ISPSC extension thrust and how it relates"),
        (8, "Budgetary Requirement", "Funding source and budget"),
        (9, "Participants / Proposed Clients", "Participant profiling and counts"),
        (10, "Gender Issues / Mandates Addressed", "Applicable GAD mandates"),
        (11, "Date and Venue / Extension Site", "Schedule and implementation site"),
        (12, "Rationale / Background", "Context and alignment with SDG / thrust / GAD"),
        (13, "Significance", "Importance of the proposed extension"),
        (14, "Objectives", "General and specific SMART objectives"),
        (15, "Methodology / Mechanics", "Implementation approach"),
        (16, "Output / Outcome", "Expected outputs and outcomes"),
        (17, "Details of Activities", "Work plan, Gantt chart, and related files"),
        (18, "Funding Strategy", "Funding strategy template and related supporting files"),
        (19, "Monitoring and Evaluation Mechanics", "M&E mechanics attachment"),
        (20, "Research Abstract Upload", "Required for research-based proposals"),
        (21, "Certificate of Completion Upload", "Required for research-based proposals"),
    ]
    StepConfig.objects.bulk_create(
        [
            StepConfig(step_no=no, flow="RESEARCH", title=t, description=d, is_visible=True, is_required=True)
            for no, t, d in research
        ]
    )
    StepConfig.objects.bulk_create(
        [
            StepConfig(step_no=no, flow="TRAINING", title=t, description=d, is_visible=True, is_required=True)
            for no, t, d in TRAINING_STEPS
        ]
    )


def apply(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")

    if not StepConfig.objects.exists():
        # Fresh install: no shared 19-step list to renumber, seed both flows.
        sync_fresh_databases(apps, schema_editor)
        return

    renumber_research_steps(apps)
    seed_training_steps(apps)
    renumber_step_forms_and_comments(apps)
    renumber_proposal_progress(apps)


def reverse(apps, schema_editor):
    # The split is not meaningfully reversible (progress above step 6 was
    # already dropped for training drafts); leave the rows in place.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0022_alter_proposalwizardstepconfig_options_and_more"),
        ("proposals", "0047_proposal_duration_proposal_funding_source_and_more"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
