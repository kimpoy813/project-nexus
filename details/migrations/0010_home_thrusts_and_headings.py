# Make the Home page's built-in sections admin-editable:
# the Extension Thrust cards ("Isem Ni Aran") and each section's headings.
#
# Seed data mirrors exactly what was previously hardcoded in
# details/templates/details/details_page.html so the public page is
# unchanged until an admin edits something.

from django.db import migrations, models


THRUSTS = [
    ("Indigenous Heritage Protection", "Protecting cultural heritage and indigenous rights within community extension activities.", "text-green-600"),
    ("Environmental Protection", "Programs that conserve ecosystems and promote sustainable practices.", "text-blue-600"),
    ("Resource Sharing", "Facilitating equitable distribution and community access to resources.", "text-yellow-500"),
    ("Numeracy and Literacy", "Adult and community education initiatives to improve literacy and numeracy.", "text-purple-600"),
    ("Governance and Administration", "Capacity-building and systems strengthening for local governance and administration.", "text-red-600"),
    ("IP-TBM Office Establishment", "Setting up institutional structures for technology-business management and IP.", "text-indigo-600"),
    ("Trade Fair and Exhibit", "Showcasing local products and linking producers to markets.", "text-pink-500"),
    ("Technology Transfer & RD Results Dissemination", "Dissemination of research outputs and support for technology uptake.", "text-teal-600"),
    ("Network and Linkage", "Building partnerships, MOUs, and collaborative networks.", "text-orange-500"),
    ("Adult Education", "Lifelong learning programs and vocational upskilling for adults.", "text-lime-600"),
    ("Calamity & Disaster Rehabilitation", "Relief operations, rehabilitation, and disaster risk reduction activities.", "text-rose-500"),
    ("Entrepreneurship & Financial Literacy", "Microenterprise support, financial literacy trainings, and market linkages.", "text-amber-500"),
    ("Health and Nutrition", "Health promotion, nutrition education, and preventive care outreach.", "text-cyan-600"),
    ("Advocacies & Social Justice", "Community advocacy, rights awareness, and social justice initiatives.", "text-violet-600"),
]

HEADINGS = [
    {
        "section": "thrust",
        "heading": "Extension Thrust",
        "subtitle": "Isem Ni Aran",
        "caption": "Approved BR No. 95-1517, S. 2022",
        "nav_label": "Thrust",
        "order": 1,
    },
    {"section": "process", "heading": "Extension Processes", "nav_label": "Processes", "order": 2},
    {"section": "targets", "heading": "Extension Targets", "nav_label": "Targets", "order": 3},
    {"section": "personnel", "heading": "Extension Personnel", "nav_label": "Personnel", "order": 4},
    {"section": "sdg", "heading": "Sustainable Development Goals", "nav_label": "SDGs", "order": 5},
    {"section": "activities", "heading": "Extension Activities", "nav_label": "Activities", "order": 6},
]


def seed(apps, schema_editor):
    HomeThrust = apps.get_model("details", "HomeThrust")
    HomeSectionHeading = apps.get_model("details", "HomeSectionHeading")

    if not HomeThrust.objects.exists():
        for index, (title, description, color) in enumerate(THRUSTS, start=1):
            HomeThrust.objects.create(
                title=title,
                description=description,
                color_class=color,
                order=index,
                is_visible=True,
            )

    for data in HEADINGS:
        HomeSectionHeading.objects.get_or_create(section=data["section"], defaults=data)


def unseed(apps, schema_editor):
    apps.get_model("details", "HomeThrust").objects.all().delete()
    apps.get_model("details", "HomeSectionHeading").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0009_site_pages"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeSectionHeading",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "section",
                    models.SlugField(
                        choices=[
                            ("thrust", "Extension Thrust"),
                            ("process", "Extension Processes"),
                            ("targets", "Extension Targets"),
                            ("personnel", "Extension Personnel"),
                            ("sdg", "Sustainable Development Goals"),
                            ("activities", "Extension Activities"),
                        ],
                        max_length=40,
                        unique=True,
                    ),
                ),
                ("heading", models.CharField(blank=True, default="", max_length=200)),
                (
                    "subtitle",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text='Emphasised line under the heading, e.g. "Isem Ni Aran".',
                        max_length=200,
                    ),
                ),
                (
                    "caption",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text='Smaller line under the subtitle, e.g. "Approved BR No. 95-1517, S. 2022".',
                        max_length=255,
                    ),
                ),
                (
                    "nav_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Label used in the sticky section navigation.",
                        max_length=60,
                    ),
                ),
                (
                    "is_visible",
                    models.BooleanField(
                        default=True,
                        help_text="Uncheck to hide this whole section from the Home page.",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Home Section Heading",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="HomeThrust",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "color_class",
                    models.CharField(
                        choices=[
                            ("text-green-600", "Green"),
                            ("text-blue-600", "Blue"),
                            ("text-yellow-500", "Yellow"),
                            ("text-purple-600", "Purple"),
                            ("text-red-600", "Red"),
                            ("text-indigo-600", "Indigo"),
                            ("text-pink-500", "Pink"),
                            ("text-teal-600", "Teal"),
                            ("text-orange-500", "Orange"),
                            ("text-lime-600", "Lime"),
                            ("text-rose-500", "Rose"),
                            ("text-amber-500", "Amber"),
                            ("text-cyan-600", "Cyan"),
                            ("text-violet-600", "Violet"),
                            ("text-gray-700", "Gray"),
                        ],
                        default="text-green-600",
                        help_text="Accent colour for the card title.",
                        max_length=40,
                    ),
                ),
                ("is_visible", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Home Extension Thrust",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed, unseed),
    ]
