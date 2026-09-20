"""Update the gender issues step description for the free-text repeater.

Step 10 no longer offers a predefined checklist: proponents type each gender
issue or mandate themselves, so the sidebar description should say so.
"""

from django.db import migrations


NEW_DESCRIPTION = "Type the GAD issues or mandates addressed"
OLD_DESCRIPTION = "Applicable GAD mandates"


def apply(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.filter(
        step_no=10,
        title="Gender Issues / Mandates Addressed",
    ).update(description=NEW_DESCRIPTION)


def reverse(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.filter(
        step_no=10,
        title="Gender Issues / Mandates Addressed",
    ).update(description=OLD_DESCRIPTION)


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0028_sex_disaggregation_step_description"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
