"""Point the About page at the system itself.

The page was about the office that runs NExUS and the campuses it serves. But a
visitor who opens "About" on a platform wants to know what the platform is, who
built it, what it runs on, and what it does — so the page is rewritten around
the system:

1. **About NExUS** — what it is, who uses it, and why it exists.
2. **The system at a glance** — developer, the office it was built for, and the
   stack, rendered by the new ``SYSTEM_PROFILE`` block from
   ``details/system_profile.py``.
3. **What NExUS does** — the capabilities a user actually gets, each one a
   feature of this codebase.
4. **Get started** — how to reach the workflow and the office.

The campuses block stays registered, so the office can still drop it onto any
page from the block palette; it simply is not what "About" is for.

Everything here is checkable against the repository: the institution name comes
from the MOA generator, the stack from ``requirements.txt`` / ``render.yaml``,
and the contact address from the site configuration.
"""

from django.db import migrations


ABOUT_SYSTEM = """
<p><strong>NExUS — the Networked Extension Unified System</strong> is the web
system the ISPSC-RDEI Extension Office uses to run its extension work. A
proposal is written in it, reviewed in it, approved in it, and reported on in
it, so a single record follows the work from the first draft to the terminal
report instead of being scattered across folders and inboxes.</p>
<p>It is used by proponents — faculty and students — who write and submit
proposals; by reviewers, coordinators, and the director, who evaluate and
approve them; and by Extension Office staff, who track MOAs, implementation,
and reporting. The public side of the site is generated from the same records:
<a href="/programs/">Programs</a> lists what has been approved, and
<a href="/gallery/">Gallery</a> shows the documentation photographs filed with
terminal reports.</p>
<p>NExUS was developed by <strong>Kim Dave Rafael</strong> for the ISPSC-RDEI
Extension Office of the Ilocos Sur Polytechnic State College (ISPSC).</p>
"""

WHAT_IT_DOES = """
<ul>
  <li><strong>Proposal writing.</strong> A guided, section-by-section wizard with
  autosave, collaborators, and the dynamic fields a proposal actually requires.</li>
  <li><strong>Review and approval.</strong> Reviewer rounds, section comments,
  summaries, and revision — with every comment tied to the section it is about.</li>
  <li><strong>Official documents.</strong> The signed proposal is kept in
  versions; the letter of award, endorsement for approval, and extension
  agreement are released from the system, and the MOA can be generated as a
  DOCX from the same record.</li>
  <li><strong>Implementation tracking.</strong> Stage-by-stage progress,
  post-activity and terminal reports, documentation photographs, and the
  certificate of completion.</li>
  <li><strong>Accomplishment reporting.</strong> Coordinators file accomplishment
  reports, and the office requests them per quarter.</li>
  <li><strong>Legacy records.</strong> Activities that predate the system are
  imported with their own documents, so the public directory is complete.</li>
  <li><strong>Public pages.</strong> Programs, Gallery, Services, and About are
  admin-editable, and the Programs directory and Gallery fill themselves from
  the records above.</li>
  <li><strong>Accounts and roles.</strong> Faculty, staff, coordinators, the
  director, and administrators each see what their role allows, with email
  verification, one-time codes, and an idle-session timeout.</li>
</ul>
"""

GET_STARTED_BODY = """
<p>The workflow, the official templates, and the proposal workspace all live
under <a href="/proposals/">Services</a>. Accounts are issued by the Extension
Office — if you need one, or you are a partner agency with a question, write to
the address below.</p>
"""


def about_the_system(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    SitePage = apps.get_model("details", "SitePage")

    about = SitePage.objects.filter(slug="about").first()
    if about is None:
        return

    # The banner's supporting line still described the office-and-campuses page.
    about.hero_eyebrow = "About the System"
    about.hero_subheading = (
        "What NExUS is, who built it, what it runs on, and what it does for "
        "the office."
    )
    about.save(update_fields=["hero_eyebrow", "hero_subheading"])

    # Rebuild rather than patch: a fresh install and an upgraded one must end
    # up with the same page.
    PageSection.objects.filter(page_id=about.pk).delete()

    PageSection.objects.create(
        page_id=about.pk,
        layout="RICH_TEXT",
        heading="About NExUS",
        subheading="Networked Extension Unified System — the office's extension work in one system.",
        body=ABOUT_SYSTEM,
        anchor="about-nexus",
        order=1,
    )
    PageSection.objects.create(
        page_id=about.pk,
        layout="SYSTEM_PROFILE",
        heading="The system at a glance",
        subheading="Who developed it, who it was built for, and what it runs on.",
        anchor="at-a-glance",
        order=2,
    )
    PageSection.objects.create(
        page_id=about.pk,
        layout="RICH_TEXT",
        heading="What NExUS does",
        subheading="Every capability below is part of the system, not a future plan.",
        body=WHAT_IT_DOES,
        anchor="what-it-does",
        order=3,
    )
    PageSection.objects.create(
        page_id=about.pk,
        layout="CTA",
        heading="Get started",
        subheading="Sign in with your institutional account, or ask the office for one.",
        body=GET_STARTED_BODY,
        cta_label="Open Services",
        cta_url="/proposals/",
        anchor="get-started",
        order=4,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0051_alter_pagesection_layout"),
    ]

    operations = [
        migrations.RunPython(about_the_system, migrations.RunPython.noop),
    ]
