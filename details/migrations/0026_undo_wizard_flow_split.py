"""
Collapse the two wizard flows back into PR #28's single 19-step list.

PR #32 ("Split the proposal wizard into the two office forms") and PR #33
("Split Utility Model into its own proposal wizard step") were both reverted,
so the code is back at PR #28 ("Step 3 proponents: admin-defined repeatable
group"): one wizard, no ``flow`` tag on a step, no Training Design fields on
``Proposal``.

``0022``-``0025`` (and ``proposals`` ``0047``/``0048``) stay in this tree as
frozen history because production databases may already have run them -
``build.sh`` applies migrations on every deploy - which is the same reason
``0021`` kept the reverted PR #30's migrations. Reverting only the code would
leave those databases with NOT NULL columns the restored models do not know
about (``flow``, ``wizard_flow``), so the next INSERT from the restored code -
the wizard seeding its steps, an admin adding a step or saving a step form -
would fail with an integrity error.

This migration rolls the data and the schema forward to the restored models:

* deletes the TRAINING steps plus the three steps the split added to the
  research list (ISPSC Extension Agenda, Utility Model, Monitoring and
  Evaluation Mechanics),
* renumbers the surviving research steps - and any admin-added extra step -
  back onto the PR #28 list, and restores the step 6 title the split
  overwrote,
* carries each proposal's completed/skipped/current step back through the same
  map, so a research draft resumes on the section it was really answering,
* re-points reviewer comments and admin-built step forms at the restored
  numbers, folding two comments that now belong to one reviewer on one step
  into a single comment and detaching forms that only existed for the training
  flow,
* drops ``flow`` and the ``(flow, step_no)`` constraint, drops
  ``wizard_flow``, and restores ``step_no``'s unique index and the ``step_no``
  ordering.

On a database that never ran the split, ``0022``-``0025`` and this migration
apply in sequence and cancel out, so a fresh install ends at the same schema
*and* the same seeded 19-step list as PR #28.

Two losses the split already caused cannot be undone here:

* ``0023`` threw away progress above step 6 for community- and request-based
  drafts, because the old steps 7+ meant different sections in the Training
  Design form. Those drafts resume at step 7 of the restored wizard.
* ``0023`` renumbered reviewer comments and admin-built step forms with an
  ascending in-place UPDATE, which piled every row from the old steps 7-18
  onto one step - and aborted the migration outright when a single reviewer
  had commented on two of those steps, because
  ``unique_section_comment_per_reviewer_step_round`` forbids two comments from
  one reviewer on one step. A database that got through it keeps the pile, and
  this migration can only map those numbers back positionally, so the
  surviving rows land together on one restored step instead of their original
  ones. ``0023`` and ``0025`` are patched to renumber downwards, so a database
  that never applied them - including one where they aborted - now gets an
  exact renumbering that this migration inverts exactly.

Unapplying it (``migrate details 0025``) restores the split *schema* only; the
renumbering back to two flows is not reconstructable, the same position
``0023`` and ``0025`` took.
"""

from django.db import migrations, models


RESEARCH_TYPES = ("RESEARCH_FACULTY", "RESEARCH_STUDENT")

# Steps the split added to the research list. None of them exists in PR #28:
# the agenda answers fold back into step 6, the utility model and the M&E
# attachment go away with the revert.
SPLIT_ONLY_STEPS = (7, 8, 20)

LAST_SPLIT_STEP = 22        # Certificate of Completion Upload, the last seeded step
REMOVED_STEPS = 3           # admin extras above it move down by this much

# The step table and each proposal's step bookkeeping were renumbered by 0023
# and then shifted again by 0025: post-split research number -> PR #28 number.
STEP_REVERSE = {
    9: 7,    # Budgetary Requirement
    10: 8,   # Participants / Proposed Clients
    11: 9,   # Gender Issues / Mandates Addressed
    12: 10,  # Date and Venue / Extension Site
    13: 11,  # Rationale / Background
    14: 12,  # Significance
    15: 13,  # Objectives
    16: 14,  # Methodology / Mechanics
    17: 15,  # Output / Outcome
    18: 16,  # Details of Activities
    19: 17,  # Funding Strategy
    21: 18,  # Research Abstract Upload
    22: 19,  # Certificate of Completion Upload
}

