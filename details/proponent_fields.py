"""
The built-in shape of wizard Step 3 (Proponents).

Step 3 used to be hardcoded: the template always printed Name, Position /
Designation, Specialization, CP Number and Email for every proponent. The
admin now owns that layout through the repeatable-group builder, and this
module holds the *defaults* it starts from.

Two rules keep the step safe:

* The defaults are only seeded when the step's form has **no fields at all**.
  An admin who deletes a field, renames a label, or turns the repeatable group
  off is never overruled.
* Seeding only happens when step 3 is still the proponents step. Step numbers
  are admin-editable, so a renumbered wizard does not get a proponent form
  grafted onto whatever step now happens to be third.
"""

from django.db import transaction

from .models import DynamicFormField, DynamicFormTemplate, ProposalWizardStepConfig


#: The default step number of "Proponents" in the built-in 20-step wizard.
PROPONENT_STEP_NO = 3

#: Label used for one row of the repeatable group.
PROPONENT_ROW_LABEL = "Proponent"

#: Default repeatable-group fields, in the order they appear on the step.
#: ``maps_to`` values are ``DynamicFormField.MapsTo`` members.
DEFAULT_PROPONENT_FIELDS = [
    {
        "label": "Name",
        "field_key": "full_name",
        "field_type": DynamicFormField.FieldType.TEXT,
        "required": True,
        "placeholder": "Full name",
        "maps_to": DynamicFormField.MapsTo.FULL_NAME,
    },
    {
        "label": "Position / Designation",
        "field_key": "designation",
        "field_type": DynamicFormField.FieldType.TEXT,
        "placeholder": "e.g. Assistant Professor IV",
        "maps_to": DynamicFormField.MapsTo.DESIGNATION,
    },
    {
        "label": "Specialization",
        "field_key": "specialization",
        "field_type": DynamicFormField.FieldType.TEXT,
        "placeholder": "e.g. Crop Science",
        "maps_to": DynamicFormField.MapsTo.SPECIALIZATION,
    },
    {
        "label": "Role",
        "field_key": "role",
        "field_type": DynamicFormField.FieldType.SELECT,
        "choices_text": "Program Leader\nProject Leader\nProponent",
        "help_text": "Leave as is unless this person holds a specific role.",
        "maps_to": DynamicFormField.MapsTo.ROLE,
    },
    {
        "label": "CP Number",
        "field_key": "cp_number",
        "field_type": DynamicFormField.FieldType.TEXT,
        "placeholder": "09XX XXX XXXX",
        "maps_to": DynamicFormField.MapsTo.CP_NUMBER,
    },
    {
        "label": "Email",
        "field_key": "email",
        "field_type": DynamicFormField.FieldType.EMAIL,
        "placeholder": "name@example.com",
        "maps_to": DynamicFormField.MapsTo.EMAIL,
    },
]


def step_title(step_no):
    config = ProposalWizardStepConfig.objects.filter(step_no=step_no).first()
    return config.title if config else ""


def is_proponents_step(step_no=PROPONENT_STEP_NO):
    """True when ``step_no`` is (still) the Proponents step.

    On a fresh database the step configs are seeded lazily from
    ``INITIAL_STEP_LABELS``, so a missing row means "the built-in step 3",
    which is Proponents.
    """
    config = ProposalWizardStepConfig.objects.filter(step_no=step_no).first()
    if config is None:
        return step_no == PROPONENT_STEP_NO
    return "proponent" in (config.title or "").lower()


def seed_default_fields(form):
    """Create the default proponent fields on ``form`` (no-op when it has any)."""
    if form.fields.exists():
        return []

    created = []
    for order, spec in enumerate(DEFAULT_PROPONENT_FIELDS, start=1):
        created.append(
            DynamicFormField.objects.create(
                form=form,
                label=spec["label"],
                field_key=spec["field_key"],
                field_type=spec.get("field_type", DynamicFormField.FieldType.TEXT),
                required=spec.get("required", False),
                placeholder=spec.get("placeholder", ""),
                help_text=spec.get("help_text", ""),
                choices_text=spec.get("choices_text", ""),
                maps_to=spec.get("maps_to", ""),
                order=order,
            )
        )
    return created


@transaction.atomic
def ensure_proponent_repeater_form(step_no=PROPONENT_STEP_NO, *, create=True):
    """Return the step's repeatable proponent form, seeding defaults as needed.

    Returns ``None`` when ``step_no`` is not the proponents step (see
    ``is_proponents_step``) so a renumbered wizard is left untouched.
    """
    if not is_proponents_step(step_no):
        return None

    form = (
        DynamicFormTemplate.objects.filter(
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step_no,
        )
        .order_by("id")
        .first()
    )

    if form is None:
        if not create:
            return None
        title = step_title(step_no) or "Proponents"
        form = DynamicFormTemplate.objects.create(
            name=f"Fields for Step {step_no}: {title}",
            slug=_unique_slug(f"fields-for-step-{step_no}-{title}"),
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step_no,
            is_active=True,
            blocks_proposal_submission=True,
            is_repeater=True,
            repeater_label=PROPONENT_ROW_LABEL,
            row_store=DynamicFormTemplate.RowStore.PROPONENT,
        )

    # Nothing built yet: adopt the proponent shape so the step always shows the
    # fields the office expects, even before an admin opens the builder.
    if not form.fields.exists():
        form.is_repeater = True
        form.row_store = DynamicFormTemplate.RowStore.PROPONENT
        form.repeater_label = form.repeater_label or PROPONENT_ROW_LABEL
        form.save(update_fields=["is_repeater", "row_store", "repeater_label", "updated_at"])
        seed_default_fields(form)

    return form


def _unique_slug(base):
    from django.utils.text import slugify

    slug = slugify(base)[:200] or "proponent-fields"
    candidate = slug
    suffix = 2
    while DynamicFormTemplate.objects.filter(slug=candidate).exists():
        candidate = f"{slug[:190]}-{suffix}"
        suffix += 1
    return candidate
