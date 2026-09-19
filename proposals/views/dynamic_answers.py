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

from django.db.models import Q

from details.models import DynamicFormAnswer, DynamicFormField, DynamicFormResponse, DynamicFormTemplate

from .dynamic_fields import (
    dependency_parent_value as _dependency_parent_value,
    dynamic_field_blocks_submission as _dynamic_field_blocks_submission,
    dynamic_parent_values_from_post as _dynamic_parent_values_from_post,
    dynamic_parent_values_from_saved as _dynamic_parent_values_from_saved,
)
from .repeaters import (
    attach_repeater_rows,
    proponent_repeater_form_for_step,
    repeater_missing,
    save_repeater_rows,
)


def _is_dynamic_step_complete(proposal, step):
    """Whether every required office-built field on this step is filled in.

    Resolved through the step row, so a form the office attached to the step
    gates it exactly like one pinned to its number does.
    """
    forms = [
        form
        for form in _dynamic_forms_for_proposal_step(step)
        if form.blocks_proposal_submission
    ]

    if not forms:
        return True

    responses = {
        res.form_id: res
        for res in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers")
    }

    saved_values = _dynamic_parent_values_from_saved(proposal)

    def _blocking_field_without_value(form, field, answer):
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


def _forms_bound_to_step(flow, applies_to, step_no, attachment_field):
    """Office-built forms shown on one step of one wizard.

    Two bindings are honoured:

    * ``attached_*_steps`` — the office picked the form for this step in the
      wizard manager. This is the one that survives reordering, because it
      points at the step *row*;
    * ``proposal_wizard_step`` — the original "pin to step number" field, kept
      so forms configured before the wizard became reorderable still show up.
    """
    queryset = DynamicFormTemplate.objects.filter(is_active=True, applies_to=applies_to)
    config = flow.get(step_no)
    if config is None:
        queryset = queryset.filter(proposal_wizard_step=step_no)
    else:
        condition = Q(**{attachment_field: config})
        if applies_to == DynamicFormTemplate.AppliesTo.PROPOSAL:
            condition |= Q(proposal_wizard_step=step_no)
        queryset = queryset.filter(condition).distinct()

    return queryset.prefetch_related("fields").order_by("name")


def _dynamic_forms_for_proposal_step(step):
    from .wizard_flows import proposal_flow

    return _forms_bound_to_step(
        proposal_flow,
        DynamicFormTemplate.AppliesTo.PROPOSAL,
        step,
        "attached_proposal_steps",
    )


def _dynamic_forms_for_moa_step(step):
    from .wizard_flows import moa_flow

    return _forms_bound_to_step(
        moa_flow,
        DynamicFormTemplate.AppliesTo.MOA,
        step,
        "attached_moa_steps",
    )


def _proposal_step_section(step):
    """The built-in part on a proposal step, if it has one."""
    from .wizard_flows import proposal_flow

    return proposal_flow.section(step)


def _attach_dynamic_forms_to_context(
    ctx,
    proposal,
    step,
    *,
    forms=None,
    exclude_keys=(),
    proponent_inline=False,
):
    """Put the step's office-built forms (and their saved answers) in context.

    ``forms`` lets a caller pass its own set — the MOA wizard does, since its
    steps are a different table. ``proponent_inline`` is set when the step's
    built-in part is the proponent roster: that group is printed inside the
    part's own template rather than in the generic block below, so it must not
    be rendered twice.
    """
    if forms is None:
        forms = list(_dynamic_forms_for_proposal_step(step))
    else:
        forms = list(forms)

    # Only one form may own the proposal's proponent rows: a duplicate would
    # print - and save - the same rows twice.
    ctx["proponent_repeater_form"] = None
    ctx["proponent_repeater_active"] = False

    kept = []
    seen_proponent_repeater = False
    for form in forms:
        if form.is_proponent_repeater:
            if seen_proponent_repeater:
                continue
            seen_proponent_repeater = True
            if proponent_inline:
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

        # A dynamic field whose key matches one the built-in part already
        # renders would print the same input twice.
        form.fields_to_render = [f for f in all_fields if f.field_key not in exclude_keys]

    ctx["dynamic_forms"] = forms
    return forms


def _attach_proposal_dynamic_forms(ctx, proposal, step):
    """Proposal-wizard wrapper: resolves the step's forms and its owned keys."""
    section = _proposal_step_section(step)
    return _attach_dynamic_forms_to_context(
        ctx,
        proposal,
        step,
        forms=_dynamic_forms_for_proposal_step(step),
        exclude_keys=section.owned_keys if section is not None else (),
        proponent_inline=bool(section is not None and section.key == "proponents"),
    )