# Reviewer comments (once 0025's +1 is undone) and admin-built step forms
# (which 0025 never shifted) sit in 0023's numbering, so they reverse through
# 0023's table. 7 and 19 were the new agenda and M&E steps; they fold into the
# sections they came out of rather than orphaning feedback on a step the
# restored wizard no longer has.
SECTION_REVERSE = {
    7: 6,    # ISPSC Extension Agenda -> SDGs / Extension Agenda
    8: 7,    # Budgetary Requirement
    9: 8,    # Participants / Proposed Clients
    10: 9,   # Gender Issues / Mandates Addressed
    11: 10,  # Date and Venue / Extension Site
    12: 11,  # Rationale / Background
    13: 12,  # Significance
    14: 13,  # Objectives
    15: 14,  # Methodology / Mechanics
    16: 15,  # Output / Outcome
    17: 16,  # Details of Activities
    18: 17,  # Funding Strategy
    19: 17,  # Monitoring and Evaluation Mechanics -> Funding Strategy
    20: 18,  # Research Abstract Upload
    21: 19,  # Certificate of Completion Upload
    22: 19,  # (post-0025 numbering) Certificate of Completion Upload
}

# 0023 and 0024 both rewrote step 6; put PR #28's wording back so the label
# matches the restored step_6.html, which collects SDGs *and* the agenda.
SPLIT_STEP_SIX_TITLES = ("SDGs Covered / Extension Agenda", "SDGs Covered")
STEP_SIX_TITLE = "SDGs / Extension Agenda"
STEP_SIX_DESCRIPTION = "SDGs covered and extension thrust"


def _section_target(step_no):
    """PR #28 step number for a row that is still in 0023's numbering."""
    if step_no in SECTION_REVERSE:
        return SECTION_REVERSE[step_no]
    if step_no > LAST_SPLIT_STEP:
        return max(1, step_no - REMOVED_STEPS)
    return step_no


def _comment_target(step_no, is_research):
    """PR #28 step number for a reviewer comment.

    0025 moved research proposals' comments up one step on top of 0023's
    renumbering, so undo that shift first and both flows of numbering reverse
    through the same table.
    """
    if is_research:
        if step_no >= 9:
            step_no -= 1
        elif step_no == 8:
            # 0025 vacated step 8 for research proposals: anything sitting
            # there was written against the Utility Model step.
            return 6
    return _section_target(step_no)


def _progress_target(step_no):
    """PR #28 step number for a proposal's step bookkeeping, or None to drop.

    The three steps the split added are dropped rather than folded in: marking
    the section before them complete would let a draft past a required step it
    never answered.
    """
    if not step_no:
        return None
    if step_no in STEP_REVERSE:
        return STEP_REVERSE[step_no]
    if step_no in SPLIT_ONLY_STEPS:
        return None
    if step_no > LAST_SPLIT_STEP:
        return step_no - REMOVED_STEPS
    return step_no


def _pointer_target(step_no):
    """PR #28 step number for a proposal's ``current_step`` pointer.

    0025 shifted the step table and each draft's completed/skipped lists, but
    it left ``current_step`` alone, so the pointer is still in 0023's
    numbering and reverses through the same table as the comments and the
    admin-built step forms.
    """
    if not step_no:
        return None
    return _section_target(step_no)


