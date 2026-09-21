"""
Admin-built dynamic forms inside the wizard: rendering, saving, and the
required-field gates.

Split out of ``wizard.py`` (which had grown past the 1,400-line guard in
``accounts/tests/test_structure.py``). These helpers are re-imported by
``wizard.py`` so the old import paths keep working, and re-exported from
``proposals.views``.

Repeatable groups are the exception: their rows are not ``DynamicFormAnswer``
records, so they are delegated to ``proposals.views.repeaters``.
"""

from details.models import DynamicFormAnswer, DynamicFormField, DynamicFormResponse, DynamicFormTemplate

from .dynamic_fields import (
    dependency_parent_value as _dependency_parent_value,
    dynamic_field_blocks_submission as _dynamic_field_blocks_submission,
    dynamic_parent_values_from_post as _dynamic_parent_values_from_post,
    dynamic_parent_values_from_saved as _dynamic_parent_values_from_saved,
    native_keys_for_step,
    native_post_name,
    native_saved_value,
)
from .repeaters import (
    attach_repeater_rows,
    proponent_repeater_form_for_step,
    repeater_missing,
    save_repeater_rows,
)


def _overlay_native_values(values, proposal, step):
    """Overlay the proposal's own saved values for this step's mirror fields.

    A "mirror" field is a dynamic field whose ``field_key`` matches one of the
    step's built-in inputs (``NATIVE_STEP_FIELDS``). Its value lives on the
    ``Proposal`` record - not in ``DynamicFormAnswer`` - so dependency checks
    and required-field gates must read it from there. Stale empty answers
    saved by older code must not shadow the real value.
    """
    for key in native_keys_for_step(step):
        native = native_saved_value(proposal, step, key)
        if native is not None:
            values[key] = native
    return values


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

    saved_values = _overlay_native_values(
        _dynamic_parent_values_from_saved(proposal), proposal, step
    )
    native_keys = native_keys_for_step(step)

    def _blocking_field_without_value(form, field, answer):
        parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
        if not _dynamic_field_blocks_submission(form, field, parent_value):
            return False
        if field.field_key in native_keys:
            # Mirror of a built-in input: the value is stored on the Proposal
            # record by the step's own save handler.
            return not native_saved_value(proposal, step, field.field_key)
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
        # The step editor edits the oldest attached form, so use the same
        # ordering in the proposal wizard.  That form is the step's own field
        # definition; any later forms are supplementary groups.
        .order_by("id")
    )


def _attach_dynamic_forms_to_context(ctx, proposal, step):
    forms = list(_dynamic_forms_for_proposal_step(step))
    primary_form_id = forms[0].id if forms else None
    for form in forms:
        # Templates use this only for presentation.  The primary form is the
        # field list edited on Admin -> Wizard Steps, so its generated form
        # name stays hidden and its fields read as part of the step itself.
        form.is_primary_step_form = form.id == primary_form_id
        form.show_heading = not form.is_primary_step_form

    # Only the first form on a step may own the proposal's proponent rows: a
    # duplicate form would otherwise print - and save - the same rows twice.
    # On step 3 that form is rendered inline by step_3.html (above the
    # project-leader panel) instead of at the bottom of the page.
    ctx["proponent_repeater_form"] = None
    ctx["proponent_repeater_active"] = False

    kept = []
    seen_proponent_repeater = False
    for form in forms:
        if form.is_proponent_repeater:
            if seen_proponent_repeater:
                continue
            seen_proponent_repeater = True
            if step == 3:
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
            # The primary step form owns the built-in field customisations.
            # A separately attached form may reuse a key for dependencies, but
            # it must not silently replace what the Wizard Step editor saved.
            step_fields.setdefault(field.field_key, field)

    ctx["step_fields"] = step_fields

    # Fields that mirror this step's built-in inputs (see NATIVE_STEP_FIELDS).
    # They exist so the admin can relabel the hardcoded inputs from the step
    # editor; the step template renders them through ``step_fields``, so they
    # must not be printed a second time in the extra-fields section.
    exclude_keys = native_keys_for_step(step)

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

        form.fields_to_render = [f for f in all_fields if f.field_key not in exclude_keys]

    # A form whose every field mirrors a built-in input has nothing of its own
    # to show: rendering it would only add an empty "extra fields" panel under
    # the hardcoded step.
    forms = [
        form for form in forms
        if form.is_repeater or form.fields_to_render
    ]

    ctx["dynamic_forms"] = forms
    return forms


