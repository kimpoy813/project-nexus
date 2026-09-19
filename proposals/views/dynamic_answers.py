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
from details.models import WizardFlow

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


def _wizard_flow_filter(proposal):
    """Q filter limiting step-attached forms to a proposal's wizard flow.

    Forms with a blank ``wizard_flow`` are shared by every flow (the seeded
    proponent repeater, for example); forms tagged RESEARCH or TRAINING only
    belong to that flow's steps. While the extension type is unset the
    proposal has only reached the shared Step 1, so only shared forms apply.
    """
    from django.db.models import Q

    flow = WizardFlow.flow_for_extension_type(proposal.extension_type) if proposal else None
    if flow:
        return Q(wizard_flow="") | Q(wizard_flow=flow)
    return Q(wizard_flow="")


def _is_dynamic_step_complete(proposal, step):
    forms = DynamicFormTemplate.objects.filter(
        is_active=True,
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step=step,
        blocks_proposal_submission=True,
    ).filter(_wizard_flow_filter(proposal)).prefetch_related("fields")
    
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


def _dynamic_forms_for_proposal_step(step, proposal=None):
    return (
        DynamicFormTemplate.objects.filter(
            is_active=True,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step,
        )
        .filter(_wizard_flow_filter(proposal))
        .prefetch_related("fields")
        .order_by("name")
    )


def _attach_dynamic_forms_to_context(ctx, proposal, step):
    forms = list(_dynamic_forms_for_proposal_step(step, proposal))

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
            step_fields[field.field_key] = field

    ctx["step_fields"] = step_fields

    # Native inputs the step templates render themselves, per flow: the same
    # step number holds different sections in the two forms.
    flow = WizardFlow.flow_for_extension_type(proposal.extension_type) if proposal else None
    hardcoded_keys_by_flow_step = {
        ("ANY", 1): {"extension_type", "scope_type", "research_title"},
        ("ANY", 2): {"title"},
        ("ANY", 4): {"implementing_agency"},
        ("ANY", 5): {"beneficiaries_count", "who_beneficiaries", "beneficiaries_who"},
        ("RESEARCH", 7): {
            "technology_title",
            "utility_model_registration_number",
            "utility_model_description",
        },
        ("RESEARCH", 8): {"budgetary_requirement"},
        ("RESEARCH", 11): {"extension_venue", "estimated_month", "estimated_year"},
        ("RESEARCH", 12): {"rationale_background"},
        ("RESEARCH", 13): {"significance"},
        ("RESEARCH", 14): {"general_objective"},
        ("RESEARCH", 19): {"monitoring_eval"},
        ("TRAINING", 9): {"extension_venue"},
        ("TRAINING", 11): {"budgetary_requirement"},
        ("TRAINING", 12): {"rationale_background"},
        ("TRAINING", 14): {"general_objective"},
    }
    exclude_keys = set(hardcoded_keys_by_flow_step.get(("ANY", step), set()))
    if flow:
        exclude_keys |= hardcoded_keys_by_flow_step.get((flow, step), set())
    elif step > 1:
        # Not picked a type yet: the classic research-shaped list.
        exclude_keys |= hardcoded_keys_by_flow_step.get(("RESEARCH", step), set())

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
    forms = [form for form in _dynamic_forms_for_proposal_step(step, proposal) if not form.is_repeater]
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

    Step 3's proponent group is saved by the step 3 branch instead, because it
    also drives the creator's role and the per-phase project leaders.
    """
    missing = []
    for form in _dynamic_forms_for_proposal_step(step, proposal):
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
        .filter(_wizard_flow_filter(proposal))
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
        step_label = f"Step {form.proposal_wizard_step}" if form.proposal_wizard_step else "Proposal wizard"

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
            if not field.required:
                continue
            parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
            answer = answer_map.get(field.id)
            if not _dynamic_field_blocks_submission(form, field, parent_value):
                continue
            if not answer or not answer.has_value:
                missing.append(f"{step_label} — {form.name}: {field.label}")

    return missing
