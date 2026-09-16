"""
Regression tests for the system's dynamic parts.

The recurring failure mode these guard against: a dropdown that is supposed to
populate from admin-managed data (Campus / College / Department tables)
instead drawing from a stale or unrelated source — a hardcoded template list,
an import-time choices snapshot, or user profiles — leaving it empty even
though the admin side has data.
"""

import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import Campus, College, Department, Profile, Signatory
from accounts.tests import factories


class CampusCascadeAjaxTests(TestCase):
    """The /ajax/colleges/ and /ajax/departments/ endpoints the cascading
    dropdowns on register/profile/admin forms depend on."""

    @classmethod
    def setUpTestData(cls):
        # Campuses created *after* module import: proves choices are resolved
        # live from the database rather than frozen at server boot.
        cls.campus = Campus.objects.create(name="Ajax Campus")
        cls.college = College.objects.create(campus=cls.campus, name="Ajax College of Science")
        College.objects.create(campus=cls.campus, name="Ajax College of Arts")
        cls.dept = Department.objects.create(
            campus=cls.campus, college=cls.college, name="Ajax Computer Department"
        )
        Department.objects.create(campus=cls.campus, college=None, name="Ajax Direct Department")

    def test_colleges_ajax_returns_db_colleges_for_campus(self):
        response = self.client.get(reverse("get_colleges_ajax"), {"campus": "Ajax Campus"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        names = [c["value"] for c in payload["colleges"]]
        self.assertIn("Ajax College of Science", names)
        self.assertIn("Ajax College of Arts", names)

    def test_colleges_ajax_scopes_to_requested_campus(self):
        other = Campus.objects.create(name="Other Campus")
        College.objects.create(campus=other, name="Other College")
        response = self.client.get(reverse("get_colleges_ajax"), {"campus": "Ajax Campus"})
        names = [c["value"] for c in response.json()["colleges"]]
        self.assertNotIn("Other College", names)

    def test_departments_ajax_filters_by_campus_and_college(self):
        response = self.client.get(
            reverse("get_departments_ajax"),
            {"campus": "Ajax Campus", "college": "Ajax College of Science"},
        )
        names = [d["value"] for d in response.json()["departments"]]
        self.assertIn("Ajax Computer Department", names)
        self.assertNotIn("Ajax Direct Department", names)

    def test_departments_ajax_without_college_returns_college_less_departments(self):
        response = self.client.get(
            reverse("get_departments_ajax"), {"campus": "Ajax Campus", "college": ""}
        )
        names = [d["value"] for d in response.json()["departments"]]
        self.assertIn("Ajax Direct Department", names)
        self.assertNotIn("Ajax Computer Department", names)

    def test_unknown_campus_returns_empty_lists(self):
        response = self.client.get(reverse("get_colleges_ajax"), {"campus": "Nowhere"})
        self.assertEqual(response.json(), {"colleges": []})
        response = self.client.get(
            reverse("get_departments_ajax"), {"campus": "Nowhere", "college": ""}
        )
        self.assertEqual(response.json(), {"departments": []})


class LazyCampusChoicesTests(TestCase):
    """Profile.campus / Signatory.campus choices must be evaluated lazily.

    Both models call full_clean() in admin flows, and their campus choices
    used to be frozen at import time — a campus created in the admin
    dashboard after the server booted was rejected as "not a valid choice".
    """

    def test_profile_full_clean_accepts_campus_created_after_boot(self):
        campus = Campus.objects.create(name="Fresh Campus")
        user = factories.make_user("lazy_profile_user")
        profile = user.profile
        profile.campus = campus.name
        profile.full_clean()  # must not raise

    def test_signatory_full_clean_accepts_campus_created_after_boot(self):
        campus = Campus.objects.create(name="Fresh Campus")
        college = College.objects.create(campus=campus, name="Fresh College")
        signatory = Signatory(
            position_title=Signatory.Position.DEAN,
            campus=campus.name,
            college=college.name,
            full_name="Juan Dela Cruz",
        )
        signatory.full_clean()  # must not raise

    def test_signatory_create_view_accepts_new_campus(self):
        """"The dashboard form itself (which runs full_clean) must succeed."""
        campus = Campus.objects.create(name="Fresh Campus")
        College.objects.create(campus=campus, name="Fresh College")
        _, client = factories.admin("sig_admin")
        response = client.post(
            reverse("signatory_create"),
            {
                "position_title": Signatory.Position.DEAN,
                "campus": campus.name,
                "college": "Fresh College",
                "department": "",
                "full_name": "Juan Dela Cruz",
                "credentials": "Ph.D",
            },
        )
        self.assertRedirects(response, reverse("signatories_list"))
        self.assertTrue(
            Signatory.objects.filter(campus=campus.name, full_name="Juan Dela Cruz").exists()
        )


class TargetFormCampusChoicesTests(TestCase):
    """The Targets form used to build its campus list from user profiles —
    empty on a fresh install even when the admin had campuses set up."""

    def test_target_create_lists_campuses_from_campus_table(self):
        # No user profile has a campus set; the old code returned nothing.
        Campus.objects.get_or_create(name="Main")
        Campus.objects.create(name="Brand New Campus")
        _, client = factories.admin("target_admin")
        response = client.get(reverse("target_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Brand New Campus")
        self.assertContains(response, "Main")

    def test_target_create_still_lists_static_fallback_when_table_empty(self):
        Campus.objects.all().delete()
        _, client = factories.admin("target_admin2")
        response = client.get(reverse("target_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Main")  # static fallback campus


class AdminEditUserCampusChoicesTests(TestCase):
    """The admin user-edit form used to hardcode seven campus options in the
    template, so admin-created campuses never appeared and a saved campus
    missing from the list was silently replaced by the first option."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user, cls.client_admin = factories.admin("edit_admin")
        cls.campus = Campus.objects.create(name="Newly Created Campus")

    def test_edit_user_lists_db_campuses(self):
        target = factories.make_user("edit_target", campus="Newly Created Campus")
        response = self.client_admin.get(reverse("admin_edit_user", args=[target.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newly Created Campus")

    def test_edit_user_keeps_legacy_saved_campus_selectable(self):
        target = factories.make_user("legacy_target", campus="Deprecated Campus")
        response = self.client_admin.get(reverse("admin_edit_user", args=[target.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deprecated Campus")

    def test_edit_user_page_uses_cascade_endpoints(self):
        target = factories.make_user("cascade_target", campus="Newly Created Campus")
        response = self.client_admin.get(reverse("admin_edit_user", args=[target.pk]))
        self.assertContains(response, reverse("get_colleges_ajax"))
        self.assertContains(response, reverse("get_departments_ajax"))

    def test_edit_user_save_preserves_campus(self):
        target = factories.make_user("save_target", campus="Newly Created Campus")
        response = self.client_admin.post(
            reverse("admin_edit_user", args=[target.pk]),
            {
                "username": "save_target",
                "email": "save_target@example.com",
                "campus": "Newly Created Campus",
                "college": "",
                "department": "",
                "role": Profile.ROLE_FACULTY,
                "full_name": "Save Target",
            },
        )
        self.assertRedirects(response, reverse("admin_dashboard"))
        target.profile.refresh_from_db()
        self.assertEqual(target.profile.campus, "Newly Created Campus")


class AccomplishmentReportFormCascadeTests(TestCase):
    """The report form's campus/college/department used to be free-text
    inputs; they must now be selects driven by the AJAX cascade."""

    @classmethod
    def setUpTestData(cls):
        cls.campus = Campus.objects.create(name="Report Campus")
        cls.submitter, cls.client_sub = factories.department_coordinator("report_coord")

    def test_form_renders_cascading_selects(self):
        response = self.client_sub.get(reverse("accomplishment_report_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_campus"')
        self.assertContains(response, 'id="id_college"')
        self.assertContains(response, 'id="id_department"')
        self.assertContains(response, reverse("get_colleges_ajax"))
        self.assertContains(response, reverse("get_departments_ajax"))

    def test_form_lists_db_campuses(self):
        response = self.client_sub.get(reverse("accomplishment_report_create"))
        self.assertContains(response, "Report Campus")

    def test_submit_uses_selected_campus(self):
        response = self.client_sub.post(
            reverse("accomplishment_report_create"),
            {
                "title": "Q1 Report",
                "year": "2026",
                "quarter": "Q1",
                "campus": "Report Campus",
                "college": "",
                "department": "",
                "narrative": "Nothing to report.",
            },
        )
        self.assertRedirects(response, reverse("accomplishment_reports_list"))
        from details.models import AccomplishmentReport

        report = AccomplishmentReport.objects.get(title="Q1 Report")
        self.assertEqual(report.campus, "Report Campus")
