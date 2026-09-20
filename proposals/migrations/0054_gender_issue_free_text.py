"""Gender Issues / Mandates becomes a free-text repeater.

The step no longer offers a predefined checklist: proponents type each gender
issue or mandate themselves and can add as many entries as they need, exactly
like the Methodology step.  ``issue_label`` therefore holds user-typed text, so
the canonical ``issue_key`` becomes optional - it is only filled when the typed
text matches one of the mandates the DOCX templates list as fixed rows.  Rows
are also ordered by id so the entries keep the order they were typed in.

Existing links are untouched: their keys and labels stay valid.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proposals', '0053_remove_gender_participant_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='proposalgenderissue',
            options={'ordering': ['id']},
        ),
        migrations.AlterField(
            model_name='proposalgenderissue',
            name='issue_key',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
