"""
Insert the Utility Model step after ISPSC Extension Agenda (step 6).

The step list is seeded into ``ProposalWizardStepConfig`` by the first wizard
visit (and by ``0023``/``0026`` on databases that ran the reverted split), so
a deployed database already holds a 19-step table with every draft's
progress, every reviewer comment and every admin-built step form numbered
against it. Inserting a step at 7 therefore means moving everything from the
old step 7 (Budgetary Requirement) upwards by one, in the same order the
wizard reads it:

* the step table itself - from the top down, because ``step_no`` is unique;
* each proposal's ``completed_steps`` / ``skipped_steps`` / ``current_step``,
  so a draft resumes on the section it was really answering (a draft that had
  finished step 6 lands on the new step 7 next, exactly where the new
  question sits);
* reviewer comments, from the top down, because one reviewer may only hold one
  comment per step per round;
* admin-built step forms (``DynamicFormTemplate.proposal_wizard_step``), so an
  office form built for "Budgetary Requirement" still opens on Budgetary
  Requirement.

Then the new step is created, the step 6 description drops the "thrust"
wording the office renamed to "extension agenda", and the seeded built-in
fields for the new step are added on databases that use the default field
set.

A fresh database has an empty step table at this point: nothing is shifted
and the first wizard visit seeds ``INITIAL_STEP_LABELS`` (already 20 steps),
so fresh and upgraded databases agree.

Reversing removes the step and shifts everything back down. Answers written
into the three ``Proposal`` columns stay put; only the step bookkeeping moves.
"""

import re

from django.db import migrations


NEW_STEP_NO = 7
NEW_STEP = {
    "title": "Utility Model",
    "description": "Title of technology, registration number, and description (N/A if not applicable)",
    "instructions": "",
    "is_visible": True,
    "is_required": True,
}

# "Fields for Step 7" / "Fields for Step 7: Budgetary Requirement"
SEEDED_FORM_NAME = re.compile(r"^Fields for Step (\d+)(?=$|:)")

OLD_STEP_SIX_DESCRIPTION = "SDGs covered and extension thrust"
NEW_STEP_SIX_DESCRIPTION = "SDGs covered and extension agenda"

DEFAULT_FIELDS = [
    {
        "key": "technology_title",
        "label": "Title of Technology",
        "type": "TEXT",
        "placeholder": "Enter the title of the technology, or N/A",
    },
    {
        "key": "utility_model_registration_number",
        "label": "Utility Model Registration Number",
        "type": "TEXT",
        "placeholder": "Enter the registration number, or N/A",
    },
    {
        "key": "utility_model_description",
        "label": "Utility Model Description",
        "type": "TEXTAREA",
        "placeholder": "Describe the utility model, or N/A",
    },
]


def _shift(step_no, delta):
    """Map one step number across the insertion (or its reversal).

    Reversing drops the Utility Model step itself (``None``) rather than
    letting its "completed" mark land on the step that takes its number.
    """
    if step_no is None:
        return None
    if delta > 0:
        return step_no + delta if step_no >= NEW_STEP_NO else step_no
    if step_no == NEW_STEP_NO:
        return None
    return step_no + delta if step_no > NEW_STEP_NO else step_no


def _shift_step_table(StepConfig, delta):
    """Renumber the step rows. ``step_no`` is unique, so walk away from the gap."""
    if delta > 0:
        rows = StepConfig.objects.filter(step_no__gte=NEW_STEP_NO).order_by("-step_no")
    else:
        rows = StepConfig.objects.filter(step_no__gt=NEW_STEP_NO).order_by("step_no")
    for row_id, step_no in list(rows.values_list("id", "step_no")):
        StepConfig.objects.filter(id=row_id).update(step_no=step_no + delta)


def _shift_proposal_progress(Proposal, delta):
    rows = list(
        Proposal.objects.all().values_list(
            "id", "completed_steps", "skipped_steps", "current_step"
        )
    )
    for proposal_id, completed_steps, skipped_steps, current_step in rows:
        completed = sorted(
            {target for target in (_shift(no, delta) for no in (completed_steps or []) if no) if target}
        )
        skipped = sorted(
            {target for target in (_shift(no, delta) for no in (skipped_steps or []) if no) if target}
        )
        current = _shift(current_step, delta) if current_step else current_step
        if current is None:
            # Reversing with the pointer on the removed step: stay on the
            # section that now holds its number.
            current = NEW_STEP_NO
        if (
            completed == list(completed_steps or [])
            and skipped == list(skipped_steps or [])
            and current == current_step
        ):
            continue
        Proposal.objects.filter(id=proposal_id).update(
            completed_steps=completed,
            skipped_steps=skipped,
            current_step=current,
        )


def _shift_reviewer_comments(Comment, delta):
    """One comment per reviewer per step per round: walk away from the gap."""
    if delta > 0:
        rows = Comment.objects.filter(step_no__gte=NEW_STEP_NO).order_by("-step_no", "id")
    else:
        rows = Comment.objects.filter(step_no__gt=NEW_STEP_NO).order_by("step_no", "id")
    for comment_id, step_no in list(rows.values_list("id", "step_no")):
        Comment.objects.filter(id=comment_id).update(step_no=step_no + delta)


