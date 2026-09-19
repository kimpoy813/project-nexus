"""
Retitle the checklist steps and the agenda step.

The updated office forms made SDGs Covered and the ISPSC Extension Agenda
pure checklists (no per-item explanations), and renamed the thrust step to
"ISPSC Extension Agenda". Applies the same renames to fresh and upgraded
databases so admin titles match what the step pages now render.
"""

from django.db import migrations


RENAMES = [
    # flow, step_no, new title, new description
    ("RESEARCH", 6, "SDGs Covered", "SDGs covered (check all that apply)"),
    (
        "RESEARCH",
        7,
        "ISPSC Extension Agenda",
        "Extension agenda covered + technology details (check all that apply)",
    ),
    (
        "TRAINING",
        6,
        "Sustainable Development Goals (SDG)",
        "SDGs covered (check all that apply)",
    ),
    (
        "TRAINING",
        7,
        "ISPSC Extension Agenda",
        "Extension agenda covered (check all that apply)",
    ),
]


def apply(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    for flow, step_no, title, description in RENAMES:
        StepConfig.objects.filter(flow=flow, step_no=step_no).update(
            title=title,
            description=description,
        )


def reverse(apps, schema_editor):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.filter(flow="RESEARCH", step_no=6).update(
        title="SDGs Covered / Extension Agenda",
        description="SDGs covered and how each relates",
    )
    StepConfig.objects.filter(flow="RESEARCH", step_no=7).update(
        title="ISPSC Extension Thrust",
        description="ISPSC extension thrust and how it relates",
    )
    StepConfig.objects.filter(flow="TRAINING", step_no=6).update(
        title="Sustainable Development Goals (SDG)",
        description="SDGs covered and how each relates",
    )
    StepConfig.objects.filter(flow="TRAINING", step_no=7).update(
        title="Extension Thrust",
        description="ISPSC extension thrust and how it relates",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0023_split_wizard_into_flows"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
