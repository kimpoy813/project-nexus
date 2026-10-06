from django.db import migrations


def consolidate_quarterly_targets(apps, schema_editor):
    """Fold the four planned quarters into one annual target.

    ``planned_total`` was kept in sync with the quarterly figures on every
    save, so it already holds the yearly target — this pass just guarantees
    it before the quarterly columns are removed.
    """
    Target = apps.get_model("details", "Target")
    for row in Target.objects.all().iterator():
        row.planned_total = (
            row.planned_q1 + row.planned_q2 + row.planned_q3 + row.planned_q4
        )
        row.save(update_fields=["planned_total"])


def redistribute_annual_targets(apps, schema_editor):
    """Reverse: spread the annual target back across the four quarters.

    Divides the annual target evenly across Q1–Q4 and gives any remainder
    to Q4, which keeps the yearly planned total identical to what
    administrators had set.
    """
    Target = apps.get_model("details", "Target")
    for row in Target.objects.all().iterator():
        base, remainder = divmod(row.planned_total, 4)
        row.planned_q1 = base
        row.planned_q2 = base
        row.planned_q3 = base
        row.planned_q4 = base + remainder
        row.save(update_fields=["planned_q1", "planned_q2", "planned_q3", "planned_q4"])


def update_seeded_target_copy(apps, schema_editor):
    """Retitle only the untouched seeded copy; preserve administrators' edits."""
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Target versus actual, by campus.",
    ).update(subheading="Annual targets with actual accomplishments by quarter.")


def restore_seeded_target_copy(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Annual targets with actual accomplishments by quarter.",
    ).update(subheading="Target versus actual, by campus.")


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0041_target_wording_for_seed_sections"),
    ]

    operations = [
        migrations.RunPython(
            consolidate_quarterly_targets,
            redistribute_annual_targets,
        ),
        migrations.RunPython(
            update_seeded_target_copy,
            restore_seeded_target_copy,
        ),
        migrations.RenameField(
            model_name="target",
            old_name="planned_total",
            new_name="target",
        ),
        migrations.RemoveField(model_name="target", name="planned_q1"),
        migrations.RemoveField(model_name="target", name="planned_q2"),
        migrations.RemoveField(model_name="target", name="planned_q3"),
        migrations.RemoveField(model_name="target", name="planned_q4"),
    ]
