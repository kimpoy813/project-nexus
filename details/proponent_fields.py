"""
The built-in shape of the Proponents section of the proposal wizard.

The proponent roster used to be hardcoded: the template always printed Name,
Position / Designation, Specialization, CP Number and Email for every
proponent. The admin now owns that layout through the repeatable-group
builder, and this module holds the *defaults* it starts from.

Two rules keep the step safe:

* The defaults are only seeded when the step's form has **no fields at all**.
  An admin who deletes a field, renames a label, or turns the repeatable group
  off is never overruled.
* Seeding only happens on the step that carries the Proponents *section*
  (``ProposalWizardStepConfig.section_key``). The admin can move that section
  to any step number, and a step that no longer carries it is left alone.
"""

from django.db import transaction

from .models import DynamicFormField, DynamicFormTemplate, ProposalWizardStepConfig
from .wizard_defaults import PROPONENTS_SECTION_KEY, default_section_for_step


#: The default step number of "Proponents" in the built-in 19-step wizard.
#: Kept for callers that predate movable sections; prefer
#: ``proponents_step_no()``.
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
    """True when ``step_no`` currently carries the Proponents section.

    On a fresh database the step configs are seeded lazily from the built-in
    layout, so a missing row on an empty table means the default section for
    that number. Once rows exist a missing row is a removed step.
    """
    config = ProposalWizardStepConfig.objects.filter(step_no=step_no).only("section_key").first()
    if config is None:
        if ProposalWizardStepConfig.objects.exists():
            return False
        return default_section_for_step(step_no) == PROPONENTS_SECTION_KEY
    return (config.section_key or "") == PROPONENTS_SECTION_KEY


def proponents_step_no():
    """The step number the Proponents section sits on, or ``None``."""
    config = (
        ProposalWizardStepConfig.objects.filter(section_key=PROPONENTS_SECTION_KEY)
        .order_by("step_no")
        .only("step_no")
        .first()
    )
    if config is not None:
        return config.step_no
    if not ProposalWizardStepConfig.objects.exists():
        return PROPONENT_STEP_NO
    return None


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
def ensure_proponent_repeater_form(step_no=None, *, create=True):
    """Return the step's repeatable proponent form, seeding defaults as needed.

    ``step_no`` defaults to wherever the Proponents section currently sits.
    Returns ``None`` when ``step_no`` does not carry that section (see
    ``is_proponents_step``) so a rearranged wizard is left untouched.
    """
    if step_no is None:
        step_no = proponents_step_no()
    if step_no is None or not is_proponents_step(step_no):
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
