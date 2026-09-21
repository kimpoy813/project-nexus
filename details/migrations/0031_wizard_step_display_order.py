"""Add a display order so the admin can drag-reorder wizard steps.

``step_no`` stays the step's identity (URLs, native templates, attached
forms). Existing rows keep their current sequence by copying ``step_no``.
"""

from django.db import migrations, models


def copy_step_no_into_display_order(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    for row in StepConfig.objects.all():
        if not row.display_order:
            row.display_order = row.step_no
            row.save(update_fields=["display_order"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0030_replace_extension_agenda"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="proposalwizardstepconfig",
            options={"ordering": ["display_order", "step_no"]},
        ),
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="display_order",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Position in the proposal wizard. Lower numbers appear first.",
            ),
        ),
        migrations.RunPython(copy_step_no_into_display_order, noop_reverse),
    ]
