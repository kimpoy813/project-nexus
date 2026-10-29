"""Enrich the About page's narrative sections with deeper NExUS system detail."""

from django.db import migrations


ENRICHED_ABOUT_SYSTEM = """
<p><strong>NExUS</strong> — the <em>Networked Extension Unified System</em> — is
the end-to-end web platform of the <strong>ISPSC-RDEI Extension Office</strong>
at Ilocos Sur Polytechnic State College. It replaces disconnected spreadsheets,
email chains, and paper folders with one shared digital record that follows
every extension initiative from first proposal draft through field
implementation, accomplishment reporting, and public archival.</p>

<p>Developed by <strong>Kim Dave Rafael</strong> for the Extension Office,
NExUS connects faculty proponents, department and campus coordinators,
assigned evaluators, office staff, the Extension Director, and system
administrators around a single source of truth — scoped to each campus,
college, and department across the institution.</p>

<p>Because the internal workflow and the public portal read from the same
database, approved initiatives and historical legacy uploads automatically
populate the <a href="/programs/">Programs</a> directory, captioned terminal
report photographs publish directly to the <a href="/gallery/">Gallery</a>,
and workflow rules, templates, and phase shares stay transparent on
<a href="/proposals/">Services</a> and <a href="/help/">Help</a>.</p>
"""


ENRICHED_WHAT_IT_DOES = """
<ul>
  <li><strong>Proposal writing.</strong> A guided 20-step wizard for programs,
  projects, and activities across Extension Proposal and Training Design
  formats — with co-proponent collaboration, live editor presence indicators,
  autosave, downloadable Excel workbooks (Work Plan, Gantt Chart, and Funding),
  and conditional research uploads.</li>
  <li><strong>Review and approval.</strong> Structured department, campus,
  evaluator, and director review rounds with section-anchored comments,
  compiled comment summaries, and controlled revision reopening.</li>
  <li><strong>Official documents.</strong> Versioned signed proposal uploads,
  centralized Proposal Storage, office release of the Letter of Award,
  Endorsement for Approval, and Extension Agreement, plus a guided four-step
  Memorandum of Agreement (<code>.docx</code>) generator and legal-review tracker.</li>
  <li><strong>Implementation tracking.</strong> Weighted progress gauges across
  Proposal, MOA, and Implementation phases, post-activity and progress
  (terminal) reports, monitoring and evaluation, captioned photo documentation,
  and faculty completion certificates.</li>
  <li><strong>Accomplishment reporting.</strong> Office-issued quarterly
  reporting windows, coordinator submissions, and campus-by-campus tracking
  against annual institutional targets.</li>
  <li><strong>No-code administration &amp; legacy records.</strong> Browser-based
  builders for wizard steps, extension processes, document templates,
  signatories, role capabilities, and historical legacy proposal imports.</li>
  <li><strong>Public pages.</strong> Home, Services, <a href="/programs/">Programs</a>,
  <a href="/gallery/">Gallery</a>, and About are managed through the built-in
  page editor while live directories update automatically from approved records.</li>
  <li><strong>Accounts, roles, and session security.</strong> Seven institutional
  roles with email verification, password strength checks, brute-force lockout
  protection, and a 10-minute idle-session guard synchronized across tabs.</li>
</ul>
"""


ENRICHED_GET_STARTED = """
<p>Explore the three-phase extension workflow and downloadable templates on
<a href="/proposals/">Services</a>, browse step-by-step guidance and frequently
asked questions in <a href="/help/">Help</a>, or sign in through
<a href="/login/">Sign In</a>. If you represent a partner agency or need
assistance from the Extension Office, reach out through the official address
on this page.</p>
"""


def enrich_about_copy(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    SitePage = apps.get_model("details", "SitePage")

    about = SitePage.objects.filter(slug="about").first()
    if about is None:
        return

    about.hero_subheading = (
        "How NExUS unifies extension proposal authoring, multi-tier review, "
        "MOA generation, field implementation, and public transparency across ISPSC."
    )
    about.save(update_fields=["hero_subheading"])

    PageSection.objects.filter(page_id=about.pk, anchor="about-nexus").update(
        body=ENRICHED_ABOUT_SYSTEM.strip()
    )
    PageSection.objects.filter(page_id=about.pk, anchor="what-it-does").update(
        subheading="Every core capability currently running in production.",
        body=ENRICHED_WHAT_IT_DOES.strip(),
    )
    PageSection.objects.filter(page_id=about.pk, anchor="get-started").update(
        body=ENRICHED_GET_STARTED.strip(),
        cta_label="Open Services",
        cta_url="/proposals/",
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0054_clean_research_abstract_step_fields"),
    ]

    operations = [
        migrations.RunPython(enrich_about_copy, noop),
    ]
