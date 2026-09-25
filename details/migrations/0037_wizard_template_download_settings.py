"""Give admins control over the template-download section on proposal steps."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0036_remove_office_forms_block"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="template_download_heading",
            field=models.CharField(
                blank=True,
                default="Proposal Templates",
                help_text="Heading above downloadable office templates on this step.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="template_download_instructions",
            field=models.TextField(
                blank=True,
                default="Download the editable workbook, complete it, and upload the finished .xlsx file below.",
                help_text="Instructions shown beside the template download buttons.",
            ),
        ),
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="work_plan_download_label",
            field=models.CharField(
                blank=True,
                default="Download Work Plan Template",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="gantt_chart_download_label",
            field=models.CharField(
                blank=True,
                default="Download Gantt Chart Template",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="funding_download_label",
            field=models.CharField(
                blank=True,
                default="Download Line-Item Budget Template",
                max_length=120,
            ),
        ),
    ]
