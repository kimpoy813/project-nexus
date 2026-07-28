# Make the Services page's Proposal / MOA / Implementation phase cards
# admin-editable. Seed values mirror the hardcoded list previously defined in
# proposals/views.services_home so the public page is unchanged until edited.

from django.db import migrations, models


PHASES = [
    {
        "key": "proposal",
        "label": "Proposal",
        "summary": "Drafting, review, revision, printing, signed upload, and approval document release.",
        "weight_percent": 40,
        "weight_label": "40% of overall progress when MOA is required",
        "order": 1,
    },
    {
        "key": "moa",
        "label": "MOA",
        "summary": "Optional agreement routing from draft through legal review, certification, agenda, and completion.",
        "weight_percent": 20,
        "weight_label": "20% of overall progress when required",
        "order": 2,
    },
    {
        "key": "implementation",
        "label": "Implementation",
        "summary": "Preparation, monitoring, progress reporting, terminal reporting, review, revision, and completion.",
        "weight_percent": 40,
        "weight_label": "40% of overall progress when MOA is required",
        "order": 3,
    },
]


def seed(apps, schema_editor):
    WorkflowPhase = apps.get_model("details", "WorkflowPhase")
    for data in PHASES:
        WorkflowPhase.objects.get_or_create(key=data["key"], defaults=data)


def unseed(apps, schema_editor):
    apps.get_model("details", "WorkflowPhase").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0010_home_thrusts_and_headings"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowPhase",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "key",
                    models.SlugField(
                        choices=[
                            ("proposal", "Proposal"),
                            ("moa", "MOA"),
                            ("implementation", "Implementation"),
                        ],
                        help_text="Identifies which set of model statuses this phase displays.",
                        max_length=30,
                        unique=True,
                    ),
                ),
                ("label", models.CharField(max_length=80)),
                ("summary", models.TextField(blank=True, default="")),
                (
                    "weight_percent",
                    models.PositiveSmallIntegerField(
                        default=40,
                        help_text="Share of overall progress, 0-100. Also sets the bar width.",
                    ),
                ),
                (
                    "weight_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text='Caption beside the bar, e.g. "40% of overall progress when MOA is required".',
                        max_length=120,
                    ),
                ),
                ("is_visible", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Workflow Phase",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
