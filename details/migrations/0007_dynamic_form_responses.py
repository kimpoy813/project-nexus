# Generated for dynamic form proposal responses on 2026-07-25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0006_builder_models"),
        ("proposals", "0043_alter_proposal_implementation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="dynamicformtemplate",
            name="proposal_wizard_step",
            field=models.PositiveSmallIntegerField(blank=True, help_text="Optional: show this form inside proposal wizard step 1-19 when Applies To is Proposal.", null=True),
        ),
        migrations.AddField(
            model_name="dynamicformtemplate",
            name="blocks_proposal_submission",
            field=models.BooleanField(default=True, help_text="If enabled, required fields in this form must be completed before proposal submission."),
        ),
        migrations.CreateModel(
            name="DynamicFormResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("form", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="responses", to="details.dynamicformtemplate")),
                ("proposal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="dynamic_form_responses", to="proposals.proposal")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dynamic_form_responses", to="auth.user")),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="DynamicFormAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.TextField(blank=True, default="")),
                ("file", models.FileField(blank=True, null=True, upload_to="dynamic_form_answers/")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="details.dynamicformfield")),
                ("response", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="details.dynamicformresponse")),
            ],
            options={
                "ordering": ["field__order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="dynamicformresponse",
            constraint=models.UniqueConstraint(condition=models.Q(("proposal__isnull", False)), fields=("form", "proposal"), name="unique_dynamic_form_response_per_proposal"),
        ),
        migrations.AddConstraint(
            model_name="dynamicformanswer",
            constraint=models.UniqueConstraint(fields=("response", "field"), name="unique_answer_per_dynamic_field"),
        ),
    ]
