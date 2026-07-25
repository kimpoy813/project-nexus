# Generated for admin no-code builder models on 2026-07-25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0005_alter_extensionprocess_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("category", models.CharField(choices=[("PROPOSAL", "Proposal"), ("MOA", "MOA"), ("IMPLEMENTATION", "Implementation"), ("REPORT", "Report"), ("CERTIFICATE", "Certificate"), ("OTHER", "Other")], default="PROPOSAL", max_length=30)),
                ("description", models.TextField(blank=True, default="")),
                ("file", models.FileField(upload_to="office_templates/")),
                ("version_label", models.CharField(blank=True, default="", max_length=40)),
                ("is_active", models.BooleanField(default=True)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["category", "title", "-updated_at"]},
        ),
        migrations.CreateModel(
            name="DynamicFormTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("applies_to", models.CharField(choices=[("PROPOSAL", "Proposal"), ("MOA", "MOA"), ("IMPLEMENTATION", "Implementation"), ("EVALUATION", "Evaluation"), ("GENERAL", "General")], default="GENERAL", max_length=30)),
                ("description", models.TextField(blank=True, default="")),
                ("instructions", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["applies_to", "name"]},
        ),
        migrations.CreateModel(
            name="DynamicFormField",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=180)),
                ("field_key", models.SlugField(max_length=120)),
                ("field_type", models.CharField(choices=[("TEXT", "Short Text"), ("TEXTAREA", "Long Text"), ("NUMBER", "Number"), ("DATE", "Date"), ("EMAIL", "Email"), ("SELECT", "Dropdown"), ("CHECKBOX", "Checkbox"), ("FILE", "File Upload")], default="TEXT", max_length=20)),
                ("required", models.BooleanField(default=False)),
                ("placeholder", models.CharField(blank=True, default="", max_length=180)),
                ("help_text", models.CharField(blank=True, default="", max_length=255)),
                ("choices_text", models.TextField(blank=True, default="", help_text="One dropdown choice per line.")),
                ("order", models.PositiveIntegerField(default=1)),
                ("form", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fields", to="details.dynamicformtemplate")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="dynamicformfield",
            constraint=models.UniqueConstraint(fields=("form", "field_key"), name="unique_dynamic_form_field_key"),
        ),
    ]
