from django.db import migrations, models

def populate_home_sections_as_page_sections(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    PageSection = apps.get_model("details", "PageSection")
    HomeSectionHeading = apps.get_model("details", "HomeSectionHeading")

    home, _ = SitePage.objects.get_or_create(slug="home", defaults={"title": "Home"})

    # If home already has sections, don't re-seed
    if PageSection.objects.filter(page=home).exists():
        return

    section_defs = [
        {
            "section": "thrust",
            "heading": "Extension Thrust",
            "subheading": "Isem Ni Aran",
            "body": "<p>Approved BR No. 95-1517, S. 2022</p>",
            "layout": "THRUST",
            "anchor": "thrust",
            "order": 1,
        },
        {
            "section": "process",
            "heading": "Extension Processes",
            "subheading": "",
            "body": "",
            "layout": "PROCESSES",
            "anchor": "process",
            "order": 2,
        },
        {
            "section": "targets",
            "heading": "Extension Targets",
            "subheading": "",
            "body": "",
            "layout": "TARGETS",
            "anchor": "targets",
            "order": 3,
        },
        {
            "section": "personnel",
            "heading": "Extension Personnel",
            "subheading": "",
            "body": "",
            "layout": "PERSONNEL",
            "anchor": "personnel",
            "order": 4,
        },
        {
            "section": "sdg",
            "heading": "Sustainable Development Goals",
            "subheading": "",
            "body": "",
            "layout": "SDG",
            "anchor": "sdg",
            "order": 5,
        },
        {
            "section": "activities",
            "heading": "Extension Activities",
            "subheading": "",
            "body": "",
            "layout": "ACTIVITIES",
            "anchor": "activities",
            "order": 6,
        },
    ]

    for item in section_defs:
        heading = item["heading"]
        subheading = item["subheading"]
        body = item["body"]
        is_visible = True

        hsh = HomeSectionHeading.objects.filter(section=item["section"]).first()
        if hsh:
            heading = hsh.heading or heading
            subheading = hsh.subtitle or subheading
            if hsh.caption:
                body = f"<p>{hsh.caption}</p>"
            is_visible = hsh.is_visible

        PageSection.objects.create(
            page=home,
            heading=heading,
            subheading=subheading,
            body=body,
            layout=item["layout"],
            anchor=item["anchor"],
            order=item["order"],
            is_visible=is_visible,
        )

def unseed_home_sections(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")
    PageSection = apps.get_model("details", "PageSection")
    home = SitePage.objects.filter(slug="home").first()
    if home:
        PageSection.objects.filter(page=home).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('details', '0032_page_blocks_and_content_log'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pagesection',
            name='layout',
            field=models.CharField(
                choices=[
                    ('RICH_TEXT', 'Rich text'),
                    ('CARD', 'Card'),
                    ('CALLOUT', 'Callout / highlight'),
                    ('CTA', 'Call to action'),
                    ('THRUST', 'Extension thrust cards'),
                    ('PROCESSES', 'Extension processes'),
                    ('TARGETS', 'Targets (planned vs. actual)'),
                    ('PERSONNEL', 'Extension personnel'),
                    ('SDG', 'Sustainable Development Goals'),
                    ('ACTIVITIES', 'Extension activities'),
                    ('TEMPLATES', 'Template library'),
                ],
                default='RICH_TEXT',
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_home_sections_as_page_sections, unseed_home_sections),
    ]
