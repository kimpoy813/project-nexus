"""Re-split the published phase weights to Proposal 50 / MOA 20 / Implementation 30.

The Services page now draws each phase's share as a progress ring, and those
same weights drive ``Proposal.overall_progress``, so the seeded captions move
with them. Rows an administrator has already customised are left untouched -
the same rule ``0015_simplify_services_hero_copy`` uses.
"""

from django.db import migrations, models


# key -> ((old weight, old caption), (new weight, new caption))
PHASES = {
    "proposal": (
        (40, "40% of overall progress when MOA is required"),
        (50, "50% of overall progress when MOA is required"),
    ),
    "moa": (
        (20, "20% of overall progress when required"),
        (20, "20% of overall progress when an MOA is required"),
    ),
    "implementation": (
        (40, "40% of overall progress when MOA is required"),
        (30, "30% of overall progress when MOA is required"),
    ),
}


def _restate(apps, pick_from, pick_to):
    WorkflowPhase = apps.get_model("details", "WorkflowPhase")

    for key, states in PHASES.items():
        from_weight, from_label = states[pick_from]
        to_weight, to_label = states[pick_to]
        WorkflowPhase.objects.filter(
            key=key,
            weight_percent=from_weight,
            weight_label=from_label,
        ).update(weight_percent=to_weight, weight_label=to_label)


def forwards(apps, schema_editor):
    _restate(apps, pick_from=0, pick_to=1)


def backwards(apps, schema_editor):
    _restate(apps, pick_from=1, pick_to=0)


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0015_simplify_services_hero_copy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflowphase",
            name="weight_percent",
            field=models.PositiveSmallIntegerField(
                default=50,
                help_text=(
                    "Share of overall progress, 0-100. Drives the progress ring on the "
                    "Services page and the overall progress calculation."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="workflowphase",
            name="weight_label",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Caption beside the ring, e.g. "50% of overall progress when MOA is required".',
                max_length=120,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
