"""
Per-step form layout (built-in vs admin-built) and proposal-field mapping.

* ``ProposalWizardStepConfig.layout`` records whether a wizard step shows its
  classic system form (``BUILTIN``) or only the admin-built fields
  (``DYNAMIC``). Steps past the built-in 19 never had a system form, so any
  that already exist are moved to ``DYNAMIC``.
* ``DynamicFormField.maps_to_proposal`` lets a plain field on a custom step
  save its answer into a real Proposal column. The seeded default fields
  mirror those columns already (``extension_type``, ``title``, ...), so their
  ``field_key`` is copied into the new column to make the mapping explicit.
"""

from django.db import migrations, models


#: Columns the seeded default step fields were always mirroring. Keys are the
#: seeded ``field_key`` values (which deliberately match the column names).
MIRRORED_PROPOSAL_COLUMNS = {
    "title",
    "extension_type",
    "scope_type",
    "research_title",
    "implementing_agency",
    "beneficiaries_count",
    "beneficiaries_who",
    "budgetary_requirement",
    "extension_venue",
    "estimated_month",
    "estimated_year",
    "rationale_background",
    "significance",
    "general_objective",
}

#: The last step number that ships with a built-in system form.
LAST_BUILTIN_STEP_NO = 19


def set_layout_and_mappings(apps, schema_editor):
    ProposalWizardStepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    DynamicFormTemplate = apps.get_model("details", "DynamicFormTemplate")
    DynamicFormField = apps.get_model("details", "DynamicFormField")

    # Steps the system never had a built-in form for are admin-built by
    # definition: they already render through the dynamic step template.
    ProposalWizardStepConfig.objects.filter(step_no__gt=LAST_BUILTIN_STEP_NO).update(
        layout="DYNAMIC"
    )

    proposal_forms = DynamicFormTemplate.objects.filter(
        applies_to="PROPOSAL",
        is_repeater=False,
    ).values_list("id", flat=True)

    DynamicFormField.objects.filter(
        form__in=proposal_forms,
        maps_to_proposal="",
        field_key__in=MIRRORED_PROPOSAL_COLUMNS,
    ).update(maps_to_proposal=models.F("field_key"))


def reverse_layout_and_mappings(apps, schema_editor):
    # The column default (BUILTIN) and blank mappings are the pre-migration
    # state; nothing to restore beyond what removing the fields undoes.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0018_seed_proponent_repeater_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="layout",
            field=models.CharField(
                choices=[
                    ("BUILTIN", "Built-in system form"),
                    ("DYNAMIC", "Custom form (admin-managed fields)"),
                ],
                default="BUILTIN",
                help_text=(
                    "Built-in system form: the step keeps its classic form and "
                    "the fields below are extra questions. Custom form: the "
                    "fields below are the whole step."
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="dynamicformfield",
            name="maps_to_proposal",
            field=models.CharField(
                blank=True,
                choices=[
                    ("title", "Title of the Program / Project / Activity"),
                    ("extension_type", "Extension type"),
                    ("scope_type", "Scope (program / project / activity)"),
                    ("research_title", "Research title"),
                    ("implementing_agency", "Implementing agency / unit"),
                    ("beneficiaries_count", "Number of beneficiaries"),
                    ("beneficiaries_who", "Who the beneficiaries are"),
                    ("budgetary_requirement", "Budgetary requirement"),
                    ("extension_venue", "Extension venue / site"),
                    ("estimated_month", "Estimated month"),
                    ("estimated_year", "Estimated year"),
                    ("rationale_background", "Rationale / background"),
                    ("significance", "Significance"),
                    ("general_objective", "General objective"),
                ],
                default="",
                help_text=(
                    "For normal (non-repeatable) fields on a proposal wizard "
                    "step: also save the answer into this proposal field, so "
                    "generated documents and reports keep working when a step "
                    "is rebuilt as a custom form."
                ),
                max_length=40,
            ),
        ),
        migrations.RunPython(set_layout_and_mappings, reverse_layout_and_mappings),
    ]
