"""
Undo the schema that the admin-configurable wizard (PR #30) introduced.

PR #30 was merged and then reverted, restoring the code to the state of PR #28
("Step 3 proponents: admin-defined repeatable group"). Its two migrations,
``0019_moawizardstepconfig_and_more`` and ``0020_backfill_wizard_step_parts``,
are kept in this tree as frozen history because production databases may
already have run them: ``build.sh`` applies migrations on every deploy.

Reverting only the code would leave those databases with two NOT NULL columns
(``order``, ``section_key``) on ``details_proposalwizardstepconfig`` that the
restored ``ProposalWizardStepConfig`` model does not know about. Django drops
the database default after adding a column, so the next INSERT from the
restored code -- the wizard seeding its missing steps, or an admin adding a
step -- would fail with an integrity error.

This migration rolls the schema forward to match the restored models instead:

* drops the two ``DynamicFormTemplate`` many-to-many attachments,
* drops ``order`` and ``section_key`` from ``ProposalWizardStepConfig`` and
  puts its ordering back to ``step_no``,
* deletes the ``MOAWizardStepConfig`` table.

On a database that never ran 0019/0020 the three migrations apply in sequence
and cancel out, so a fresh install ends at the same schema as PR #28.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0020_backfill_wizard_step_parts"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="dynamicformtemplate",
            name="attached_moa_steps",
        ),
        migrations.AlterModelOptions(
            name="proposalwizardstepconfig",
            options={"ordering": ["step_no"]},
        ),
        migrations.RemoveField(
            model_name="dynamicformtemplate",
            name="attached_proposal_steps",
        ),
        migrations.RemoveField(
            model_name="proposalwizardstepconfig",
            name="order",
        ),
        migrations.RemoveField(
            model_name="proposalwizardstepconfig",
            name="section_key",
        ),
        migrations.DeleteModel(
            name="MOAWizardStepConfig",
        ),
    ]
