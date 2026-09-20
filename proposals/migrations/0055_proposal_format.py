from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proposals", "0054_gender_issue_free_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposal",
            name="proposal_format",
            field=models.CharField(
                blank=True,
                choices=[
                    ("EXTENSION_PROPOSAL", "Extension Proposal"),
                    ("TRAINING_DESIGN", "Training Design"),
                ],
                default="",
                help_text=(
                    "Community-based extensions must use Training Design. Request-based "
                    "extensions may use Training Design or the Extension Proposal format."
                ),
                max_length=30,
            ),
        ),
    ]
