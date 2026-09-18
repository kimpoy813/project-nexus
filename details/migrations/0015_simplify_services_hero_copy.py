"""Keep the public Services hero focused on its primary action."""

from django.db import migrations


OLD_SUBHEADING = "Proposal processing, review, approval, and implementation in one guided flow."
NEW_SUBHEADING = "A simple path from proposal to implementation."


def forwards(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    SitePage.objects.filter(
        slug="services",
        hero_subheading=OLD_SUBHEADING,
    ).update(hero_subheading=NEW_SUBHEADING)


def backwards(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    SitePage.objects.filter(
        slug="services",
        hero_subheading=NEW_SUBHEADING,
    ).update(hero_subheading=OLD_SUBHEADING)


class Migration(migrations.Migration):
    dependencies = [
        ("details", "0014_dynamicformfield_depends_on_key_and_more"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