def restore_step_table(apps):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")

    # The Training Design flow goes away with the split, and so do the three
    # steps the split added to the research list.
    StepConfig.objects.filter(flow="TRAINING").delete()
    StepConfig.objects.filter(flow="RESEARCH", step_no__in=SPLIT_ONLY_STEPS).delete()

    # Renumber upwards (9 -> 7, 10 -> 8, ...): every target is either a step
    # deleted just above or one the previous row vacated, so the (flow,
    # step_no) constraint that is still in place cannot be tripped.
    for split_no in sorted(STEP_REVERSE):
        StepConfig.objects.filter(flow="RESEARCH", step_no=split_no).update(
            step_no=STEP_REVERSE[split_no]
        )

    _shift_admin_extras(StepConfig)
    _absorb_shared_flow_steps(StepConfig)
    StepConfig.objects.filter(step_no=6, title__in=SPLIT_STEP_SIX_TITLES).update(
        title=STEP_SIX_TITLE, description=STEP_SIX_DESCRIPTION
    )
    _dedupe_step_numbers(StepConfig)


def _shift_admin_extras(StepConfig):
    """Admin steps added past the seeded list follow the renumbering down."""
    rows = list(
        StepConfig.objects.filter(flow="RESEARCH", step_no__gt=LAST_SPLIT_STEP)
        .order_by("step_no", "id")
        .values_list("id", "step_no")
    )
    for row_id, step_no in rows:
        StepConfig.objects.filter(id=row_id).update(step_no=step_no - REMOVED_STEPS)


def _absorb_shared_flow_steps(StepConfig):
    """Fold steps an admin tagged ALL into the single list.

    Step 1 is shared by every proposal and keeps its number. Anything else an
    admin tagged ALL while the split was live keeps its number too - the two
    flows numbered their steps independently, so once ``flow`` is dropped a
    number can be taken twice. A collision moves to the end of the list, where
    an admin can put it back in the Wizard Step Manager; an extra step above
    the seeded list follows the research extras down by the three steps that
    disappeared.
    """
    moving = list(
        StepConfig.objects.filter(flow="ALL")
        .exclude(step_no=1)
        .order_by("step_no", "id")
        .values_list("id", "step_no")
    )
    used = set(
        StepConfig.objects.exclude(id__in=[row_id for row_id, _ in moving]).values_list(
            "step_no", flat=True
        )
    )
    next_free = (max(used) + 1) if used else 1
    for row_id, step_no in moving:
        if step_no > LAST_SPLIT_STEP:
            step_no -= REMOVED_STEPS
        if step_no in used:
            while next_free in used:
                next_free += 1
            step_no = next_free
            next_free += 1
        StepConfig.objects.filter(id=row_id).update(step_no=step_no)
        used.add(step_no)


def _dedupe_step_numbers(StepConfig):
    """Last guard before ``step_no`` becomes unique again.

    Nothing above should leave two rows on one number, but a duplicate would
    abort the deploy on the ALTER TABLE, so push any collision to the end of
    the list instead - an admin can move it back in the Wizard Step Manager.
    """
    used = set()
    rows = list(StepConfig.objects.order_by("step_no", "id").values_list("id", "step_no"))
    for row_id, step_no in rows:
        if step_no in used:
            step_no = max(used) + 1
            while step_no in used:
                step_no += 1
            StepConfig.objects.filter(id=row_id).update(step_no=step_no)
        used.add(step_no)


def restore_proposal_progress(apps):
    """Map each draft's step bookkeeping back onto the PR #28 numbering."""
    Proposal = apps.get_model("proposals", "Proposal")
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")

    visible = list(
        StepConfig.objects.filter(is_visible=True)
        .order_by("step_no")
        .values_list("step_no", flat=True)
    ) or [1]

    rows = list(
        Proposal.objects.all().values_list(
            "id", "completed_steps", "skipped_steps", "current_step"
        )
    )
    for proposal_id, completed_steps, skipped_steps, current_step in rows:
        completed = {
            target
            for target in (_progress_target(no) for no in (completed_steps or []))
            if target
        }
        skipped = {
            target
            for target in (_progress_target(no) for no in (skipped_steps or []))
            if target
        }
        skipped -= completed

        current = _pointer_target(current_step)
        if current not in visible:
            # It pointed at a step the split added, or at nothing at all:
            # resume on the first section the draft has not answered.
            answered = completed | skipped
            current = next((no for no in visible if no not in answered), visible[-1])

        Proposal.objects.filter(id=proposal_id).update(
            completed_steps=sorted(completed),
            skipped_steps=sorted(skipped),
            current_step=current,
        )


