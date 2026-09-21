# Make the last hardcoded copy on the Home and Services pages admin-editable:
#
# * the 17 SDG badges on the Home page (previously 17 copy-pasted cards), and
# * the eyebrows/headings/helper text of the six built-in Services sections.
#
# Seed data mirrors exactly what was previously hardcoded in the templates so
# the public pages are unchanged until an admin edits something.

from django.db import migrations, models


SDG_LABELS = [
    ("01", "No Poverty"),
    ("02", "Zero Hunger"),
    ("03", "Good Health and Well-being"),
    ("04", "Quality Education"),
    ("05", "Gender Equality"),
    ("06", "Clean Water and Sanitation"),
    ("07", "Affordable and Clean Energy"),
    ("08", "Decent Work and Economic Growth"),
    ("09", "Industry, Innovation and Infrastructure"),
    ("10", "Reduced Inequalities"),
    ("11", "Sustainable Cities and Communities"),
    ("12", "Responsible Consumption and Production"),
    ("13", "Climate Action"),
    ("14", "Life Below Water"),
    ("15", "Life on Land"),
    ("16", "Peace, Justice and Strong Institutions"),
    ("17", "Partnerships for the Goals"),
]


SERVICE_BLOCKS = [
    {
        "key": "workflow",
        "eyebrow": "Workflow",
        "heading": "From proposal to implementation",
        "subheading": "Each ring is that phase's share of overall progress",
        "footer_note": (
            "The three weights total {total}% of overall progress and are maintained by the "
            "Extension Office. When a project needs no MOA, that share is redistributed across "
            "Proposal and Implementation."
        ),
        "empty_text": "",
        "nav_label": "",
        "anchor": "",
        "order": 1,
    },
    {
        "key": "process",
        "eyebrow": "Process records",
        "heading": "Current process flow",
        "subheading": "Open a process to view its saved steps.",
        "footer_note": "",
        "empty_text": "No process records are published yet.",
        "nav_label": "Process flow",
        "anchor": "maintained-process",
        "order": 2,
    },
    {
        "key": "templates",
        "eyebrow": "Downloads",
        "heading": "Official templates",
        "subheading": "Download the latest office files.",
        "footer_note": "",
        "empty_text": "No office templates are published yet.",
        "nav_label": "Templates",
        "anchor": "template-library",
        "order": 3,
    },
    {
        "key": "forms",
        "eyebrow": "Requirements",
        "heading": "Current office forms",
        "subheading": "The fields below reflect the current checklist.",
        "footer_note": "",
        "empty_text": "No admin-managed forms are published yet.",
        "nav_label": "Forms",
        "anchor": "office-forms",
        "order": 4,
    },
    {
        "key": "checklist",
        "eyebrow": "Proposal checklist",
        "heading": "{count} sections before submission",
        "subheading": "A quick view of the proposal wizard.",
        "footer_note": "",
        "empty_text": "",
        "nav_label": "Proposal checklist",
        "anchor": "proposal-wizard",
        "order": 5,
    },
    {
        "key": "lifecycle",
        "eyebrow": "Status tracking",
        "heading": "Proposal progress",
        "subheading": (
            "The large ring is the phase's share of overall progress; the small rings track "
            "how far each status has moved that phase forward."
        ),
        "footer_note": "",
        "empty_text": "",
        "nav_label": "Status tracking",
        "anchor": "status-lifecycle",
        "order": 6,
    },
]


def seed(apps, schema_editor):
    HomeSDG = apps.get_model("details", "HomeSDG")
    ServiceSectionCopy = apps.get_model("details", "ServiceSectionCopy")

    if not HomeSDG.objects.exists():
        for index, (code, label) in enumerate(SDG_LABELS, start=1):
            HomeSDG.objects.create(
                code=code,
                label=label,
                order=index,
                is_visible=True,
            )

    for data in SERVICE_BLOCKS:
        ServiceSectionCopy.objects.get_or_create(key=data["key"], defaults=data)


def unseed(apps, schema_editor):
    apps.get_model("details", "HomeSDG").objects.all().delete()
    apps.get_model("details", "ServiceSectionCopy").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0031_wizard_step_display_order"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeSDG",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "code",
                    models.CharField(
                        help_text='Badge number, e.g. "01". Picks the artwork file static/sdg/<code>.png.',
                        max_length=10,
                        unique=True,
                    ),
                ),
                ("label", models.CharField(max_length=120)),
                ("is_visible", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Home SDG Badge",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ServiceSectionCopy",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "key",
                    models.SlugField(
                        choices=[
                            ("workflow", "Workflow at a glance"),
                            ("process", "Process flow"),
                            ("templates", "Template library"),
                            ("forms", "Office forms"),
                            ("checklist", "Proposal checklist"),
                            ("lifecycle", "Status lifecycle"),
                        ],
                        max_length=30,
                        unique=True,
                    ),
                ),
                (
                    "eyebrow",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Small uppercase label above the heading.",
                        max_length=120,
                    ),
                ),
                ("heading", models.CharField(blank=True, default="", max_length=220)),
                ("subheading", models.CharField(blank=True, default="", max_length=300)),
                (
                    "footer_note",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Small print under the section. The workflow block may use {total} for the live weight total.",
                    ),
                ),
                (
                    "empty_text",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Message shown when this section has no records yet.",
                        max_length=220,
                    ),
                ),
                (
                    "nav_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Label in the jump-link nav. Blank hides this section from the nav.",
                        max_length=60,
                    ),
                ),
                (
                    "anchor",
                    models.SlugField(
                        blank=True,
                        default="",
                        help_text="Section id the jump link scrolls to.",
                        max_length=60,
                    ),
                ),
                (
                    "is_visible",
                    models.BooleanField(
                        default=True,
                        help_text="Uncheck to hide this whole section from the Services page.",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Services Section Copy",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
