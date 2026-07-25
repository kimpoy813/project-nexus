# Generated for wizard step manager and role capabilities on 2026-07-25

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0007_dynamic_form_responses"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProposalWizardStepConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step_no", models.PositiveSmallIntegerField(unique=True)),
                ("title", models.CharField(max_length=160)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("instructions", models.TextField(blank=True, default="")),
                ("is_visible", models.BooleanField(default=True)),
                ("is_required", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["step_no"]},
        ),
        migrations.CreateModel(
            name="RoleCapability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("FACULTY", "Faculty"), ("STAFF", "Staff"), ("EVALUATOR", "Evaluator"), ("DEPARTMENT_COORDINATOR", "Department Coordinator"), ("CAMPUS_COORDINATOR", "Campus Coordinator"), ("DIRECTOR", "Director"), ("ADMIN", "Admin")], max_length=50)),
                ("capability", models.CharField(choices=[("CREATE_PROPOSAL", "Create proposals"), ("REVIEW_PROPOSAL", "Review/comment on proposals"), ("MANAGE_MOA", "Manage MOA workflow"), ("MANAGE_IMPLEMENTATION", "Manage implementation workflow"), ("SUBMIT_QUARTERLY_ACCOMPLISHMENT", "Submit quarterly accomplishment reports"), ("VIEW_ANALYTICS", "View analytics dashboards")], max_length=80)),
                ("enabled", models.BooleanField(default=False)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["role", "capability"]},
        ),
        migrations.CreateModel(
            name="AccomplishmentReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("year", models.PositiveIntegerField(default=2026)),
                ("quarter", models.CharField(choices=[("Q1", "1st Quarter"), ("Q2", "2nd Quarter"), ("Q3", "3rd Quarter"), ("Q4", "4th Quarter")], max_length=2)),
                ("campus", models.CharField(blank=True, default="", max_length=150)),
                ("college", models.CharField(blank=True, default="", max_length=255)),
                ("department", models.CharField(blank=True, default="", max_length=255)),
                ("narrative", models.TextField(blank=True, default="")),
                ("activities_count", models.PositiveIntegerField(default=0)),
                ("beneficiaries_count", models.PositiveIntegerField(default=0)),
                ("partners_count", models.PositiveIntegerField(default=0)),
                ("attachment", models.FileField(blank=True, null=True, upload_to="accomplishment_reports/")),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accomplishment_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-year", "quarter", "campus", "department"]},
        ),
        migrations.AddConstraint(
            model_name="rolecapability",
            constraint=models.UniqueConstraint(fields=("role", "capability"), name="unique_role_capability"),
        ),
    ]
