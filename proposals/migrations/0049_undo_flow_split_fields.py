"""
Drop the ``Proposal`` fields the two-flow wizard (PR #32/#33) collected.

PR #32 ("Split the proposal wizard into the two office forms") and PR #33
("Split Utility Model into its own proposal wizard step") were both reverted,
so ``proposals/models.py`` is back at PR #28 and no longer declares these
six fields:

* ``duration`` and ``funding_source`` - Training Design flow sections,
* ``monitoring_eval_file`` - the Monitoring and Evaluation Mechanics upload,
* ``technology_title``, ``utility_model_registration_number`` and
  ``utility_model_description`` - the technology/utility-model answers.

``0047`` and ``0048`` stay in this tree as frozen history because production
databases may already have run them (``build.sh`` applies migrations on every
deploy) - the same reason ``details/0021`` kept the reverted PR #30's
migrations. Five of the six columns are NOT NULL with the database default
dropped again after the ADD COLUMN, so leaving them behind would make every
INSERT from the restored code - a proponent starting a draft, an admin
creating a legacy proposal - fail with an integrity error.

Any answers already saved in these columns, and any uploaded M&E file, go
with them; the restored wizard has no step that collects or renders them.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0048_proposal_technology_title_and_more"),
    ]

    operations = [
        migrations.RemoveField(model_name="proposal", name="duration"),
        migrations.RemoveField(model_name="proposal", name="funding_source"),
        migrations.RemoveField(model_name="proposal", name="monitoring_eval_file"),
        migrations.RemoveField(model_name="proposal", name="technology_title"),
        migrations.RemoveField(
            model_name="proposal", name="utility_model_registration_number"
        ),
        migrations.RemoveField(model_name="proposal", name="utility_model_description"),
    ]
