"""Recolor existing SiteConfiguration rows from the old forest-green brand
colour to the new golden-yellow brand colour.

New rows already default to the gold value (see 0015 and the model); this
migration brings rows created before the redesign in line so the whole
system renders the yellow palette.
"""

from django.db import migrations

OLD_PRIMARY = "#103b07"
NEW_PRIMARY = "#a16207"


def recolor(apps, schema_editor):
    SiteConfiguration = apps.get_model("accounts", "SiteConfiguration")
    SiteConfiguration.objects.filter(primary_color=OLD_PRIMARY).update(
        primary_color=NEW_PRIMARY
    )


def noop(apps, schema_editor):
    # Deliberately not reversed: recolouring back would resurrect a brand
    # colour the system no longer ships.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_populate_campuses_colleges_departments"),
    ]

    operations = [
        migrations.RunPython(recolor, noop),
    ]
