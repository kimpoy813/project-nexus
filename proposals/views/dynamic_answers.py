"""
Admin-built dynamic forms inside the wizard: rendering, saving, and the
required-field gates.

Split out of ``wizard.py`` (which had grown past the 1,400-line guard in
``accounts/tests/test_structure.py``). These helpers are re-imported by
``wizard.py`` so the old import paths keep working, and re-exported from
``proposals.views``.

Repeatable groups are the exception: their rows are not ``DynamicFormAnswer``
records, so they are delegated to ``proposals.views.repeaters``.

A step's layout decides how its fields are treated:

* ``BUILTIN`` layout: the step's classic system form owns the Proposal
  columns it has always saved. An admin field mapped to one of those columns
  (see ``builtin_handled_keys``) is a label override for the system input -
  it is neither rendered nor validated a second time, so it can never block
  the step. Unmapped admin fields render as extra questions below the system
  form.
* ``DYNAMIC`` layout: the admin-built form is the whole step. Every field
  renders, validates, and saves; a field with ``maps_to_proposal`` also
  writes its answer into the real Proposal column so the generated DOCX
  forms, review screens, and dashboards keep reading it.
"""

from details.models import DynamicFormAnswer, DynamicFormField, DynamicFormResponse, DynamicFormTemplate

from .dynamic_fields import (
    dependency_parent_value as _dependency_parent_value,
    dynamic_field_blocks_submission as _dynamic_field_blocks_submission,
    dynamic_parent_values_from_post as _dynamic_parent_values_from_post,
    dynamic_parent_values_from_saved as _dynamic_parent_values_from_saved,
)
from .repeaters import (
    attach_repeater_rows,
    repeater_missing,
    save_repeater_rows,
)
from .wizard_builtin import builtin_handled_keys, uses_builtin_form


#: Proposal columns a dynamic field may map to that hold integers. Values are
#: coerced before writing; an unparsable or empty value clears the column.
_INTEGER_PROPOSAL_COLUMNS = {"beneficiaries_count", "estimated_year"}


def _proposal_column_value(proposal, column):
    """Current value of a mapped Proposal column, as a string for templates."""
    raw = getattr(proposal, column, None)
    if raw is None:
        return ""
    return str(raw)


def _write_mapped_proposal_value(proposal, column, raw_value, changed_columns):
    """Write one mapped field's answer into its Proposal column.

    Mapped fields keep the office's rebuilt step feeding the same columns the
    built-in form used to fill, so generated documents and reports do not
    notice the change. Empty values clear the column (the proponent deleted
    their answer); unparsable integers are dropped rather than crashing.
    """
    if column not in _INTEGER_PROPOSAL_COLUMNS:
        setattr(proposal, column, (raw_value or "").strip())
        changed_columns.add(column)
        return

    text = (raw_value or "").strip()
    if not text:
        setattr(proposal, column, None)
        changed_columns.add(column)
        return
    if text.lstrip("-").isdigit():
        setattr(proposal, column, int(text))
        changed_columns.add(column)


def _field_is_builtin_override(field, handled_keys):
    """True when ``field`` only relabels an input the system form owns.

    Matched by the admin's explicit ``maps_to_proposal`` mapping, or - for the
    seeded defaults - by a field key equal to the Proposal column name.
    """
    if field.maps_to_proposal:
        return field.maps_to_proposal in handled_keys
    return field.field_key in handled_keys


def _mapped_column_for_field(field, handled_keys):
    """The Proposal column ``field`` writes to, if any (and if not an override)."""
    if _field_is_builtin_override(field, handled_keys):
        return ""
    return field.maps_to_proposal or ""


def _is_dynamic_step_complete(proposal, step):
    forms = DynamicFormTemplate.objects.filter(
        is_active=True,
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step=step,
        blocks_proposal_submission=True,
    ).prefetch_related("fields")

    if not forms.exists():
        return True

    responses = {
        res.form_id: res
        for res in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers")
    }

    saved_values = _dynamic_parent_values_from_saved(proposal)
    handled_keys = builtin_handled_keys(step)

    def _blocking_field_without_value(form, field, answer):
        if _field_is_builtin_override(field, handled_keys):
            # Owned (and validated) by the step's built-in system form.
            return False
        parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
        if not _dynamic_field_blocks_submission(form, field, parent_value):
            return False
        return not answer or not answer.has_value

    for form in forms:
        if form.is_repeater:
            # Repeatable groups keep their rows outside DynamicFormAnswer.
            if repeater_missing(proposal, form):
                return False
            continue

        res = responses.get(form.id)
        answer_map = {ans.field_id: ans for ans in res.answers.all()} if res else {}

        for field in form.fields.all():
            if _blocking_field_without_value(form, field, answer_map.get(field.id)):
                return False
    return True


