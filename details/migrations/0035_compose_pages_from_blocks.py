"""
Compose every public page from content blocks.

Two long-standing inconsistencies are settled here.

**Services painted its own copies of three builders.** The process accordion,
"Official templates", and "Current office forms" were hardcoded in
``services_home.html`` while the same data also had builders under Content &
Builders — which is exactly why the Template Library appeared in two places
with two renderers and no way to reorder or hide either. Each becomes a real
``PageSection`` bound to the matching content source, carrying the headings and
intro copy the template used, so the published page is unchanged while becoming
editable.

An earlier release auto-created a *hidden* PROCESSES section on Services
because the built-in accordion was showing instead. That row is reused and
unhidden rather than duplicated: it is now the only thing rendering processes.

**Reports and Achievements had no sections of their own.** Their blocks were
conjured on the fly every time an admin opened the editor, so the pages were
empty to a visitor until somebody happened to visit the editor. They are seeded
properly here, once, and then belong to the admin like any other page.
"""

from django.db import migrations


#: ``slug -> [(layout, heading, subheading, anchor), ...]`` in page order.
PAGE_BLOCKS = {
    "services": [
        ("PROCESSES", "Current process flow", "Open a process to view its saved steps.", "maintained-process"),
        ("TEMPLATES", "Official templates", "Download the latest office files.", "template-library"),
        ("FORMS", "Current office forms", "The fields below reflect the current checklist.", "office-forms"),
    ],
    "reports": [
        ("TARGETS", "Extension Targets", "Planned versus actual, by campus.", "targets"),
    ],
    "achievements": [
        ("ACTIVITIES", "Extension Activities", "Completed activities worth highlighting.", "activities"),
    ],
}


def seed_page_blocks(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    PageSection = apps.get_model("details", "PageSection")

    for slug, blocks in PAGE_BLOCKS.items():
        page, _ = SitePage.objects.get_or_create(
            slug=slug, defaults={"title": slug.title()}
        )
        seeded_layouts = {layout for layout, *_ in blocks}

        # Anything the admin already added keeps its relative order, below the
        # seeded blocks.
        offset = len(blocks)
        for section in PageSection.objects.filter(page=page):
            if section.layout not in seeded_layouts:
                PageSection.objects.filter(pk=section.pk).update(order=section.order + offset)

        for position, (layout, heading, subheading, anchor) in enumerate(blocks, start=1):
            existing = PageSection.objects.filter(page=page, layout=layout).first()
            if existing:
                # Reuse the auto-created row: it is the same block.
                PageSection.objects.filter(pk=existing.pk).update(
                    heading=existing.heading or heading,
                    subheading=existing.subheading or subheading,
                    anchor=anchor,
                    is_visible=True,
                    order=position,
                )
                continue

            PageSection.objects.create(
                page=page,
                heading=heading,
                subheading=subheading,
                body="",
                layout=layout,
                anchor=anchor,
                is_visible=True,
                order=position,
            )


def unseed_page_blocks(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    PageSection = apps.get_model("details", "PageSection")

    for slug, blocks in PAGE_BLOCKS.items():
        page = SitePage.objects.filter(slug=slug).first()
        if not page:
            continue
        PageSection.objects.filter(
            page=page, layout__in=[layout for layout, *_ in blocks]
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0034_content_source_registry"),
    ]

    operations = [
        migrations.RunPython(seed_page_blocks, unseed_page_blocks),
    ]