def _attach_moa_dynamic_forms(ctx, proposal, step):
    """MOA-wizard wrapper: its steps hold their own attached forms."""
    return _attach_dynamic_forms_to_context(
        ctx,
        proposal,
        step,
        forms=_dynamic_forms_for_moa_step(step),
    )


def _save_dynamic_form_answers(proposal, step, user, request, forms=None):
    """Save admin-built dynamic fields attached to the current wizard step.

    Returns a list of missing required field labels. Values are saved even when
    some required fields are still empty so proponents can draft gradually.
    Required fields whose ``depends_on`` condition is not met are skipped:
    the user never saw them, so they cannot be missing.

    Repeatable groups are skipped here: their rows are saved (and validated) by
    ``proposals.views.repeaters`` because they do not live in
    ``DynamicFormAnswer``.
    """
    if forms is None:
        forms = _dynamic_forms_for_proposal_step(step)
    forms = [form for form in forms if not form.is_repeater]
    missing = []
    post_values = _dynamic_parent_values_from_post(forms, request)

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
                missing.append(f"{form.name}: {field.label}")

    return missing


def _save_step_repeaters(proposal, step, request, user):
    """Save every repeatable group on this step.

    The proponent group is saved by the step whose built-in part is the
    roster, because that path also drives the creator's role and the per-phase
    project leaders.
    """
    section = _proposal_step_section(step)
    on_proponent_step = bool(section is not None and section.key == "proponents")

    missing = []
    for form in _dynamic_forms_for_proposal_step(step):
        if not form.is_repeater:
            continue
        if on_proponent_step and form.is_proponent_repeater:
            # The proponents part saves its own group, because that path also
            # sorts out the creator's role and the per-phase project leaders.
            continue
        form_missing, _meta = save_repeater_rows(proposal, form, request, user)
        missing.extend(form_missing)
    return missing


def _proposal_dynamic_requirements_missing(proposal):
    """Missing required office-built fields across every visible wizard step.

    Resolved step by step, so a form counts wherever the office put it: pinned
    to a step number or attached to the step row. A form on a step the office
    has hidden is not a requirement any more, because the step is not part of
    the flow.
    """
    from .wizard_flows import proposal_flow

    proposal_flow.ensure_defaults()

    saved_values = _dynamic_parent_values_from_saved(proposal)
    missing = []

    for step_config in proposal_flow.visible():
        forms = [
            form
            for form in _dynamic_forms_for_proposal_step(step_config.step_no)
            if form.blocks_proposal_submission
        ]
        if not forms:
            continue

        step_label = f"Step {step_config.step_no}"
        responses = {
            response.form_id: response
            for response in DynamicFormResponse.objects.filter(
                proposal=proposal,
                form__in=forms,
            ).prefetch_related("answers")
        }

        for form in forms:
            if form.is_repeater:
                missing.extend(
                    f"{step_label} — {form.name}: {item}"
                    for item in repeater_missing(proposal, form)
                )
                continue

            response = responses.get(form.id)
            answer_map = {}
            if response:
                answer_map = {answer.field_id: answer for answer in response.answers.all()}

            for field in form.fields.all():
                if not field.required:
                    continue
                parent_value = _dependency_parent_value(
                    proposal, field.depends_on_key, saved_values=saved_values
                )
                if not _dynamic_field_blocks_submission(form, field, parent_value):
                    continue
                answer = answer_map.get(field.id)
                if not answer or not answer.has_value:
                    missing.append(f"{step_label} — {form.name}: {field.label}")

    return missing


def _save_moa_dynamic_form_answers(proposal, step, user, request):
    """Save the office-built fields attached to an MOA drafting step."""
    return _save_dynamic_form_answers(
        proposal,
        step,
        user,
        request,
        forms=_dynamic_forms_for_moa_step(step),
    )


def _is_moa_dynamic_step_complete(proposal, step):
    """Whether every required office-built field on an MOA step is filled in."""
    forms = [
        form
        for form in _dynamic_forms_for_moa_step(step)
        if form.blocks_proposal_submission and not form.is_repeater
    ]
    if not forms:
        return True

    responses = {
        response.form_id: response
        for response in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers")
    }

    for form in forms:
        response = responses.get(form.id)
        answer_map = {answer.field_id: answer for answer in response.answers.all()} if response else {}
        for field in form.fields.all():
            if not field.required:
                continue
            answer = answer_map.get(field.id)
            if not answer or not answer.has_value:
                return False
    return True