def restore_reviewer_comments(apps):
    Comment = apps.get_model("proposals", "ProposalSectionComment")

    # Materialise the rows first: folding two comments into one deletes a row,
    # and a streaming queryset would skip whatever sat behind it.
    rows = list(
        Comment.objects.order_by("step_no", "id").values(
            "id", "step_no", "proposal__extension_type"
        )
    )
    for row in rows:
        comment = Comment.objects.filter(id=row["id"]).first()
        if comment is None:
            continue  # already folded into another comment on this step
        _move_comment(
            Comment,
            comment,
            _comment_target(row["step_no"], row["proposal__extension_type"] in RESEARCH_TYPES),
        )


def _move_comment(Comment, comment, target):
    if target == comment.step_no:
        return

    clash = (
        Comment.objects.filter(
            proposal_id=comment.proposal_id,
            review_round_id=comment.review_round_id,
            reviewer_id=comment.reviewer_id,
            step_no=target,
        )
        .exclude(id=comment.id)
        .first()
    )
    if clash is None:
        comment.step_no = target
        comment.save(update_fields=["step_no"])
        return

    # Two sections folded back onto one step - the agenda and utility-model
    # comments join step 6, which is where the office answered both before the
    # split. Keep both texts on the older comment instead of deleting a
    # reviewer's feedback, and keep it visible if either part was.
    keep, drop = (comment, clash) if comment.created_at <= clash.created_at else (clash, comment)
    keep.comment = "{}\n\n---\n\n{}".format(keep.comment.rstrip(), drop.comment.strip())
    keep.is_resolved = keep.is_resolved and drop.is_resolved
    keep.is_visible_to_proponent = keep.is_visible_to_proponent or drop.is_visible_to_proponent
    keep.save(update_fields=["comment", "is_resolved", "is_visible_to_proponent"])
    drop.delete()


def restore_step_forms(apps):
    """Re-point admin-built step forms at the restored step numbers."""
    FormTemplate = apps.get_model("details", "DynamicFormTemplate")

    # A form built for the Training Design flow has no step to sit on any
    # more. Detach it: it stays in the builder library and an admin can point
    # it at the single wizard again, which beats silently hanging a training
    # section off an unrelated research step.
    FormTemplate.objects.filter(wizard_flow="TRAINING").update(proposal_wizard_step=None)

    rows = list(
        FormTemplate.objects.filter(
            applies_to="PROPOSAL", proposal_wizard_step__isnull=False
        )
        .order_by("proposal_wizard_step", "id")
        .values_list("id", "proposal_wizard_step")
    )
    for form_id, step_no in rows:
        target = _section_target(step_no)
        if target != step_no:
            FormTemplate.objects.filter(id=form_id).update(proposal_wizard_step=target)


def apply(apps, schema_editor):
    restore_step_forms(apps)
    restore_reviewer_comments(apps)
    restore_step_table(apps)
    restore_proposal_progress(apps)


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0025_split_utility_model_step"),
        ("proposals", "0049_undo_flow_split_fields"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="proposalwizardstepconfig",
            name="unique_wizard_step_per_flow",
        ),
        migrations.AlterModelOptions(
            name="proposalwizardstepconfig",
            options={"ordering": ["step_no"]},
        ),
        migrations.RemoveField(
            model_name="dynamicformtemplate",
            name="wizard_flow",
        ),
        migrations.RemoveField(
            model_name="proposalwizardstepconfig",
            name="flow",
        ),
        migrations.AlterField(
            model_name="proposalwizardstepconfig",
            name="step_no",
            field=models.PositiveSmallIntegerField(unique=True),
        ),
    ]
