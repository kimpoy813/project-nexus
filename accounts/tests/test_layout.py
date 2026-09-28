"""
Layout smoke tests.

The system used to float every screen in a centred, fixed-width column
(``max-w-2xl … max-w-7xl mx-auto``). It now uses a fluid full-width layout
driven by ``static/css/nexus-layout.css``: ``.nx-page`` for page bodies,
``.nx-bar`` for the navbar and footer, ``.nx-dash__inner`` for dashboards, and
``.nx-auth`` for the split sign-in screens.

These tests render the real pages through their views, so a template that
regresses to a capped container — or stops rendering at all — fails here
instead of in a browser.

They also pin the fixed-navbar offset: the navbar is ``fixed top-0`` and
``<main class="nexus-shell">`` carries its height as top padding, which is the
only thing keeping a page's first row out from under the header.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Profile
from proposals.models import Proposal

from . import factories


#: Capped, centred containers that must not come back as page shells.
CAPPED_CONTAINERS = (
    "max-w-7xl mx-auto",
    "max-w-6xl mx-auto",
    "max-w-5xl mx-auto",
    "max-w-4xl mx-auto",
    "max-w-3xl mx-auto",
    "max-w-2xl mx-auto",
    "mx-auto max-w-7xl",
    "mx-auto max-w-6xl",
    "mx-auto max-w-5xl",
)


class FluidContainerAssertions:
    """Shared helpers: a page must render, span the viewport, and stay clean."""

    def assertFluidPage(self, response, *, fluid_marker="nx-page"):
        markers = (fluid_marker,) if isinstance(fluid_marker, str) else tuple(fluid_marker)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertTrue(
            any(marker in html for marker in markers),
            f"page uses none of the fluid containers {markers}",
        )
        self.assertIn("css/nexus-layout.css", html, "layout stylesheet is not linked")
        for capped in CAPPED_CONTAINERS:
            self.assertNotIn(capped, html, f"page still uses a capped container: {capped}")
        return html


class PublicPageLayoutTests(FluidContainerAssertions, TestCase):
    """Anonymous pages: home, services, reports, achievements."""

    def test_public_pages_use_the_fluid_container(self):
        urls = ("/", reverse("services_home"), reverse("reports_page"), reverse("achievements_page"))
        for url in urls:
            with self.subTest(url=url):
                self.assertFluidPage(self.client.get(url))

    def test_navbar_and_footer_share_the_page_gutter(self):
        html = self.assertFluidPage(self.client.get("/"))
        self.assertIn("nx-bar", html)


class AuthScreenLayoutTests(FluidContainerAssertions, TestCase):
    """Sign-in screens fill the width via the split brand panel."""

    PAGES = ("login", "register", "password_reset")

    #: The sign-in and sign-up screens sit lower than the password-reset ones,
    #: which already carried their own top offset. The offset lives on each
    #: page's own section instead of ``.nx-auth``, so the screens that share
    #: that class are left alone.
    LOWERED_SECTIONS = {
        "login": '<section class="pb-16 pt-16">',
        "register": '<section class="bg-gray-50 pt-16 pb-10">',
    }

    def test_auth_pages_render_the_split_layout(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                html = self.assertFluidPage(self.client.get(reverse(name)), fluid_marker="nx-auth")
                self.assertIn("nx-auth__panel", html)
                self.assertIn("nx-auth__form", html)

    def test_login_and_register_sit_lower_on_the_page(self):
        for name, section in self.LOWERED_SECTIONS.items():
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                self.assertIn(section, html)


class DashboardLayoutTests(FluidContainerAssertions, TestCase):
    """Every role dashboard spans the viewport."""

    DASHBOARDS = {
        Profile.ROLE_ADMIN: "admin_dashboard",
        Profile.ROLE_DIRECTOR: "director_dashboard",
        Profile.ROLE_STAFF: "staff_dashboard",
        Profile.ROLE_EVALUATOR: "evaluator_dashboard",
        Profile.ROLE_FACULTY: "faculty_dashboard",
        Profile.ROLE_DEPARTMENT_COORDINATOR: "department_coordinator_dashboard",
        Profile.ROLE_CAMPUS_COORDINATOR: "campus_coordinator_dashboard",
    }

    def test_role_dashboards_span_the_viewport(self):
        for index, (role, url_name) in enumerate(self.DASHBOARDS.items()):
            with self.subTest(role=role):
                user = factories.make_user(f"layout_dash_{index}", role, department="Computer Science",
                                           campus="Main Campus")
                client = factories.make_client(user)
                self.assertFluidPage(
                    client.get(reverse(url_name)),
                    fluid_marker=("nx-page", "nx-dash__inner"),
                )


class AdminScreenLayoutTests(FluidContainerAssertions, TestCase):
    """Admin lists, managers and CRUD forms use the fluid container."""

    PAGES = (
        "campuses_list", "campus_create", "colleges_list", "college_create",
        "departments_list", "department_create", "personnel_list", "processes_list",
        "activities_list", "activity_create", "targets_list", "target_create",
        "signatories_list", "signatory_create",
        "document_templates_list", "proposal_templates_list",
        "wizard_steps_manager", "wizard_step_create",
        "workflow_phases_manager", "home_sections_manager", "role_capabilities_manager",
        "admin_create_account",
    )

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("layout_admin", Profile.ROLE_ADMIN)

    def test_admin_pages_use_the_fluid_container(self):
        client = factories.make_client(self.admin)
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertFluidPage(client.get(reverse(name)))

    def test_admin_edit_user_form_uses_the_fluid_container(self):
        client = factories.make_client(self.admin)
        target = factories.make_user("layout_target", Profile.ROLE_FACULTY)
        self.assertFluidPage(client.get(reverse("admin_edit_user", args=[target.id])))

    def test_profile_screens_use_the_fluid_container(self):
        user = factories.make_user("layout_profile", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        for name in ("profile_view", "profile_edit"):
            with self.subTest(page=name):
                self.assertFluidPage(client.get(reverse(name)))


class CoordinatorAndWorkflowLayoutTests(FluidContainerAssertions, TestCase):
    """Accomplishment reports, the wizard and the proposal trackers."""

    @classmethod
    def setUpTestData(cls):
        cls.coordinator = factories.make_user(
            "layout_coord", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )
        cls.author = factories.make_user("layout_author", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.author)

    def test_accomplishment_report_screens_use_the_fluid_container(self):
        client = factories.make_client(self.coordinator)
        for name in ("accomplishment_reports_list", "accomplishment_report_create"):
            with self.subTest(page=name):
                self.assertFluidPage(client.get(reverse(name)))

    def test_wizard_step_uses_the_fluid_shell(self):
        client = factories.make_client(self.author)
        url = reverse("proposal_wizard", args=[self.proposal.id, 1])
        html = self.assertFluidPage(client.get(url), fluid_marker="nexus-wizard-layout")
        self.assertNotIn("lg:grid-cols-12", html, "wizard still uses the old 12-column grid")

    def test_proposal_trackers_use_the_fluid_container(self):
        client = factories.make_client(self.author)
        pages = {
            "proposal_moa_tracker": reverse("proposal_moa_tracker", args=[self.proposal.id]),
            "proposal_implementation_tracker": reverse(
                "proposal_implementation_tracker", args=[self.proposal.id]
            ),
            "proposal_storage": reverse("proposal_storage", args=[self.proposal.id]),
            "proposal_upload_signed_proposal": reverse(
                "proposal_upload_signed_proposal", args=[self.proposal.id]
            ),
        }
        reachable = 0
        for name, url in pages.items():
            with self.subTest(page=name):
                response = client.get(url)
                if response.status_code != 200:
                    # Some trackers need a later lifecycle state; they are
                    # covered by the workflow suite, not here.
                    continue
                reachable += 1
                self.assertFluidPage(response)
        self.assertGreater(reachable, 0, "no tracker page rendered for this proposal")


class HeaderOffsetTests(SimpleTestCase):
    """Content must start *below* the fixed navbar on every screen.

    The navbar is ``position: fixed``, so the page shell carries its height as
    top padding. Losing ``nexus-shell`` from ``<main>`` — or the padding from
    the class — slides the first row of every page under the header. That is
    most obvious on a proposal wizard step, where the step heading and the
    Office Instructions card disappear behind the bar, but it is a site-wide
    regression, so it is pinned here rather than in one template.
    """

    BASE_TEMPLATE = settings.BASE_DIR / "templates" / "base.html"
    STYLESHEET = settings.BASE_DIR / "static" / "css" / "nexus-ui.css"

    def _stylesheet(self):
        return self.STYLESHEET.read_text(encoding="utf-8")

    def _shell_rule(self, css, *, inside_mobile_breakpoint=False):
        """The declarations of the ``.nexus-shell`` rule.

        ``inside_mobile_breakpoint`` selects the copy inside
        ``@media (max-width: 768px)`` so a mobile-only override cannot hide a
        missing desktop offset.
        """
        blocks = [css]
        if inside_mobile_breakpoint:
            match = re.search(r"@media \(max-width: 768px\) \{(.*?)\n\}", css, re.S)
            self.assertIsNotNone(match, "the mobile refinement block disappeared")
            blocks = [match.group(1)]
        for block in blocks:
            rule = re.search(r"\.nexus-shell\s*\{([^}]*)\}", block)
            if rule:
                return rule.group(1)
        return ""

    def test_base_template_offsets_main_below_the_navbar(self):
        html = self.BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('<main id="main-content" class="nexus-shell">', html)
        # The stray attribute this replaced (`<main id="main-content" ">`)
        # dropped the offset silently; make sure it cannot come back.
        self.assertNotIn('<main id="main-content" ">', html)

    def test_the_shell_padding_follows_the_navbar_height(self):
        css = self._stylesheet()
        self.assertRegex(css, r"--nx-header-h:\s*5rem;", "desktop navbar height is not declared")
        self.assertRegex(css, r"\.nexus-navbar\s*\{[^}]*height:\s*var\(--nx-header-h\)",
                         "the navbar no longer sizes itself from --nx-header-h")
        self.assertIn("padding-top: var(--nx-header-h)", self._shell_rule(css),
                      ".nexus-shell must pad the page clear of the fixed navbar")

    def test_the_offset_survives_the_mobile_breakpoint(self):
        """The bar shrinks to 4.5rem on phones; the offset must shrink with it."""
        css = self._stylesheet()
        mobile = re.search(r"@media \(max-width: 768px\) \{(.*?)\n\}", css, re.S)
        self.assertIsNotNone(mobile, "the mobile refinement block disappeared")
        self.assertRegex(mobile.group(1), r"--nx-header-h:\s*4\.5rem;")
        self.assertNotIn("padding-top", self._shell_rule(css, inside_mobile_breakpoint=True),
                         "a mobile-only padding override hides the shared offset")


class RenderedHeaderOffsetTests(TestCase):
    """A rendered page ships both halves of the offset: class + stylesheet.

    ``TestCase`` rather than ``SimpleTestCase`` because the public pages read
    the site configuration and CMS content from the database.
    """

    def test_pages_keep_the_offset_when_rendered(self):
        for url in ("/", reverse("login")):
            with self.subTest(page=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('<main id="main-content" class="nexus-shell">', html)
                self.assertIn("css/nexus-ui.css", html, "the shell stylesheet is not linked")

    def test_the_wizard_step_clears_the_header(self):
        """The report came from here: a proposal wizard step under the header."""
        author = factories.make_user("layout_offset_author", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=author)
        client = factories.make_client(author)
        for step in (1, 2):
            with self.subTest(step=step):
                response = client.get(reverse("proposal_wizard", args=[proposal.id, step]))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('<main id="main-content" class="nexus-shell">', html)
                self.assertIn("nexus-wizard-layout", html)


#: Templates that are complete documents in their own right: they render no
#: navbar, so they need no offset. Everything else must go through base.html.
#: Matched against the end of the path, so they stay app-relative.
STANDALONE_TEMPLATES = (
    "templates/maintenance.html",                    # 503 interstitial
    "templates/500.html",                            # must render even when DB/context processors fail
    "accounts/templates/debug_login.html",           # local debug helper
    "accounts/email/password_reset_email.html",      # e-mail bodies
    "accounts/email/verification_email.html",
)


def is_standalone(path):
    relative = path.relative_to(Path(settings.BASE_DIR)).as_posix()
    return relative.endswith(STANDALONE_TEMPLATES)


def _template_files():
    root = Path(settings.BASE_DIR)
    dirs = [root / "templates"]
    dirs += sorted(app for app in root.glob("*") if (app / "templates").is_dir())
    for app in dirs:
        yield from (app / "templates" if app.name != "templates" else app).rglob("*.html")


def _without_django_comments(text):
    return re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", text, flags=re.S)


class NavbarOffsetSourceTests(SimpleTestCase):
    """Only base.html may paint the fixed navbar.

    The navbar is ``fixed top-0`` and lives in exactly one template, so the
    ``.nexus-shell`` offset on ``<main>`` covers the whole site. A second
    navbar — or a page that bypasses the shell — would render under the header
    again, and no per-page padding would catch it.
    """

    def test_base_html_is_the_only_template_that_renders_the_navbar(self):
        offenders = []
        for path in _template_files():
            relative = path.relative_to(Path(settings.BASE_DIR)).as_posix()
            if "node_modules" in relative or relative.endswith("templates/base.html"):
                continue
            markup = _without_django_comments(path.read_text(encoding="utf-8"))
            if 'class="nexus-navbar' in markup:
                offenders.append(relative)
        self.assertEqual(offenders, [], "these templates paint their own fixed navbar")

    def test_standalone_documents_really_have_no_navbar(self):
        """The exemption list must not grow into a way to skip the offset."""
        for relative in STANDALONE_TEMPLATES:
            matches = [p for p in _template_files()
                       if p.relative_to(Path(settings.BASE_DIR)).as_posix().endswith(relative)]
            with self.subTest(template=relative):
                self.assertTrue(matches, f"{relative} no longer exists")
                markup = _without_django_comments(matches[0].read_text(encoding="utf-8"))
                self.assertNotIn('class="nexus-navbar', markup)
                self.assertNotIn('class="nexus-shell', markup,
                                 "a standalone document must not rely on the shell")

    def test_every_page_template_reaches_the_shell(self):
        """A page is either a partial, standalone, or extends the shell."""
        orphaned = []
        for path in _template_files():
            relative = path.relative_to(Path(settings.BASE_DIR)).as_posix()
            if "node_modules" in relative or relative.endswith("templates/base.html"):
                continue
            if is_standalone(path):
                continue
            markup = path.read_text(encoding="utf-8")
            if "{% extends" in markup or "{# partial" in markup:
                continue
            # Includes/partials never open a <body>; a template that does is a
            # page, and a page that is not extending base.html has no offset.
            if "<body" in markup.lower():
                orphaned.append(relative)
        self.assertEqual(orphaned, [], "these page templates bypass the shell in base.html")


class SiteWideHeaderOffsetTests(TestCase):
    """Every page family renders clear of the fixed navbar.

    The regression this pins was site-wide: ``<main>`` lost ``nexus-shell``, so
    the first row of *every* screen slid under the header. The proposal wizard
    step was simply where it was reported. These render one page per family —
    public, auth, all seven dashboards, profile, the wizard steps, MOA,
    implementation, storage, review, accomplishment reports and the admin
    screens — and a full URLconf sweep of every route is what originally
    verified the fix (205 distinct pages).
    """

    SHELL = '<main id="main-content" class="nexus-shell">'

    def assertClearsTheHeader(self, client, url, *, where=None):
        # `follow` because a few lifecycle screens redirect when the proposal is
        # not in the right state yet; the page that finally paints is the one
        # that has to clear the header.
        response = client.get(url, follow=True)
        label = where or url
        self.assertEqual(response.status_code, 200, f"{label} did not render")
        html = response.content.decode()
        self.assertIn(self.SHELL, html, f"{label} renders without the header offset")
        self.assertIn("css/nexus-ui.css", html, f"{label} does not link the shell stylesheet")
        return html

    def test_public_and_auth_pages_clear_the_header(self):
        for url in ("/", reverse("services_home"), reverse("reports_page"),
                    reverse("achievements_page"), reverse("login"),
                    reverse("register"), reverse("password_reset")):
            with self.subTest(page=url):
                self.assertClearsTheHeader(self.client, url)

    def test_every_role_dashboard_clears_the_header(self):
        dashboards = {
            Profile.ROLE_ADMIN: "admin_dashboard",
            Profile.ROLE_DIRECTOR: "director_dashboard",
            Profile.ROLE_STAFF: "staff_dashboard",
            Profile.ROLE_EVALUATOR: "evaluator_dashboard",
            Profile.ROLE_FACULTY: "faculty_dashboard",
            Profile.ROLE_DEPARTMENT_COORDINATOR: "department_coordinator_dashboard",
            Profile.ROLE_CAMPUS_COORDINATOR: "campus_coordinator_dashboard",
        }
        for index, (role, url_name) in enumerate(dashboards.items()):
            with self.subTest(role=role):
                user = factories.make_user(f"offset_dash_{index}", role)
                self.assertClearsTheHeader(
                    factories.make_client(user), reverse(url_name), where=f"{role} dashboard"
                )

    def test_every_proposal_wizard_step_clears_the_header(self):
        """The reported screen: all of them, not just the first."""
        author = factories.make_user("offset_wizard", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=author)
        client = factories.make_client(author)
        checked = 0
        for step in range(1, 21):
            url = reverse("proposal_wizard", args=[proposal.id, step])
            response = client.get(url)
            if response.status_code != 200:
                continue  # gated by an earlier step; covered by the workflow suite
            checked += 1
            with self.subTest(step=step):
                self.assertClearsTheHeader(client, url, where=f"wizard step {step}")
        self.assertGreater(checked, 0, "no wizard step rendered")

    def test_proposal_lifecycle_screens_clear_the_header(self):
        author = factories.make_user("offset_flow", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=author)
        client = factories.make_client(author)
        pages = {
            "proposal_create": reverse("proposal_create"),
            "proposal_moa_tracker": reverse("proposal_moa_tracker", args=[proposal.id]),
            "proposal_moa_draft": reverse("proposal_moa_draft", args=[proposal.id]),
            "proposal_implementation_tracker": reverse(
                "proposal_implementation_tracker", args=[proposal.id]
            ),
            "proposal_storage": reverse("proposal_storage", args=[proposal.id]),
            "proposal_upload_signed_proposal": reverse(
                "proposal_upload_signed_proposal", args=[proposal.id]
            ),
        }
        for name, url in pages.items():
            with self.subTest(page=name):
                self.assertClearsTheHeader(client, url, where=name)

    def test_profile_and_accomplishment_screens_clear_the_header(self):
        user = factories.make_user("offset_profile", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        for name in ("profile_view", "profile_edit"):
            with self.subTest(page=name):
                self.assertClearsTheHeader(client, reverse(name), where=name)

        coordinator = factories.make_user(
            "offset_coord", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )
        coord_client = factories.make_client(coordinator)
        for name in ("accomplishment_reports_list", "accomplishment_report_create"):
            with self.subTest(page=name):
                self.assertClearsTheHeader(coord_client, reverse(name), where=name)

    def test_admin_screens_clear_the_header(self):
        admin_user = factories.make_user("offset_admin", Profile.ROLE_ADMIN)
        client = factories.make_client(admin_user)
        for name in ("wizard_steps_manager", "wizard_step_create", "workflow_phases_manager",
                     "campuses_list", "campus_create", "signatories_list",
                     "document_templates_list", "role_capabilities_manager",
                     "admin_create_account", "activities_list"):
            with self.subTest(page=name):
                self.assertClearsTheHeader(client, reverse(name), where=name)