def _shift_step_forms(FormTemplate, delta):
    """Carry admin-built step forms to their new step numbers.

    The seeded forms are named after their step ("Fields for Step 7", or
    "Fields for Step 7: Budgetary Requirement" once an admin edited the step).
    That name shows in the Forms list and in the "please complete" message
    proponents see, so it follows the step; any other name is the office's
    own and stays as it is.
    """
    if delta > 0:
        rows = FormTemplate.objects.filter(
            applies_to="PROPOSAL", proposal_wizard_step__gte=NEW_STEP_NO
        ).order_by("-proposal_wizard_step", "id")
    else:
        rows = FormTemplate.objects.filter(
            applies_to="PROPOSAL", proposal_wizard_step__gt=NEW_STEP_NO
        ).order_by("proposal_wizard_step", "id")
    for form_id, step_no, name in list(rows.values_list("id", "proposal_wizard_step", "name")):
        new_step_no = step_no + delta
        updates = {"proposal_wizard_step": new_step_no}
        match = SEEDED_FORM_NAME.match(name or "")
        if match and int(match.group(1)) == step_no:
            updates["name"] = f"Fields for Step {new_step_no}{name[match.end():]}"
        FormTemplate.objects.filter(id=form_id).update(**updates)


def _seed_default_fields(FormTemplate, FormField):
    """Give the new step the same built-in fields the seeder would.

    Only on a database that already carries the seeded per-step forms: a
    fresh install gets them from ``_seed_default_fields`` on the first wizard
    visit, and a database whose office never used the built-in forms keeps
    not having them.
    """
    if not FormTemplate.objects.filter(
        applies_to="PROPOSAL", slug__startswith="step-", slug__endswith="-fields"
    ).exists():
        return

    base_slug = f"step-{NEW_STEP_NO}-fields"
    slug = base_slug
    suffix = 2
    while FormTemplate.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    form, created = FormTemplate.objects.get_or_create(
        proposal_wizard_step=NEW_STEP_NO,
        applies_to="PROPOSAL",
        defaults={
            "name": f"Fields for Step {NEW_STEP_NO}",
            "slug": slug,
            "is_active": True,
            "blocks_proposal_submission": True,
        },
    )
    if not created and form.fields.exists():
        return
    for order, item in enumerate(DEFAULT_FIELDS, start=1):
        FormField.objects.get_or_create(
            form=form,
            field_key=item["key"],
            defaults={
                "label": item["label"],
                "field_type": item["type"],
                "placeholder": item["placeholder"],
                "required": True,
                "order": order,
            },
        )


def apply(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    FormTemplate = apps.get_model("details", "DynamicFormTemplate")
    FormField = apps.get_model("details", "DynamicFormField")
    Proposal = apps.get_model("proposals", "Proposal")
    Comment = apps.get_model("proposals", "ProposalSectionComment")

    if not StepConfig.objects.exists():
        # Fresh install: the first wizard visit seeds the 20-step list.
        return
    if StepConfig.objects.filter(step_no=NEW_STEP_NO, title=NEW_STEP["title"]).exists():
        # Already applied (a database restored from a post-upgrade backup).
        return

    _shift_step_forms(FormTemplate, +1)
    _shift_reviewer_comments(Comment, +1)
    _shift_step_table(StepConfig, +1)
    _shift_proposal_progress(Proposal, +1)

    StepConfig.objects.create(step_no=NEW_STEP_NO, **NEW_STEP)
    StepConfig.objects.filter(step_no=6, description=OLD_STEP_SIX_DESCRIPTION).update(
        description=NEW_STEP_SIX_DESCRIPTION
    )
    _seed_default_fields(FormTemplate, FormField)


def reverse(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    FormTemplate = apps.get_model("details", "DynamicFormTemplate")
    FormField = apps.get_model("details", "DynamicFormField")
    Proposal = apps.get_model("proposals", "Proposal")
    Comment = apps.get_model("proposals", "ProposalSectionComment")

    step = StepConfig.objects.filter(step_no=NEW_STEP_NO, title=NEW_STEP["title"]).first()
    if step is None:
        return

    step.delete()
    # Only the built-in field set is removed with the step. A form an admin
    # built on the step is detached instead, so the office's own fields stay
    # in the builder library.
    forms = FormTemplate.objects.filter(applies_to="PROPOSAL", proposal_wizard_step=NEW_STEP_NO)
    seeded = forms.filter(slug__startswith=f"step-{NEW_STEP_NO}-fields")
    seeded_ids = list(seeded.values_list("id", flat=True))
    # Delete the fields by hand: the historical models' cascade cannot walk the
    # answers/rows hanging off a field the way the live models do.
    apps.get_model("details", "DynamicFormAnswer").objects.filter(field__form_id__in=seeded_ids).delete()
    apps.get_model("details", "DynamicFormRow").objects.filter(response__form_id__in=seeded_ids).delete()
    apps.get_model("details", "DynamicFormResponse").objects.filter(form_id__in=seeded_ids).delete()
    FormField.objects.filter(form_id__in=seeded_ids).delete()
    FormTemplate.objects.filter(id__in=seeded_ids).delete()
    forms.update(proposal_wizard_step=None)
    Comment.objects.filter(step_no=NEW_STEP_NO).delete()

    _shift_step_forms(FormTemplate, -1)
    _shift_reviewer_comments(Comment, -1)
    _shift_step_table(StepConfig, -1)
    _shift_proposal_progress(Proposal, -1)

    StepConfig.objects.filter(step_no=6, description=NEW_STEP_SIX_DESCRIPTION).update(
        description=OLD_STEP_SIX_DESCRIPTION
    )


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0026_undo_wizard_flow_split"),
        ("proposals", "0050_utility_model_fields"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
