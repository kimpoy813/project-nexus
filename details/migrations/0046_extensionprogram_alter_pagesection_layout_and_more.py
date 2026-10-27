"""
Replace the Reports and Achievements pages with Programs, Gallery, and About.

The public navigation used to end with **Reports** and **Achievements**, two
pages whose blocks were generic (targets and activities). The site now ends
with **Programs** — the directory of every extension program, backed by the
new ``ExtensionProgram`` table — **Gallery** (photographs of those programs),
and **About** (the Extension Office's story).

Existing admin edits are carried over rather than discarded: the Reports page
is renamed to Programs and Achievements to Gallery, keeping every section the
office already composed. The new directory/gallery blocks are then seeded at
the top of each page, and About gets its first content.

Deleting the two old pages instead would have silently dropped published
copy, so the rename is deliberate. The old URLs (/reports/, /achievements/)
permanently redirect to their replacements (see ``details/urls.py``).
"""

from django.db import migrations, models
from django.db.models import F

import details.models
import django.db.models.deletion


#: Old page slug -> replacement, so existing sections follow the page.
PAGE_RENAMES = {
    "reports": "programs",
    "achievements": "gallery",
}

#: Page headers. Blank hero fields are filled in on existing rows; anything an
#: admin already wrote is left untouched.
NEW_PAGES = [
    {
        "slug": "programs",
        "title": "Programs",
        "hero_eyebrow": "Extension Programs",
        "hero_heading": "Every extension program, in one place",
        "hero_subheading": (
            "Browse the institution's extension programs across every campus — "
            "filter by year, type, research basis, or the group that led the work."
        ),
        "meta_title": "",
        "meta_description": (
            "The complete directory of extension programs: campus, year, type, "
            "research basis, partner communities, and participants served."
        ),
    },
    {
        "slug": "gallery",
        "title": "Gallery",
        "hero_eyebrow": "Program Gallery",
        "hero_heading": "Pictures of extension programs",
        "hero_subheading": (
            "Moments from the field: trainings, distributions, and the partner "
            "communities the institution works with."
        ),
        "meta_title": "",
        "meta_description": "Photographs of the institution's extension programs.",
    },
    {
        "slug": "about",
        "title": "About",
        "hero_eyebrow": "About NExUS",
        "hero_heading": "One system for the institution's extension work",
        "hero_subheading": (
            "Who the Extension Office is, what it does, and how this platform "
            "supports the work from proposal to implementation."
        ),
        "meta_title": "",
        "meta_description": (
            "About the Extension Office and NExUS, the Networked Extension "
            "Unified System."
        ),
    },
]

ABOUT_BODY = (
    "<p>NExUS — the Networked Extension Unified System — brings the "
    "institution's extension work together in one place: the programs the "
    "office runs, the people who run them, and the documents that record "
    "them.</p>"
    "<p>The platform supports the whole extension lifecycle described on the "
    "Services page: preparing and routing a proposal, reviewing it with the "
    "right offices, releasing approved documents, optional MOA tracking, and "
    "reporting on implementation.</p>"
    "<p>Use <a href=\"/programs/\">Programs</a> to browse what the institution "
    "has already delivered across its campuses, and "
    "<a href=\"/gallery/\">Gallery</a> to see the work in the field.</p>"
)

#: Sections seeded on each new page, in order, only when that layout is not
#: already present. ``body`` / ``cta_*`` are optional per block.
PAGE_BLOCKS = {
    "programs": [
        {
            "layout": "PROGRAMS",
            "heading": "Extension Programs",
            "subheading": (
                "Every published program, with the totals and filters the "
                "office reports on."
            ),
            "anchor": "all-programs",
        },
    ],
    "gallery": [
        {
            "layout": "GALLERY",
            "heading": "Program Gallery",
            "subheading": "Photographs from the institution's extension programs.",
            "anchor": "program-gallery",
        },
    ],
    "about": [
        {
            "layout": "RICH_TEXT",
            "heading": "About the Extension Office",
            "subheading": "",
            "anchor": "about-the-office",
            "body": ABOUT_BODY,
        },
        {
            "layout": "CTA",
            "heading": "See the work",
            "subheading": "",
            "anchor": "start-a-proposal",
            "cta_label": "Explore the programs",
            "cta_url": "/programs/",
        },
    ],
}


def _rename_pages(SitePage, old_to_new):
    for old, new in old_to_new.items():
        old_page = SitePage.objects.filter(slug=old).first()
        if old_page is None:
            continue
        if SitePage.objects.filter(slug=new).exists():
            # Both rows exist (e.g. a hand-created page): leave the live one.
            continue
        old_page.slug = new
        old_page.title = new.title()
        old_page.save(update_fields=["slug", "title"])


