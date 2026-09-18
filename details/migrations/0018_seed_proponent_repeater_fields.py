"""
Give Step 3 (Proponents) its default repeatable group.

Step 3 used to be hardcoded: Name, Position / Designation, Specialization,
Role, CP Number and Email were printed by the template and saved onto
``ProposalProponent``. They are now an admin-owned repeatable group, so every
existing installation needs the equivalent fields or the step would come up
empty.

Two safety rules, mirroring ``details.proponent_fields``:

* fields are only created when the step's form has none - an admin's own
  layout is never touched;
* the form is only touched when step 3 is still the proponents step (step
  numbers are editable, and a renumbered wizard must not get a proponent form
  grafted onto whatever is third).
"""

from django.db import migrations


def seed(apps, schema_editor):
    DynamicFormField = apps.get_model("details", "DynamicFormField")
    DynamicFormTemplate = apps.get_model("details", "DynamicFormTemplate")
    ProposalWizardStepConfig = apps.get_model("details", "ProposalWizardStepConfig")

    config = ProposalWizardStepConfig.objects.filter(step_no=3).first()
    if config is not None and "proponent" not in (config.title or "").lower():
        return

    form = (
        DynamicFormTemplate.objects.filter(
            applies_to="PROPOSAL",
            proposal_wizard_step=3,
        )
        .order_by("id")
        .first()
    )
    if form is None:
        return

    if DynamicFormField.objects.filter(form=form).exists():
        # The office already built something for this step: only fill in the
        # mapping for fields whose key makes the intent obvious.
        for field in DynamicFormField.objects.filter(form=form):
            if field.maps_to:
                continue
            if field.field_key in {"full_name", "name", "proponent_name"}:
                field.maps_to = "full_name"
            elif field.field_key in {"designation", "position"}:
                field.maps_to = "designation"
            elif field.field_key == "email":
                field.maps_to = "email"
            else:
                continue
            field.save(update_fields=["maps_to"])
        return

    form.is_repeater = True
    form.row_store = "PROPONENT"
    form.repeater_label = form.repeater_label or "Proponent"
    form.save(update_fields=["is_repeater", "row_store", "repeater_label"])

    defaults = [
        {
            "label": "Name",
            "field_key": "full_name",
            "field_type": "TEXT",
            "required": True,
            "placeholder": "Full name",
            "maps_to": "full_name",
        },
        {
            "label": "Position / Designation",
            "field_key": "designation",
            "field_type": "TEXT",
            "placeholder": "e.g. Assistant Professor IV",
            "maps_to": "designation",
        },
        {
            "label": "Specialization",
            "field_key": "specialization",
            "field_type": "TEXT",
            "placeholder": "e.g. Crop Science",
            "maps_to": "specialization",
        },
        {
            "label": "Role",
            "field_key": "role",
            "field_type": "SELECT",
            "choices_text": "Program Leader\nProject Leader\nProponent",
            "help_text": "Leave as is unless this person holds a specific role.",
            "maps_to": "role",
        },
        {
            "label": "CP Number",
            "field_key": "cp_number",
            "field_type": "TEXT",
            "placeholder": "09XX XXX XXXX",
            "maps_to": "cp_number",
        },
        {
            "label": "Email",
            "field_key": "email",
            "field_type": "EMAIL",
            "placeholder": "name@example.com",
            "maps_to": "email",
        },
    ]

    for order, spec in enumerate(defaults, start=1):
        DynamicFormField.objects.create(form=form, order=order, **spec)


def unseed(apps, schema_editor):
    """Drop the seeded fields again (their rows stay: they are proponent data)."""
    DynamicFormField = apps.get_model("details", "DynamicFormField")
    DynamicFormTemplate = apps.get_model("details", "DynamicFormTemplate")

    form = (
        DynamicFormTemplate.objects.filter(applies_to="PROPOSAL", proposal_wizard_step=3)
        .order_by("id")
        .first()
    )
    if form is None:
        return
    DynamicFormField.objects.filter(
        form=form,
        field_key__in=[
            "full_name",
            "designation",
            "specialization",
            "role",
            "cp_number",
            "email",
        ],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0017_dynamicformfield_maps_to_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
