"""
Permission tests: who may reach what.

These are the highest-value tests in the suite. Permission logic is
security-relevant, spread across several modules, and the kind of thing that
regresses silently — a role quietly gaining access looks identical to a
working page until someone notices.

Each test asserts the *response*, not just a helper's return value, so a view
that forgets to call the helper still fails.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.views import (
    ACCOMPLISHMENT_SUBMIT_ROLES,
    ACCOMPLISHMENT_VIEW_ONLY_ROLES,
    can_access_accomplishment_reports,
    can_submit_accomplishment_reports,
    user_has_capability,
)
from details.models import AccomplishmentReport, RoleCapability

from . import factories


DENIED = (302, 403)


class AccomplishmentReportPermissionTests(TestCase):
    """Coordinators submit; Staff and Director view only; Admin is excluded."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("p_admin", Profile.ROLE_ADMIN)
        cls.director = factories.make_user("p_director", Profile.ROLE_DIRECTOR)
        cls.staff = factories.make_user("p_staff", Profile.ROLE_STAFF)
        cls.faculty = factories.make_user("p_faculty", Profile.ROLE_FACULTY)
        cls.evaluator = factories.make_user("p_evaluator", Profile.ROLE_EVALUATOR)
        cls.dept = factories.make_user(
            "p_dept", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )
        cls.campus = factories.make_user(
            "p_campus", Profile.ROLE_CAMPUS_COORDINATOR, campus="Main Campus"
        )

    # ---- submitting -----------------------------------------------------

    def test_only_coordinators_may_open_the_submit_form(self):
        allowed = [self.dept, self.campus]
        denied = [self.staff, self.director, self.admin, self.faculty, self.evaluator]

        for user in allowed:
            with self.subTest(role=user.profile.role, expect="allowed"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_report_create"))
                self.assertEqual(response.status_code, 200)

        for user in denied:
            with self.subTest(role=user.profile.role, expect="denied"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_report_create"))
                self.assertIn(response.status_code, DENIED)

    def test_denied_roles_cannot_create_a_report_by_posting_directly(self):
        """Hiding the button is not enough; the POST must be rejected too."""
        payload = {
            "title": "Should not be created",
            "year": "2026",
            "quarter": AccomplishmentReport.Quarter.Q1,
        }

        for user in [self.staff, self.director, self.admin, self.faculty]:
            with self.subTest(role=user.profile.role):
                before = AccomplishmentReport.objects.count()
                client = factories.make_client(user)
                client.post(reverse("accomplishment_report_create"), payload)
                self.assertEqual(AccomplishmentReport.objects.count(), before)

    def test_coordinator_can_actually_create_a_report(self):
        client = factories.make_client(self.dept)
        before = AccomplishmentReport.objects.count()

        client.post(
            reverse("accomplishment_report_create"),
            {
                "title": "Q1 Community Outreach",
                "year": "2026",
                "quarter": AccomplishmentReport.Quarter.Q1,
                "narrative": "Ran three barangay sessions.",
            },
        )

        self.assertEqual(AccomplishmentReport.objects.count(), before + 1)

    # ---- viewing --------------------------------------------------------

    def test_view_access_covers_coordinators_staff_and_director_only(self):
        allowed = [self.dept, self.campus, self.staff, self.director]
        denied = [self.admin, self.faculty, self.evaluator]

        for user in allowed:
            with self.subTest(role=user.profile.role, expect="allowed"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_reports_list"))
                self.assertEqual(response.status_code, 200)

        for user in denied:
            with self.subTest(role=user.profile.role, expect="denied"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_reports_list"))
                self.assertIn(response.status_code, DENIED)

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("accomplishment_reports_list"))
        self.assertIn(response.status_code, DENIED)

    def test_submit_button_is_hidden_from_view_only_roles(self):
        coordinator = factories.make_client(self.dept)
        self.assertContains(coordinator.get(reverse("accomplishment_reports_list")), "Submit Report")

        for user in [self.staff, self.director]:
            with self.subTest(role=user.profile.role):
                client = factories.make_client(user)
                self.assertNotContains(
                    client.get(reverse("accomplishment_reports_list")), "Submit Report"
                )

    # ---- scoping --------------------------------------------------------

    def test_coordinators_only_see_reports_from_their_own_scope(self):
        AccomplishmentReport.objects.create(
            title="CS department report",
            year=2026,
            quarter=AccomplishmentReport.Quarter.Q1,
            department="Computer Science",
        )
        AccomplishmentReport.objects.create(
            title="Nursing department report",
            year=2026,
            quarter=AccomplishmentReport.Quarter.Q1,
            department="Nursing",
        )

        client = factories.make_client(self.dept)
        response = client.get(reverse("accomplishment_reports_list"))

        self.assertContains(response, "CS department report")
        self.assertNotContains(response, "Nursing department report")

    def test_staff_and_director_see_reports_from_every_scope(self):
        AccomplishmentReport.objects.create(
            title="CS department report",
            year=2026,
            quarter=AccomplishmentReport.Quarter.Q1,
            department="Computer Science",
        )
        AccomplishmentReport.objects.create(
            title="Nursing department report",
            year=2026,
            quarter=AccomplishmentReport.Quarter.Q1,
            department="Nursing",
        )

        for user in [self.staff, self.director]:
            with self.subTest(role=user.profile.role):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_reports_list"))
                self.assertContains(response, "CS department report")
                self.assertContains(response, "Nursing department report")

    # ---- helpers --------------------------------------------------------

    def test_permission_helpers_agree_with_the_role_constants(self):
        cases = [
            (self.dept, True, True),
            (self.campus, True, True),
            (self.staff, False, True),
            (self.director, False, True),
            (self.admin, False, False),
            (self.faculty, False, False),
        ]
        for user, may_submit, may_view in cases:
            with self.subTest(role=user.profile.role):
                self.assertIs(can_submit_accomplishment_reports(user), may_submit)
                self.assertIs(can_access_accomplishment_reports(user), may_view)

    def test_admin_is_not_granted_the_submit_capability_implicitly(self):
        """Admin implies every other capability but deliberately not this one."""
        capability = RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT

        self.assertFalse(user_has_capability(self.admin, capability))
        self.assertTrue(user_has_capability(self.dept, capability))

        # Regression guard: Admin must keep its other capabilities.
        self.assertTrue(
            user_has_capability(self.admin, RoleCapability.Capability.VIEW_ANALYTICS)
        )

    def test_role_constants_do_not_overlap(self):
        self.assertFalse(ACCOMPLISHMENT_SUBMIT_ROLES & ACCOMPLISHMENT_VIEW_ONLY_ROLES)
        self.assertNotIn(Profile.ROLE_ADMIN, ACCOMPLISHMENT_SUBMIT_ROLES)
        self.assertNotIn(Profile.ROLE_ADMIN, ACCOMPLISHMENT_VIEW_ONLY_ROLES)


class AdminOnlyAreaTests(TestCase):
    """Every admin-only URL must reject non-admins."""

    ADMIN_URLS = [
        "admin_dashboard",
        "admin_create_account",
        "page_content_list",
        "home_sections_manager",
        "workflow_phases_manager",
        "personnel_list",
        "activities_list",
        "processes_list",
        "targets_list",
        "signatories_list",
        "document_templates_list",
        "proposal_templates_list",
        "wizard_steps_manager",
        "role_capabilities_manager",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("a_admin", Profile.ROLE_ADMIN)
        cls.non_admins = [
            factories.make_user("a_director", Profile.ROLE_DIRECTOR),
            factories.make_user("a_staff", Profile.ROLE_STAFF),
            factories.make_user("a_faculty", Profile.ROLE_FACULTY),
            factories.make_user("a_evaluator", Profile.ROLE_EVALUATOR),
        ]

    def test_admin_can_reach_every_admin_url(self):
        client = factories.make_client(self.admin)
        for name in self.ADMIN_URLS:
            with self.subTest(url=name):
                self.assertEqual(client.get(reverse(name)).status_code, 200)

    def test_non_admins_are_denied_every_admin_url(self):
        for user in self.non_admins:
            client = factories.make_client(user)
            for name in self.ADMIN_URLS:
                with self.subTest(role=user.profile.role, url=name):
                    self.assertIn(client.get(reverse(name)).status_code, DENIED)

    def test_anonymous_users_are_denied_every_admin_url(self):
        for name in self.ADMIN_URLS:
            with self.subTest(url=name):
                self.assertIn(self.client.get(reverse(name)).status_code, DENIED)


class DashboardAccessTests(TestCase):
    """Each role dashboard renders for its own role."""

    DASHBOARDS = {
        Profile.ROLE_ADMIN: "admin_dashboard",
        Profile.ROLE_DIRECTOR: "director_dashboard",
        Profile.ROLE_STAFF: "staff_dashboard",
        Profile.ROLE_EVALUATOR: "evaluator_dashboard",
        Profile.ROLE_FACULTY: "faculty_dashboard",
        Profile.ROLE_DEPARTMENT_COORDINATOR: "department_coordinator_dashboard",
        Profile.ROLE_CAMPUS_COORDINATOR: "campus_coordinator_dashboard",
    }

    def test_every_role_can_load_its_own_dashboard(self):
        for role, url_name in self.DASHBOARDS.items():
            with self.subTest(role=role):
                user = factories.make_user(f"d_{role.lower()}", role)
                client = factories.make_client(user)
                self.assertEqual(client.get(reverse(url_name)).status_code, 200)

    def test_dashboard_redirect_sends_each_role_somewhere_valid(self):
        for role in self.DASHBOARDS:
            with self.subTest(role=role):
                user = factories.make_user(f"r_{role.lower()}", role)
                client = factories.make_client(user)
                response = client.get(reverse("dashboard_redirect"))
                self.assertIn(response.status_code, (200, 302))

    def test_anonymous_users_cannot_reach_dashboards(self):
        for url_name in self.DASHBOARDS.values():
            with self.subTest(url=url_name):
                self.assertIn(self.client.get(reverse(url_name)).status_code, DENIED)
