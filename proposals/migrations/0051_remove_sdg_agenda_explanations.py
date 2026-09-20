"""Remove the per-item explanation fields from the SDG and agenda checklists.

The wizard now records only which SDGs and Extension Agenda items apply to a
proposal.  The old fields were introduced for the previous free-text prompts;
removing them keeps the database model and generated documents aligned with
the checklist-only form.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0050_utility_model_fields"),
    ]

    operations = [
        migrations.RemoveField(model_name="proposalsdg", name="explanation"),
        migrations.RemoveField(model_name="proposalthrust", name="explanation"),
    ]
