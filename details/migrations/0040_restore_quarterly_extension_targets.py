from django.db import migrations, models


def restore_default_target_copy(apps, schema_editor):
    """Retitle only the untouched seeded copy; preserve administrators' edits."""

    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Annual targets with actual accomplishments by quarter.",
    ).update(subheading="Planned versus actual, by campus.")


def update_default_target_copy(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Planned versus actual, by campus.",
    ).update(subheading="Annual targets with actual accomplishments by quarter.")


def redistribute_annual_targets(apps, schema_editor):
    """Spread each annual target back across the four planned quarters.

    ``0039`` collapsed the quarterly planned figures into one annual number,
    so the original per-quarter split is gone.  Divide the annual target
    evenly across Q1–Q4 and give any remainder to Q4, which keeps the yearly
    planned total identical to what administrators had set.
    """

    Target = apps.get_model("details", "Target")
    for row in Target.objects.all().iterator():
        annual = row.planned_total
        base, remainder = divmod(annual, 4)
        row.planned_q1 = base
        row.planned_q2 = base
        row.planned_q3 = base
        row.planned_q4 = base + remainder
        row.save(update_fields=["planned_q1", "planned_q2", "planned_q3", "planned_q4"])


def consolidate_quarterly_plans(apps, schema_editor):
    """Turn the four planned values back into one annual target."""

    Target = apps.get_model("details", "Target")
    for row in Target.objects.all().iterator():
        row.planned_total = sum(
            getattr(row, f"planned_q{quarter}") for quarter in range(1, 5)
        )
        row.save(update_fields=["planned_total"])


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0039_simplify_extension_targets"),
    ]

    operations = [
        migrations.RunPython(
            restore_default_target_copy,
            update_default_target_copy,
        ),
        migrations.AddField(
            model_name="target",
            name="planned_q1",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="target",
            name="planned_q2",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="target",
            name="planned_q3",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="target",
            name="planned_q4",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RenameField(
            model_name="target",
            old_name="target",
            new_name="planned_total",
        ),
        migrations.RunPython(
            redistribute_annual_targets,
            consolidate_quarterly_plans,
        ),
        migrations.AlterField(
            model_name="target",
            name="planned_total",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]