def seed_new_pages(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    PageSection = apps.get_model("details", "PageSection")

    _rename_pages(SitePage, PAGE_RENAMES)

    for seed in NEW_PAGES:
        page, created = SitePage.objects.get_or_create(slug=seed["slug"], defaults=seed)
        if created:
            continue
        # Fill only blank copy, so an admin's hero is never overwritten.
        changed = False
        for field, value in seed.items():
            if field == "slug":
                continue
            if not getattr(page, field):
                setattr(page, field, value)
                changed = True
        if changed:
            page.save()

    for slug, blocks in PAGE_BLOCKS.items():
        page = SitePage.objects.filter(slug=slug).first()
        if page is None:
            continue

        existing_layouts = set(
            PageSection.objects.filter(page=page).values_list("layout", flat=True)
        )
        missing = [block for block in blocks if block["layout"] not in existing_layouts]
        if not missing:
            continue

        # The seeded blocks belong at the top; anything the admin already
        # composed keeps its relative order below them.
        PageSection.objects.filter(page=page).update(order=F("order") + len(missing))
        for position, block in enumerate(missing, start=1):
            PageSection.objects.create(
                page=page,
                layout=block["layout"],
                heading=block.get("heading", ""),
                subheading=block.get("subheading", ""),
                body=block.get("body", ""),
                anchor=block.get("anchor", ""),
                cta_label=block.get("cta_label", ""),
                cta_url=block.get("cta_url", ""),
                is_visible=True,
                order=position,
            )


def unseed_new_pages(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    PageSection = apps.get_model("details", "PageSection")

    PageSection.objects.filter(layout__in=["PROGRAMS", "GALLERY"]).delete()
    SitePage.objects.filter(slug="about").delete()
    _rename_pages(SitePage, {new: old for old, new in PAGE_RENAMES.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('details', '0045_quarterlyreportrequest_accomplishmentreport_request_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtensionProgram',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('campus', models.CharField(blank=True, default='', help_text='Campus that carried out the program, e.g. “Main Campus”.', max_length=100)),
                ('year', models.PositiveSmallIntegerField(default=details.models._current_year, help_text='Reporting year used by the Programs page filter.')),
                ('extension_type', models.CharField(choices=[('COMMUNITY_BASED', 'Community-based'), ('REQUEST_BASED', 'Request-based'), ('RESEARCH_BASED', 'Research-based')], default='COMMUNITY_BASED', max_length=20)),
                ('research_basis', models.CharField(choices=[('FACULTY', 'Based on Faculty Research'), ('STUDENT', 'Based on Student Research'), ('OTHERS', 'Others')], default='OTHERS', max_length=20)),
                ('led_by', models.CharField(choices=[('FACULTY', 'Faculty'), ('JOINT', 'Joint'), ('STUDENT', 'Student')], default='FACULTY', max_length=20, verbose_name='Led by')),
                ('target_community', models.CharField(blank=True, default='', help_text='Partner school, barangay, LGU, or group served.', max_length=255)),
                ('duration', models.CharField(blank=True, default='', help_text='Schedule as it should be published, e.g. “January–October 2025”.', max_length=150)),
                ('objectives', models.TextField(blank=True, default='', help_text='One objective per line; shown when a visitor opens Full details.')),
                ('student_participants', models.PositiveIntegerField(default=0)),
                ('faculty_participants', models.PositiveIntegerField(default=0)),
                ('research_staff_participants', models.PositiveIntegerField(default=0)),
                ('beneficiaries', models.PositiveIntegerField(default=0, help_text='Community members served.')),
                ('cover_image', models.ImageField(blank=True, help_text='Optional photo shown on the program card.', null=True, upload_to='programs/')),
                ('document_url', models.URLField(blank=True, default='', help_text='Link to the full document, e.g. a Google Drive file.')),
                ('is_visible', models.BooleanField(default=True, help_text='Uncheck to hide this program from the public Programs page.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Extension Program',
                'ordering': ['-year', 'title'],
            },
        ),
        migrations.AlterField(
            model_name='pagesection',
            name='layout',
            field=models.CharField(choices=[('RICH_TEXT', 'Rich text'), ('CARD', 'Card'), ('CALLOUT', 'Callout / highlight'), ('CTA', 'Call to action'), ('THRUST', 'Extension Thrust cards'), ('PROCESSES', 'Extension Processes'), ('TARGETS', 'Extension Targets'), ('PERSONNEL', 'Extension Personnel'), ('SDG', 'Sustainable Development Goals'), ('ACTIVITIES', 'Extension Activities'), ('TEMPLATES', 'Template Library'), ('PROGRAMS', 'Extension Programs'), ('GALLERY', 'Program Gallery')], default='RICH_TEXT', max_length=20),
        ),
        migrations.AlterField(
            model_name='sitepage',
            name='slug',
            field=models.SlugField(choices=[('home', 'Home'), ('services', 'Services'), ('programs', 'Programs'), ('gallery', 'Gallery'), ('about', 'About')], max_length=40, unique=True),
        ),
        migrations.CreateModel(
            name='GalleryPhoto',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, default='', help_text='Short caption, e.g. “Seedling distribution in Sta. Maria”.', max_length=180)),
                ('caption', models.TextField(blank=True, default='', help_text='Optional longer description shown in the lightbox.')),
                ('image', models.ImageField(upload_to='gallery/')),
                ('campus', models.CharField(blank=True, default='', help_text='Only needed when the photo is not attached to a program.', max_length=100)),
                ('taken_on', models.DateField(blank=True, help_text='Optional date the photo was taken.', null=True)),
                ('is_visible', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('program', models.ForeignKey(blank=True, help_text='Optional program this photo belongs to.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='photos', to='details.extensionprogram')),
            ],
            options={
                'verbose_name': 'Gallery Photo',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.RunPython(seed_new_pages, unseed_new_pages),
    ]
