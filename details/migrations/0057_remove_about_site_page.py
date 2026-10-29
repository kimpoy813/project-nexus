"""Remove the About ``SitePage`` while About and Help are retired for now."""

from django.db import migrations, models


def _remove_about_page(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    SitePage.objects.filter(slug="about").delete()


def _restore_about_page(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    SitePage.objects.get_or_create(
        slug="about",
        defaults={"title": "About", "is_published": True},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0056_simplify_about_page_copy"),
    ]

    operations = [
        migrations.RunPython(_remove_about_page, _restore_about_page),
        migrations.AlterField(
            model_name="sitepage",
            name="slug",
            field=models.SlugField(
                choices=[
                    ("home", "Home"),
                    ("services", "Services"),
                    ("programs", "Programs"),
                    ("gallery", "Gallery"),
                ],
                max_length=40,
                unique=True,
            ),
        ),
    ]
