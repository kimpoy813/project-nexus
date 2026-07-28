# Admin-editable public page content (Home, Services, Reports, Achievements)

import django.db.models.deletion
import django_ckeditor_5.fields
from django.conf import settings
from django.db import migrations, models


PAGE_SEEDS = [
    {
        "slug": "home",
        "title": "Home",
        "hero_heading": "Networked Extension Unified System",
        "hero_subheading": (
            "A digital platform for managing, monitoring, and advancing institutional "
            "extension initiatives aligned with sustainable development goals."
        ),
        "meta_title": "",
        "meta_description": "",
    },
    {
        "slug": "services",
        "title": "Services",
        "hero_eyebrow": "Extension Services",
        "hero_heading": "Proposal processing, review, approval, and implementation in one guided flow.",
        "hero_subheading": (
            "The services page follows the maintained process records and the Proposal model "
            "lifecycle: a guided proposal wizard, review rounds, post-approval document release, "
            "optional MOA routing, and implementation reporting."
        ),
        "meta_title": "",
        "meta_description": "",
    },
    {
        "slug": "reports",
        "title": "Reports",
        "hero_eyebrow": "Extension Reports",
        "hero_heading": "Extension reports and documentation",
        "hero_subheading": (
            "Consolidated reporting on extension programs, projects, and activities "
            "across all campuses."
        ),
        "meta_title": "",
        "meta_description": "",
    },
    {
        "slug": "achievements",
        "title": "Achievements",
        "hero_eyebrow": "Extension Achievements",
        "hero_heading": "Milestones and recognitions",
        "hero_subheading": (
            "Highlights, awards, and measurable outcomes from institutional extension work."
        ),
        "meta_title": "",
        "meta_description": "",
    },
]


def seed_pages(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    for seed in PAGE_SEEDS:
        SitePage.objects.get_or_create(slug=seed["slug"], defaults=seed)


def unseed_pages(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    SitePage.objects.filter(slug__in=[s["slug"] for s in PAGE_SEEDS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0008_wizard_step_config_role_capability_reports"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SitePage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "slug",
                    models.SlugField(
                        choices=[
                            ("home", "Home"),
                            ("services", "Services"),
                            ("reports", "Reports"),
                            ("achievements", "Achievements"),
                        ],
                        max_length=40,
                        unique=True,
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                ("hero_eyebrow", models.CharField(blank=True, default="", max_length=120)),
                ("hero_heading", models.CharField(blank=True, default="", max_length=220)),
                ("hero_subheading", models.TextField(blank=True, default="")),
                ("meta_title", models.CharField(blank=True, default="", max_length=180)),
                ("meta_description", models.TextField(blank=True, default="")),
                (
                    "is_published",
                    models.BooleanField(
                        default=True,
                        help_text="Unpublish to hide this page from visitors (admins can still preview it).",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="site_page_updates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Site Page",
                "ordering": ["slug"],
            },
        ),
        migrations.CreateModel(
            name="PageSection",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("heading", models.CharField(blank=True, default="", max_length=220)),
                ("subheading", models.CharField(blank=True, default="", max_length=300)),
                ("body", django_ckeditor_5.fields.CKEditor5Field(blank=True, default="")),
                (
                    "layout",
                    models.CharField(
                        choices=[
                            ("RICH_TEXT", "Rich text"),
                            ("CARD", "Card"),
                            ("CALLOUT", "Callout / highlight"),
                        ],
                        default="RICH_TEXT",
                        max_length=20,
                    ),
                ),
                (
                    "anchor",
                    models.SlugField(
                        blank=True,
                        default="",
                        help_text="Optional #anchor so the section can be linked to directly.",
                        max_length=60,
                    ),
                ),
                ("image", models.ImageField(blank=True, null=True, upload_to="page_sections/")),
                ("is_visible", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="details.sitepage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Page Section",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed_pages, unseed_pages),
    ]
