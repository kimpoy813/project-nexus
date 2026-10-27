"""Retune the public pages: banner follows the page title, one job per page.

Three things were wrong with the seeded pages and are fixed here.

1. **Stale banners.** Programs still announced itself as "Extension Reports"
   and Gallery as "Extension Achievements" — wording from the pages they
   replaced. The banner now defers to the page title (``SitePage.hero_title``),
   so those overrides are cleared and only the supporting sentence is written.

2. **Secondary sections.** Programs carried an Extension Targets block and
   Gallery an Activities block, both of which showed "nothing here yet" on a
   system with no data, and neither of which is what the visitor came for. Each
   page now holds exactly one section: its directory, or its gallery.

3. **The About page.** It was one paragraph and a call to action. It now opens
   with what the office is and does, lists the campuses it actually serves
   (from ``accounts.Campus``, with live programme counts), and closes with the
   ways to work with it.

The copy stays factual: it describes the workflow the code implements and the
campuses the institution records. Nothing here invents history, awards, or
numbers.
"""

from django.db import migrations


ABOUT_INTRO = """
<p>The <strong>ISPSC-RDEI Extension Office</strong> plans, reviews, and records the
institution's extension work: the programs, projects, and activities that carry
research and instruction out to partner communities.</p>
<p><strong>NExUS</strong> — the Networked Extension Unified System — is where that work is
managed. A proponent drafts a proposal, the right offices review and approve it,
the signed copy and the approval documents are released, a MOA is tracked when
one is required, and implementation is reported stage by stage until the
terminal report is filed.</p>
<p>Because every step is recorded here, the public pages are not a separate
publication to keep up to date: <a href="/programs/">Programs</a> lists what has been
approved, each program's document is its own signed proposal or legacy upload,
and <a href="/gallery/">Gallery</a> shows the photographs submitted with terminal
reports.</p>
"""

#: "Services" is ``services_home``, which lives at /proposals/ — the same page
#: that holds the workflow, the official templates, and the proposal workspace.
ABOUT_CTA_BODY = """
<p>Proponents and offices work through <a href="/proposals/">Services</a>: the
process from proposal to implementation, the official templates, and the
workspace where a proposal is filed and followed. Partner communities, agencies,
and researchers can reach the office at
<a href="mailto:ispsc.nexus@gmail.com">ispsc.nexus@gmail.com</a>.</p>
"""

#: The banner heading is the page title, so only the supporting line is written
#: here — an eyebrow that just repeats the heading would be noise.
HERO_DEFAULTS = {
    # slug: (eyebrow, subheading)
    "programs": (
        "Extension Programs",
        "Every extension program approved in this system, with its campus, year, "
        "participants, objectives, and the document behind it.",
    ),
    "gallery": (
        "Documentation",
        "Photographs from the extension activities documented in terminal reports.",
    ),
    "about": (
        "ISPSC-RDEI Extension Office",
        "The office behind this platform: what it does, the campuses it serves, "
        "and how to work with it.",
    ),
}

#: Sections that do not belong to the page they were seeded on.
OBSOLETE_SECTIONS = {
    "programs": ("TARGETS",),
    "gallery": ("ACTIVITIES",),
}


def _clear_stale_heroes(apps, schema_editor):
    SitePage = apps.get_model("details", "SitePage")

    for slug, (eyebrow, subheading) in HERO_DEFAULTS.items():
        page = SitePage.objects.filter(slug=slug).first()
        if page is None:
            continue
        page.hero_eyebrow = eyebrow
        page.hero_subheading = subheading
        # Drop any hand-written heading that no longer matches the page title;
        # the banner then tracks the title on every future rename.
        if page.hero_heading.strip().casefold() != page.title.strip().casefold():
            page.hero_heading = ""
        page.save(update_fields=["hero_eyebrow", "hero_heading", "hero_subheading"])


def _drop_secondary_sections(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")

    for slug, layouts in OBSOLETE_SECTIONS.items():
        PageSection.objects.filter(page__slug=slug, layout__in=layouts).delete()


def _rebuild_about(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    about_id = _page_id(apps, "about")

    # The seeded About page was one paragraph plus a button; rebuild it rather
    # than patch it, so a fresh install and an upgraded one end up identical.
    PageSection.objects.filter(page_id=about_id).delete()

    PageSection.objects.create(
        page_id=about_id,
        layout="RICH_TEXT",
        heading="About the Extension Office",
        subheading="What this office does, and what this platform does for it.",
        body=ABOUT_INTRO,
        anchor="about-the-office",
        order=1,
    )
    PageSection.objects.create(
        page_id=about_id,
        layout="CAMPUSES",
        heading="Campuses we serve",
        subheading=(
            "Each campus runs its own extension work. The count beside a campus "
            "is how many of its programs are published in this system."
        ),
        anchor="campuses",
        order=2,
    )
    PageSection.objects.create(
        page_id=about_id,
        layout="CTA",
        heading="Work with the Extension Office",
        subheading="Where to start, whichever side of the work you are on.",
        body=ABOUT_CTA_BODY,
        cta_label="Start a proposal",
        cta_url="/proposals/",
        anchor="work-with-us",
        order=3,
    )


def _page_id(apps, slug):
    SitePage = apps.get_model("details", "SitePage")
    return SitePage.objects.get(slug=slug).pk


def forwards(apps, schema_editor):
    _clear_stale_heroes(apps, schema_editor)
    _drop_secondary_sections(apps, schema_editor)
    _rebuild_about(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0049_alter_pagesection_layout_alter_sitepage_hero_heading"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
