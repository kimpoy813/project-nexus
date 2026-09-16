"""Recolor existing HomeThrust cards from green/lime accents to the new
golden-yellow palette so previously installed sites match the redesign."""

from django.db import migrations

RECOLOR_MAP = {
    "text-green-600": "text-yellow-600",
    "text-lime-600": "text-yellow-700",
}


def recolor(apps, schema_editor):
    HomeThrust = apps.get_model("details", "HomeThrust")
    for old, new in RECOLOR_MAP.items():
        HomeThrust.objects.filter(color_class=old).update(color_class=new)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0015_alter_homethrust_color_class"),
    ]

    operations = [
        migrations.RunPython(recolor, noop),
    ]
