# The Services hero moved from a left-aligned two-column layout to the centred
# banner used by Home, Reports, and Achievements. The seeded heading was a long
# sentence written for the old layout, so shorten it to match the other pages.
#
# Only applied when the row still holds the original seeded text, so any admin
# edit made in the meantime is preserved.

from django.db import migrations


OLD_HEADING = "Proposal processing, review, approval, and implementation in one guided flow."
NEW_HEADING = "Extension Services"

OLD_SUBHEADING = (
    "The services page follows the maintained process records and the Proposal model "
    "lifecycle: a guided proposal wizard, review rounds, post-approval document release, "
    "optional MOA routing, and implementation reporting."
)
NEW_SUBHEADING = (
    "Proposal processing, review, approval, and implementation in one guided flow."
)


def forwards(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    page = SitePage.objects.filter(slug="services").first()
    if not page:
        return

    changed = False
    if page.hero_heading == OLD_HEADING:
        page.hero_heading = NEW_HEADING
        changed = True
    if page.hero_subheading == OLD_SUBHEADING:
        page.hero_subheading = NEW_SUBHEADING
        changed = True
    if changed:
        page.save(update_fields=["hero_heading", "hero_subheading"])


def backwards(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    page = SitePage.objects.filter(slug="services").first()
    if not page:
        return

    changed = False
    if page.hero_heading == NEW_HEADING:
        page.hero_heading = OLD_HEADING
        changed = True
    if page.hero_subheading == NEW_SUBHEADING:
        page.hero_subheading = OLD_SUBHEADING
        changed = True
    if changed:
        page.save(update_fields=["hero_heading", "hero_subheading"])


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0011_workflow_phase"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
