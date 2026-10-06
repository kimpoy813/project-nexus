from django.db import migrations


def rename_planned_wording(apps, schema_editor):
    """Align seeded Extension Targets copy with the "Target" terminology.

    The reports page was seeded (migration 0035) with the subheading
    "Planned versus actual, by campus." The feature now says "target"
    everywhere in the UI, so existing installs get their seeded copy
    updated to match. Only that exact seeded string is touched — anything
    an administrator typed themselves is left alone.
    """
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Planned versus actual, by campus.",
    ).update(subheading="Target versus actual, by campus.")


def restore_planned_wording(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(
        layout="TARGETS",
        subheading="Target versus actual, by campus.",
    ).update(subheading="Planned versus actual, by campus.")


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0040_restore_quarterly_extension_targets"),
    ]

    operations = [
        migrations.RunPython(rename_planned_wording, restore_planned_wording),
    ]
