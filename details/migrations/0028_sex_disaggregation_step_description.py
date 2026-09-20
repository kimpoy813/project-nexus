"""Update the participant step description for sex disaggregation."""

from django.db import migrations


NEW_DESCRIPTION = "Sex-disaggregated participant counts"


def apply(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.filter(
        step_no=9,
        title="Participants / Proposed Clients",
    ).update(description=NEW_DESCRIPTION)


def reverse(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.filter(
        step_no=9,
        title="Participants / Proposed Clients",
    ).update(description="Participant profiling and counts")


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0027_utility_model_step"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
