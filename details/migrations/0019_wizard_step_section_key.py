"""
Decouple wizard behaviour from step numbers.

Each ``ProposalWizardStepConfig`` now records the built-in *section* it
renders (``section_key``). Existing rows are stamped with the section their
step number shipped with in the original 19-step wizard, so an installation
that has already been renamed, hidden, or extended by the admin keeps working
exactly as before - a step 3 still titled "Proponents" keeps the proponent
roster, and a step the admin added (say step 20) is left as a fields-only
step.

The one heuristic: a built-in position that the admin has re-titled so that
it no longer resembles its original section is still assumed to be that
section, because before this migration that is what it rendered.
"""

from django.db import migrations, models


DEFAULTS = {
    1: "extension_type",
    2: "title",
    3: "proponents",
    4: "implementing_agency",
    5: "beneficiaries",
    6: "sdg_thrust",
    7: "budget",
    8: "participants",
    9: "gender_issues",
    10: "schedule_venue",
    11: "rationale",
    12: "significance",
    13: "objectives",
    14: "methodology",
    15: "outputs",
    16: "activities",
    17: "funding",
    18: "research_abstract",
    19: "certificate",
}


def stamp_sections(apps, schema_editor):
    ProposalWizardStepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    for config in ProposalWizardStepConfig.objects.all():
        section = DEFAULTS.get(config.step_no, "")
        if section and not config.section_key:
            config.section_key = section
            config.save(update_fields=["section_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0018_seed_proponent_repeater_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="section_key",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Built-in part of the proposal form shown on this step. "
                    "Leave blank for a step made only of admin-built fields."
                ),
                max_length=60,
            ),
        ),
        migrations.RunPython(stamp_sections, migrations.RunPython.noop),
    ]