def _dynamic_forms_for_proposal_step(step):
    return (
        DynamicFormTemplate.objects.filter(
            is_active=True,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step,
        )
        .prefetch_related("fields")
        .order_by("name")
    )


def _attach_dynamic_forms_to_context(ctx, proposal, step):
    forms = list(_dynamic_forms_for_proposal_step(step))
    builtin_step = uses_builtin_form(step)

    # Only the first form on a step may own the proposal's proponent rows: a
    # duplicate form would otherwise print - and save - the same rows twice.
    # While the step keeps its built-in layout, that form is rendered inline by
    # step_3.html (above the project-leader panel). On a custom-layout step it
    # renders through the generic dynamic template like any other form.
    ctx["proponent_repeater_form"] = None
    ctx["proponent_repeater_active"] = False

    kept = []
    seen_proponent_repeater = False
    for form in forms:
        if form.is_proponent_repeater:
            if seen_proponent_repeater:
                continue
            seen_proponent_repeater = True
            if builtin_step and step == 3:
                ctx["proponent_repeater_form"] = form
                ctx["proponent_repeater_active"] = True
                continue
        kept.append(form)
    forms = kept

    attach_repeater_rows(proposal, [form for form in forms if form.is_repeater])
    if ctx["proponent_repeater_form"] is not None:
        attach_repeater_rows(proposal, [ctx["proponent_repeater_form"]])

    if not forms:
        ctx["dynamic_forms"] = []
        ctx["step_fields"] = {}
        return []

    responses = {
        response.form_id: response
        for response in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers", "answers__field")
    }

    step_fields = {}
    for form in forms:
        for field in form.fields.all():
            step_fields[field.field_key] = field

    ctx["step_fields"] = step_fields

    # Fields the step's built-in system form already renders (by mapping or -
    # for the seeded defaults - by field key) stay hidden in the "extra
    # fields" box; on a custom-layout step nothing is excluded because the
    # admin-built form is the whole step.
    exclude_keys = builtin_handled_keys(step)

    for form in forms:
        response = responses.get(form.id)
        answer_by_field = {}
        if response:
            answer_by_field = {answer.field_id: answer for answer in response.answers.all()}
        form.response = response

        all_fields = list(form.fields.all())
        for field in all_fields:
            answer = answer_by_field.get(field.id)
            field.answer = answer
            field.answer_value = getattr(answer, "value", "") if answer else ""
            field.answer_file = getattr(answer, "file", None) if answer else None
            # A field mapped to a Proposal column shows the column's current
            # value (what the generated documents print), so switching a step
            # between layouts never hides data the proponent already entered.
            if field.maps_to_proposal:
                column_value = _proposal_column_value(proposal, field.maps_to_proposal)
                if column_value:
                    field.answer_value = column_value

        form.fields_to_render = [f for f in all_fields if not _field_is_builtin_override(f, exclude_keys)]

    # A form whose every field is a label override for the system form's own
    # inputs has nothing of its own to print (and one with no fields at all is
    # an empty card): keep both out of the render list so no duplicate inputs
    # or empty boxes appear. Everything stays reachable through ``step_fields``.
    ctx["dynamic_forms"] = [
        form for form in forms
        if form.is_repeater or form.fields_to_render
    ]
    return forms


