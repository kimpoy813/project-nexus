"""Keep the About page copy concise, calm, and consistent with the other public pages."""

from django.db import migrations


SIMPLE_ABOUT_SYSTEM = """
<p><strong>NExUS</strong> — the <em>Networked Extension Unified System</em> — is
the web platform of the <strong>ISPSC-RDEI Extension Office</strong>. Instead of
separate spreadsheets and paper folders, a single proposal record carries an
extension activity from initial drafting and review through MOA preparation,
field implementation, and final reporting.</p>

<p>Approved proposals and imported historical records automatically populate the
<a href="/programs/">Programs</a> directory, while captioned photographs from
terminal reports appear in the <a href="/gallery/">Gallery</a>. Workflow rules
and official templates live on <a href="/proposals/">Services</a>, and written
guidance lives on <a href="/help/">Help</a>.</p>
"""


SIMPLE_WHAT_IT_DOES = """
<ul>
  <li><strong>Proposal writing.</strong> A guided 20-step wizard for programs,
  projects, and activities, with co-proponent collaboration, autosave, Excel
  templates, and conditional research uploads.</li>
  <li><strong>Review and approval.</strong> Department, campus, evaluator, and
  director reviews with section comments, compiled summaries, and controlled
  revisions.</li>
  <li><strong>Official documents.</strong> Versioned signed proposals, released
  award and endorsement documents, and a guided Memorandum of Agreement
  (<code>.docx</code>) generator.</li>
  <li><strong>Implementation tracking.</strong> Stage-by-stage progress across
  Proposal, MOA, and Implementation, post-activity and terminal reports, and
  photo documentation.</li>
  <li><strong>Accomplishment reporting.</strong> Quarterly reporting windows for
  coordinators tracked against annual campus targets.</li>
  <li><strong>Public pages.</strong> Home, Services, <a href="/programs/">Programs</a>,
  <a href="/gallery/">Gallery</a>, and About are editable in the admin workspace
  while public directories stay synced with real records.</li>
  <li><strong>Accounts and roles.</strong> Faculty, coordinators, evaluators,
  staff, the director, and administrators each get a scoped workspace with email
  verification and idle-session protection.</li>
</ul>
"""


SIMPLE_GET_STARTED = """
<p>Workflow stages, templates, and proposal creation live under
<a href="/proposals/">Services</a>, and common questions are answered on
<a href="/help/">Help</a>. If you need an account or have a partner inquiry,
contact the Extension Office.</p>
"""


def simplify_about_copy(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    SitePage = apps.get_model("details", "SitePage")

    about = SitePage.objects.filter(slug="about").first()
    if about is None:
        return

    about.hero_subheading = (
        "What NExUS is, who built it, and how it runs extension work across ISPSC."
    )
    about.save(update_fields=["hero_subheading"])

    PageSection.objects.filter(page_id=about.pk, anchor="about-nexus").update(
        body=SIMPLE_ABOUT_SYSTEM.strip()
    )
    PageSection.objects.filter(page_id=about.pk, anchor="what-it-does").update(
        subheading="Capabilities currently running in the system.",
        body=SIMPLE_WHAT_IT_DOES.strip(),
    )
    PageSection.objects.filter(page_id=about.pk, anchor="get-started").update(
        body=SIMPLE_GET_STARTED.strip(),
        cta_label="Open Services",
        cta_url="/proposals/",
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0055_enrich_about_page_copy"),
    ]

    operations = [
        migrations.RunPython(simplify_about_copy, noop),
    ]
