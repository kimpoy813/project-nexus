"""
Give every existing wizard step the part it was already rendering.

Before this migration the proposal wizard's content was decided by step
*number*: step 5 always rendered the beneficiaries inputs, step 11 always the
rationale textarea, and so on. Steps now name their part (``section_key``) and
carry their own position (``order``), so an existing installation has to be
told which part each of its rows was showing — otherwise every step would
suddenly render as an empty office-built form.

The mapping is by step number, which is exactly how the old code resolved it,
so nothing changes for anyone until an admin moves something.

Also: seeds the four MOA drafting steps (which were hardcoded in the view) and
re-links every ``DynamicFormTemplate`` that was pinned to a proposal step by
number onto the matching step row, so forms follow a step when it is reordered.
"""

from django.db import migrations


#: ``(step_no, section_key)`` — the parts the proposal wizard shipped with.
PROPOSAL_SECTION_BY_STEP = [
    (1, "extension_type"),
    (2, "title"),
    (3, "proponents"),
    (4, "implementing_agency"),
    (5, "beneficiaries"),
    (6, "sdg_thrust"),
    (7, "budgetary_requirement"),
    (8, "participants"),
    (9, "gender_issues"),
    (10, "schedule_venue"),
    (11, "rationale_background"),
    (12, "significance"),
    (13, "objectives"),
    (14, "methodologies"),
    (15, "output_outcomes"),
    (16, "details_of_activities"),
    (17, "funding_strategy"),
    (18, "research_abstract"),
    (19, "certificate_of_completion"),
]

MOA_STEPS = [
    (1, "agreement_basics", "Agreement Basics", "Title, reference, dates, and purpose"),
    (2, "parties_signatories", "Parties and Signatories", "Names, representatives, and signers"),
    (3, "scope_terms", "Scope and Terms", "Responsibilities, deliverables, and rules"),
    (4, "attachments_review", "Attachments and Review", "Upload files and finalize the draft"),
]


def forwards(apps, schema_editor):
    ProposalWizardStepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    MOAWizardStepConfig = apps.get_model("details", "MOAWizardStepConfig")
    DynamicFormTemplate = apps.get_model("details", "DynamicFormTemplate")

    # 1. Position + part for the proposal steps that already exist.
    section_by_step = dict(PROPOSAL_SECTION_BY_STEP)
    updates = []
    for row in ProposalWizardStepConfig.objects.all():
        row.order = row.step_no
        if not row.section_key:
            row.section_key = section_by_step.get(row.step_no, "")
        updates.append(row)
    if updates:
        ProposalWizardStepConfig.objects.bulk_update(updates, ["order", "section_key"])

    # 2. The MOA drafting steps, which the view used to hardcode as 1..4.
    if not MOAWizardStepConfig.objects.exists():
        MOAWizardStepConfig.objects.bulk_create([
            MOAWizardStepConfig(
                step_no=step_no,
                order=step_no,
                section_key=section_key,
                title=title,
                description=description,
                is_visible=True,
                is_required=True,
            )
            for step_no, section_key, title, description in MOA_STEPS
        ])

    # 3. Attach step-pinned forms to their step row.
    for form in DynamicFormTemplate.objects.filter(proposal_wizard_step__isnull=False):
        step = ProposalWizardStepConfig.objects.filter(step_no=form.proposal_wizard_step).first()
        if step is not None:
            form.attached_proposal_steps.add(step)


def backwards(apps, schema_editor):
    ProposalWizardStepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    MOAWizardStepConfig = apps.get_model("details", "MOAWizardStepConfig")

    MOAWizardStepConfig.objects.all().delete()
    ProposalWizardStepConfig.objects.update(order=0, section_key="")


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0019_moawizardstepconfig_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