def _save_dynamic_form_answers(proposal, step, user, request):
    """Save admin-built dynamic fields attached to the current wizard step.

    Returns a list of missing required field labels. Values are saved even when
    some required fields are still empty so proponents can draft gradually.
    Required fields whose ``depends_on`` condition is not met are skipped:
    the user never saw them, so they cannot be missing.

    On a built-in-layout step, fields that only relabel the system form's own
    inputs are skipped entirely: the system form both saved and validated
    them, so counting them again would block the step forever. On any step, a
    field mapped to a Proposal column also writes its answer into that column
    so the generated documents keep reading it.

    Repeatable groups are skipped here: their rows are saved (and validated) by
    ``proposals.views.repeaters`` because they do not live in
    ``DynamicFormAnswer``.
    """
    forms = [form for form in _dynamic_forms_for_proposal_step(step) if not form.is_repeater]
    missing = []
    post_values = _dynamic_parent_values_from_post(forms, request)
    handled_keys = builtin_handled_keys(step)
    changed_columns = set()

    for form in forms:
        response, _ = DynamicFormResponse.objects.get_or_create(
            form=form,
            proposal=proposal,
            defaults={"submitted_by": user},
        )
        if response.submitted_by_id is None and user.is_authenticated:
            response.submitted_by = user
            response.save(update_fields=["submitted_by", "updated_at"])

        for field in form.fields.all():
            if _field_is_builtin_override(field, handled_keys):
                # The step's built-in system form owns this column: it already
                # saved and validated it in this same request.
                continue

            input_name = f"dynamic_field_{field.id}"
            answer, _ = DynamicFormAnswer.objects.get_or_create(
                response=response,
                field=field,
            )

            if field.field_type == DynamicFormField.FieldType.FILE:
                uploaded = request.FILES.get(input_name)
                if uploaded:
                    answer.file = uploaded
                # Keep existing file when no new file is uploaded.
                answer.value = ""
            elif field.field_type == DynamicFormField.FieldType.CHECKBOX:
                answer.value = "Yes" if request.POST.get(input_name) == "on" else ""
            else:
                answer.value = (request.POST.get(input_name) or "").strip()

            answer.save()

            if field.maps_to_proposal:
                _write_mapped_proposal_value(
                    proposal, field.maps_to_proposal, answer.value, changed_columns
                )

            parent_value = _dependency_parent_value(proposal, field.depends_on_key, post_values=post_values)
            if not answer.has_value and _dynamic_field_blocks_submission(form, field, parent_value):
                missing.append(f"{form.name}: {field.label}")

    if changed_columns:
        proposal.save(update_fields=sorted(changed_columns))

    return missing


def _save_step_repeaters(proposal, step, request, user):
    """Save every repeatable group on this step.

    While Step 3 keeps its built-in layout, its proponent group is saved by the
    built-in step saver instead, because that path also drives the creator's
    role and the per-phase project leaders. A custom-layout Step 3 saves its
    rows here like any other repeatable group.
    """
    missing = []
    for form in _dynamic_forms_for_proposal_step(step):
        if not form.is_repeater:
            continue
        if uses_builtin_form(step) and step == 3 and form.is_proponent_repeater:
            # The built-in Step 3 saver (proponents module) also sorts out the
            # creator's role and the per-phase project leaders.
            continue
        form_missing, _meta = save_repeater_rows(proposal, form, request, user)
        missing.extend(form_missing)
    return missing


def _proposal_dynamic_requirements_missing(proposal):
    """Return missing required admin-built proposal fields across all wizard steps."""
    forms = list(
        DynamicFormTemplate.objects.filter(
            is_active=True,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            blocks_proposal_submission=True,
        )
        .exclude(proposal_wizard_step__isnull=True)
        .prefetch_related("fields")
    )
    if not forms:
        return []

    responses = {
        response.form_id: response
        for response in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers")
    }

    saved_values = _dynamic_parent_values_from_saved(proposal)

    missing = []
    for form in forms:
        form_step = form.proposal_wizard_step
        step_label = f"Step {form_step}" if form_step else "Proposal wizard"
        handled_keys = builtin_handled_keys(form_step)

        if form.is_repeater:
            missing.extend(
                f"{step_label} — {form.name}: {item}" for item in repeater_missing(proposal, form)
            )
            continue

        response = responses.get(form.id)
        answer_map = {}
        if response:
            answer_map = {answer.field_id: answer for answer in response.answers.all()}

        for field in form.fields.all():
            if _field_is_builtin_override(field, handled_keys):
                # Owned by the step's built-in system form, which has its own
                # completion rule on the Proposal row itself.
                continue
            if not field.required:
                continue
            parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
            answer = answer_map.get(field.id)
            if not _dynamic_field_blocks_submission(form, field, parent_value):
                continue
            if not answer or not answer.has_value:
                missing.append(f"{step_label} — {form.name}: {field.label}")

    return missing
