"""
Dependency rules for admin-built dynamic form fields.

The wizard step editor lets admins show a field only when a parent field holds
a particular value (``depends_on_key`` / ``depends_on_value``). The browser
hides non-matching fields, and these helpers let the server reach the same
conclusion so a *hidden* required field never blocks submission.
"""

from details.models import DynamicFormResponse


# Sentinel returned when a dependency's parent field cannot be located.
DEPENDENCY_PARENT_NOT_FOUND = object()


#: Built-in wizard inputs that the admin's "Fields for Step N" rows *mirror*.
#:
#: The step editor lets the office relabel the hardcoded inputs (label,
#: placeholder, help text, choices) by editing a dynamic field whose
#: ``field_key`` matches the native input's name. Those mirror fields must
#: never be rendered a second time by the configured-fields partial, and must
#: never demand their own ``dynamic_field_<id>`` answer -
#: the native save path already collects and stores the value on the
#: ``Proposal`` record itself.
#:
#: Maps step number -> {field_key: proposal attribute / native POST name}.
NATIVE_STEP_FIELDS = {
    1: {
        "extension_type": "extension_type",
        "scope_type": "scope_type",
        "research_title": "research_title",
    },
    2: {"title": "title"},
    4: {"implementing_agency": "implementing_agency"},
    5: {
        "beneficiaries_count": "beneficiaries_count",
        "beneficiaries_who": "beneficiaries_who",
        # Legacy key used by an older seed of the step 5 form.
        "who_beneficiaries": "beneficiaries_who",
    },
    # Step 7 is the Utility Model step (constants.UTILITY_MODEL_STEP_NO).
    7: {
        "technology_title": "technology_title",
        "utility_model_registration_number": "utility_model_registration_number",
        "utility_model_description": "utility_model_description",
    },
    8: {"budgetary_requirement": "budgetary_requirement"},
    11: {
        "extension_venue": "extension_venue",
        "estimated_month": "estimated_month",
        "estimated_year": "estimated_year",
    },
    12: {"rationale_background": "rationale_background"},
    13: {"significance": "significance"},
    14: {"general_objective": "general_objective"},
}


def native_keys_for_step(step):
    """The set of field keys that mirror built-in inputs on ``step``."""
    return set(NATIVE_STEP_FIELDS.get(step) or {})


def native_post_name(step, field_key):
    """POST name / Proposal attribute behind a mirror field, or ``None``."""
    return (NATIVE_STEP_FIELDS.get(step) or {}).get(field_key)


def native_saved_value(proposal, step, field_key):
    """The value the native save path stored for a mirror field.

    Returns ``None`` when ``field_key`` does not mirror a built-in input on
    ``step``; otherwise the proposal's saved value as a string (empty string
    when nothing has been saved yet).
    """
    attr = native_post_name(step, field_key)
    if attr is None or proposal is None:
        return None
    value = getattr(proposal, attr, None)
    if value is None:
        return ""
    return str(value).strip()


def normalise_dependency_value(value):
    """Normalise a parent field value for dependency comparisons.

    Mirrors the client-side check in ``_dynamic_fields.html`` while smoothing
    over representation differences: checkboxes submit ``on`` in the browser
    but are persisted as ``Yes``. Comparison is case-insensitive.
    """
    if value is None:
        return ""
    text = str(value).strip().lower()
    if text in {"on", "yes", "true", "1"}:
        return "yes"
    return text


def dependency_is_satisfied(field, parent_value):
    """Return True when a dynamic field should be considered *visible*.

    Mirrors the client-side show/hide logic:
    * No ``depends_on_key`` configured -> always visible.
    * Parent field cannot be located -> the browser leaves the field visible,
      so the server must keep requiring it.
    * Otherwise visible only when the parent's current value matches one of
      the comma-separated ``depends_on_value`` entries.
    """
    key = (getattr(field, "depends_on_key", "") or "").strip()
    if not key:
        return True
    if parent_value is DEPENDENCY_PARENT_NOT_FOUND:
        return True
    expected = [
        normalise_dependency_value(part)
        for part in (field.depends_on_value or "").split(",")
    ]
    actual = normalise_dependency_value(parent_value)
    return actual in expected


def dependency_parent_value(proposal, key, post_values=None, saved_values=None):
    """Resolve the current value of a dependency's parent field."""
    key = (key or "").strip()
    if not key:
        return DEPENDENCY_PARENT_NOT_FOUND

    # Native wizard inputs submit under their own field name and take
    # precedence, matching the client-side lookup order (``[name=...]`` is
    # checked before ``[data-field-key=...]``).
    if post_values is not None and key in post_values:
        return post_values[key]
    if saved_values is not None and key in saved_values:
        return saved_values[key]

    # Native wizard values that live on the Proposal model itself (e.g.
    # extension_type) are readable even when the parent step is not the
    # current one.
    if proposal is not None:
        attr = getattr(proposal, key, None)
        if isinstance(attr, (str, int, float, bool)):
            return attr
    return DEPENDENCY_PARENT_NOT_FOUND


def dynamic_parent_values_from_post(forms, request):
    """Map of dynamic field key -> submitted value for this request."""
    values = {}
    for form in forms:
        for field in form.fields.all():
            input_name = f"dynamic_field_{field.id}"
            if input_name in request.POST:
                values[field.field_key] = request.POST.get(input_name, "")
    return values


def dynamic_parent_values_from_saved(proposal):
    """Map of dynamic field key -> saved value across a proposal's responses."""
    values = {}
    responses = DynamicFormResponse.objects.filter(
        proposal=proposal
    ).prefetch_related("answers__field")
    for response in responses:
        for answer in response.answers.all():
            field = answer.field
            if field is not None and field.field_key:
                values.setdefault(field.field_key, (answer.value or "").strip())
    return values


def dynamic_field_blocks_submission(form, field, parent_value):
    """True when a required dynamic field is visible and therefore blocking.

    Required fields hidden behind an unmet ``depends_on`` condition must not
    block submission — the user never saw them.
    """
    return (
        form.blocks_proposal_submission
        and field.required
        and dependency_is_satisfied(field, parent_value)
    )
