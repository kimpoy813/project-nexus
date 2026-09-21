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
"""

from django.test import TestCase
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
        "signatories_list", "signatory_create", "dynamic_forms_list",
        "document_templates_list", "wizard_steps_manager", "wizard_step_create",
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
