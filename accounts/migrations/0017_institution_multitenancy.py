# Generated manually for institution-based NExUS tenants.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def default_structure_json():
    # Legacy ISPSC structure converted to the new editable JSON shape.
    legacy = {
        "Candon": {
            "College of Hospitality and Tourism": [
                "Bachelor of Science in Hospitality Management",
                "Bachelor of Science in Tourism Management",
            ],
            "": [
                "Bachelor of Science in Information Technology",
                "Bachelor of Secondary Education",
            ],
        },
        "Main": {
            "College of Arts and Sciences": [
                "Bachelor of Arts in English Language",
                "Bachelor of Arts in Political Science",
                "Bachelor of Science in Computer Science",
            ],
            "College of Business Management & Entrepreneurship": [
                "Bachelor of Science in Business Administration",
                "Bachelor of Science in Office Administration",
            ],
            "Collge of Teacher Education": [
                "Bachelor of Secondary Education",
                "Bachelor of Elementary Education",
                "Bachelor of Physical Education",
                "Bachelor of Culture and Arts Education",
            ],
            "School of Criminal Justice Education": ["Bachelor of Science in Criminology"],
            "College of Health Sciences": [
                "Bachelor of Science in Midwifery",
                "Bachelor of Science in Nursing",
            ],
        },
        "Sta Maria": {
            "College of Teacher Education (CTE)": [
                "Bachelor of Elementary Education",
                "Bachelor of Secondary Education",
                "Bachelor of Technology and Livelihood Education",
            ],
            "College of Computing Studies (CCS)": [
                "Bachelor of Science in Information Technology",
                "Bachelor of Science in Information Systems",
            ],
            "College of Agriculture, Forestry, Engineering, & Development Communication (CAFEDC)": [
                "Bachelor of Science in Agriculture",
                "Bachelor of Science in Forestry",
                "Bachelor of Science in Agroforestry",
                "Bachelor of Science in Agricultural and Biosystems Engineering",
                "Bachelor of Science in Development Communication",
            ],
            "College of Business Management and Entreprenership CBME)": [
                "Bachelor of Science in Hospitality Management",
            ],
            "College of Graduate Studies (CGS)": [
                "Doctor of Education in Educational Management",
                "Doctor of Philosophy in English Language Education",
                "Doctor of Philosophy in Agronomy",
                "Doctor of Philosophy in Technology Education Management",
                "Master of Arts in Education",
            ],
        },
        "Cervantes": {
            "": [
                "Bachelor of Elementary Education",
                "Bachelor of Secondary Education",
                "Bachelor of Science in Information Technology",
                "Bachelor of Science in Criminology",
                "Bachelor of Technology and Livelihood Education",
                "Bachelor of Technical-Vocational Teacher Education",
            ],
        },
        "Tagudin": {
            "College of Teacher Education (CTE)": [
                "Bachelor of Secondary Education",
                "Bachelor of Elementary Education",
                "Bachelor of Physical Education",
            ],
            "College of Arts and Sciences (CAS)": [
                "Bachelor of Arts in Psychology",
                "Bachelor of Arts in Social Science",
                "Bachelor of Science in Mathematics",
                "Bachelor of Science in Information Technology",
                "Bachelor of Arts in English Language",
                "Bachelor of Public Administration",
            ],
            "College of Business Management and Entrepreneurship (CBME)": [
                "Bachelor of Science in Business Administration",
                "Bachelor of Science in Entrepreneurship",
            ],
        },
        "Narvacan": {
            "": [
                "Bachelor of Science in Fisheries",
                "Bachelor of Technology and Livelihood Education",
                "Bachelor of Physical Education",
            ],
        },
        "Santiago": {
            "Institute of Technology": [
                "Bachelor of Science in Industrial Technology",
                "Bachelor of Science in Mechatronics Technology",
            ],
            "College of Teacher Education": ["Bachelor of Technical Vocation Teacher Education"],
        },
    }
    return {
        "campuses": [
            {
                "name": campus,
                "colleges": [
                    {"name": college, "departments": departments}
                    for college, departments in colleges.items()
                ],
            }
            for campus, colleges in legacy.items()
        ]
    }


def seed_default_institution(apps, schema_editor):
    Institution = apps.get_model("accounts", "Institution")
    Profile = apps.get_model("accounts", "Profile")
    Signatory = apps.get_model("accounts", "Signatory")

    institution, _ = Institution.objects.get_or_create(
        slug="ispsc",
        defaults={
            "name": "Ilocos Sur Polytechnic State College",
            "short_name": "ISPSC",
            "contact_email": "ispsc.nexus@gmail.com",
            "structure": default_structure_json(),
            "onboarding_completed_at": timezone.now(),
            "is_active": True,
        },
    )
    Profile.objects.filter(institution__isnull=True).update(institution=institution)
    Signatory.objects.filter(institution__isnull=True).update(institution=institution)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0016_add_evaluator_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="Institution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True)),
                ("short_name", models.CharField(blank=True, default="", max_length=60)),
                ("contact_email", models.EmailField(blank=True, default="", max_length=254)),
                ("email_domain", models.CharField(blank=True, default="", help_text="Optional domain hint for public registrations, e.g. ispsc.edu.ph.", max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("structure", models.JSONField(blank=True, default=dict)),
                ("onboarding_completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_institutions", to=settings.AUTH_USER_MODEL)),
                ("onboarding_completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="completed_institution_onboardings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="profile",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="profiles", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="signatory",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="signatories", to="accounts.institution"),
        ),
        migrations.AlterField(
            model_name="profile",
            name="campus",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AlterField(
            model_name="signatory",
            name="campus",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.RemoveConstraint(
            model_name="signatory",
            name="unique_signatory_per_position_scope",
        ),
        migrations.RunPython(seed_default_institution, noop_reverse),
        migrations.AddConstraint(
            model_name="signatory",
            constraint=models.UniqueConstraint(fields=("institution", "position_title", "campus", "college", "department"), name="unique_signatory_per_institution_position_scope"),
        ),
    ]
