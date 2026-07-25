# Generated for implementation phase process labels on 2026-07-25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0042_moanotification"),
    ]

    operations = [
        migrations.AlterField(
            model_name="proposal",
            name="implementation_status",
            field=models.CharField(
                choices=[
                    ("NOT_STARTED", "Not Started"),
                    ("PREPARATION", "Preparation"),
                    ("IMPLEMENTATION", "Implementation of Extension Activity"),
                    ("POST_ACTIVITY_REPORT", "Post-Extension Activity Report Submission"),
                    ("TERMINAL_REPORT", "Extension Progress Report"),
                    ("MONITORING", "Monitoring and Evaluation"),
                    ("REVISION", "Summary of Comments and Actions Taken"),
                    ("COMPLETED", "Final Evaluation and Documentation"),
                ],
                default="NOT_STARTED",
                max_length=30,
            ),
        ),
    ]
