from django.db import migrations, models


def update_default_target_copy(apps, schema_editor):
    """Retitle only the untouched seeded copy; preserve administrators' edits."""

    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Planned versus actual, by campus.",
    ).update(subheading="Annual targets with actual accomplishments by quarter.")


def restore_default_target_copy(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Annual targets with actual accomplishments by quarter.",
    ).update(subheading="Planned versus actual, by campus.")


def consolidate_quarterly_targets(apps, schema_editor):
    """Turn the four old planned values into one annual target.

    The public/admin forms historically wrote planned figures by quarter while
    ``planned_total`` was only a cached value.  Prefer the quarterly sum when
    it exists, then make both annual totals consistent with their source data
    before the obsolete planned-quarter columns are removed.
    """

    Target = apps.get_model("details", "Target")
    for row in Target.objects.all().iterator():
        planned_sum = sum(
            getattr(row, f"planned_q{quarter}") for quarter in range(1, 5)
        )
        actual_sum = sum(
            getattr(row, f"actual_q{quarter}") for quarter in range(1, 5)
        )
        if planned_sum:
            row.planned_total = planned_sum
        row.actual_total = actual_sum
        row.save(update_fields=["planned_total", "actual_total"])


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0038_alter_processstep_options"),
    ]

    operations = [
        migrations.RunPython(
            update_default_target_copy,
            restore_default_target_copy,
        ),
        migrations.RunPython(
            consolidate_quarterly_targets,
            migrations.RunPython.noop,
        ),
        migrations.RenameField(
            model_name="target",
            old_name="planned_total",
            new_name="target",
        ),
        migrations.RemoveField(
            model_name="target",
            name="planned_q1",
        ),
        migrations.RemoveField(
            model_name="target",
            name="planned_q2",
        ),
        migrations.RemoveField(
            model_name="target",
            name="planned_q3",
        ),
        migrations.RemoveField(
            model_name="target",
            name="planned_q4",
        ),
        migrations.AlterField(
            model_name="target",
            name="target",
            field=models.PositiveIntegerField(default=0, verbose_name="annual target"),
        ),
        migrations.AlterField(
            model_name="target",
            name="actual_total",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]