def _save_dynamic_form_answers(proposal, step, user, request):
    """Save admin-built dynamic fields attached to the current wizard step.

    Returns a list of missing required field labels. Values are saved even when
    some required fields are still empty so proponents can draft gradually.
    Required fields whose ``depends_on`` condition is not met are skipped:
    the user never saw them, so they cannot be missing.

    Repeatable groups are skipped here: their rows are saved (and validated) by
    ``proposals.views.repeaters`` because they do not live in
    ``DynamicFormAnswer``.
    """
    forms = [form for form in _dynamic_forms_for_proposal_step(step) if not form.is_repeater]
    missing = []
    post_values = _dynamic_parent_values_from_post(forms, request)
    native_keys = native_keys_for_step(step)

    # Mirror fields post under their native input names (extension_type,
    # title, ...), not under dynamic_field_<id>, so dependency parents must
    # also be readable from those names.
    for key in native_keys:
        post_name = native_post_name(step, key)
        if post_name and post_name in request.POST:
            post_values.setdefault(key, request.POST.get(post_name, ""))

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
            input_name = f"dynamic_field_{field.id}"

            if field.field_key in native_keys:
                # Mirror of a built-in input. The step's own save handler has
                # already validated and stored the value on the Proposal
                # record; don't create a shadow DynamicFormAnswer, and don't
                # report it missing here - the native step logic owns it.
                parent_value = _dependency_parent_value(
                    proposal, field.depends_on_key, post_values=post_values
                )
                if (
                    not native_saved_value(proposal, step, field.field_key)
                    and _dynamic_field_blocks_submission(form, field, parent_value)
                ):
                    missing.append(field.label)
                continue

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

            parent_value = _dependency_parent_value(proposal, field.depends_on_key, post_values=post_values)
            if not answer.has_value and _dynamic_field_blocks_submission(form, field, parent_value):
                # This field is part of the wizard step itself.  Keep internal
                # DynamicFormTemplate names out of proponent-facing errors.
                missing.append(field.label)

    return missing


def _save_step_repeaters(proposal, step, request, user):
    """Save every repeatable group on this step.

    Step 3's proponent group is saved by the step 3 branch instead, because it
    also drives the creator's role and the per-phase project leaders.
    """
    missing = []
    for form in _dynamic_forms_for_proposal_step(step):
        if not form.is_repeater:
            continue
        if step == 3 and form.is_proponent_repeater:
            # Step 3's own group is saved by the proponents module, which also
            # sorts out the creator's role and the per-phase project leaders.
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
    # Values that live on the Proposal record (mirrors of built-in inputs)
    # take precedence over any stale empty DynamicFormAnswer rows.
    for form in forms:
        _overlay_native_values(saved_values, proposal, form.proposal_wizard_step)

    missing = []
    for form in forms:
        step_no = form.proposal_wizard_step
        step_label = f"Step {step_no}" if step_no else "Proposal wizard"

        if form.is_repeater:
            missing.extend(
                f"{step_label} — {item}" for item in repeater_missing(proposal, form)
            )
            continue

        response = responses.get(form.id)
        answer_map = {}
        if response:
            answer_map = {answer.field_id: answer for answer in response.answers.all()}

        native_keys = native_keys_for_step(step_no)

        for field in form.fields.all():
            if not field.required:
                continue
            parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
            if not _dynamic_field_blocks_submission(form, field, parent_value):
                continue
            if field.field_key in native_keys:
                # Mirror of a built-in input: read the proposal's own field.
                if not native_saved_value(proposal, step_no, field.field_key):
                    missing.append(f"{step_label} — {field.label}")
                continue
            answer = answer_map.get(field.id)
            if not answer or not answer.has_value:
                missing.append(f"{step_label} — {field.label}")

    return missing
