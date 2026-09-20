"""Remove the free-text ``Other`` gender issue option.

Gender Issues / Mandates is a predefined multi-select checklist.  Existing
``Other`` links are no longer valid, so remove them before dropping the field
that stored their user-entered description.
"""

from django.db import migrations


def remove_other_links(apps, schema_editor):
    ProposalGenderIssue = apps.get_model("proposals", "ProposalGenderIssue")
    ProposalGenderIssue.objects.filter(issue_key="others").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0051_remove_sdg_agenda_explanations"),
    ]

    operations = [
        migrations.RunPython(remove_other_links, migrations.RunPython.noop),
        migrations.RemoveField(model_name="proposalgenderissue", name="other_text"),
    ]
