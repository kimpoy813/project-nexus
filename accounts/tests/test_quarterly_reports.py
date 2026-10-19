"""
The quarterly report cycle: ask the campus, upload the file, enter the counts.

The behaviour worth locking down:

* Only Staff, Director and Admin open requests; a Campus Coordinator answers.
* A report that answers a request must carry the uploaded file.
* The counts the coordinator enters land on the campus ``Target`` rows for
  that quarter - replacing, never adding, so a correction does not
  double-count.
* Staff and Director can see the file and the figures; a coordinator cannot
  read another campus's submission.
"""

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts import permissions
from accounts.models import Profile
from details.models import (
    AccomplishmentReport,
    AccomplishmentTargetEntry,
    QuarterlyReportRequest,
    Target,
)
from details.quarterly import contributions_from_report_counts, submissions_for

from . import factories


DENIED = (302, 403)


def make_request_row(*, campus="Main Campus", year=2026, quarter="Q3", **kwargs):
    return QuarterlyReportRequest.objects.create(
        campus=campus, year=year, quarter=quarter, **kwargs
    )


def report_payload(**overrides):
    payload = {
        "title": "Q3 Accomplishment Report",
        "year": "2026",
        "quarter": "Q3",
        "campus": "Main Campus",
        "narrative": "Three barangay sessions.",
    }
    payload.update(overrides)
    return payload


class QuarterlyRequestAccessTests(TestCase):
    """Who may ask, and who may look at the answers."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("qr_admin", Profile.ROLE_ADMIN)
        cls.director = factories.make_user("qr_director", Profile.ROLE_DIRECTOR)
        cls.staff = factories.make_user("qr_staff", Profile.ROLE_STAFF)
        cls.coordinator = factories.make_user(
            "qr_campus", Profile.ROLE_CAMPUS_COORDINATOR, campus="Main Campus"
        )
        cls.other_coordinator = factories.make_user(
            "qr_campus2", Profile.ROLE_CAMPUS_COORDINATOR, campus="Satellite Campus"
        )
        cls.department_coordinator = factories.make_user(
            "qr_dept", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )
        cls.faculty = factories.make_user("qr_faculty", Profile.ROLE_FACULTY)
        cls.evaluator = factories.make_user("qr_evaluator", Profile.ROLE_EVALUATOR)

    def test_request_roles_may_open_the_request_form(self):
        for user in [self.admin, self.director, self.staff]:
            with self.subTest(role=user.profile.role, expect="allowed"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_request_create"))
                self.assertEqual(response.status_code, 200)

    def test_other_roles_are_denied_the_request_form(self):
        for user in [self.coordinator, self.department_coordinator, self.faculty, self.evaluator]:
            with self.subTest(role=user.profile.role, expect="denied"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_request_create"))
                self.assertIn(response.status_code, DENIED)

    def test_request_list_is_visible_to_requesters_and_campus_coordinators_only(self):
        for user in [self.admin, self.director, self.staff, self.coordinator]:
            with self.subTest(role=user.profile.role, expect="allowed"):
                client = factories.make_client(user)
                self.assertEqual(
                    client.get(reverse("accomplishment_requests_list")).status_code, 200
                )

        for user in [self.department_coordinator, self.faculty, self.evaluator]:
            with self.subTest(role=user.profile.role, expect="denied"):
                client = factories.make_client(user)
                response = client.get(reverse("accomplishment_requests_list"))
                self.assertIn(response.status_code, DENIED)

    def test_anonymous_users_are_sent_to_login(self):
        response = self.client.get(reverse("accomplishment_requests_list"))
        self.assertIn(response.status_code, DENIED)

    def test_a_coordinator_cannot_post_a_request(self):
        before = QuarterlyReportRequest.objects.count()
        client = factories.make_client(self.coordinator)

        client.post(
            reverse("accomplishment_request_create"),
            {"year": "2026", "quarter": "Q3", "campuses": ["Main Campus"]},
        )

        self.assertEqual(QuarterlyReportRequest.objects.count(), before)

    def test_request_predicates_agree_with_the_role_sets(self):
        cases = [
            (self.admin, True, True),
            (self.director, True, True),
            (self.staff, True, True),
            (self.coordinator, False, True),
            (self.department_coordinator, False, False),
            (self.faculty, False, False),
        ]
        for user, may_request, may_view in cases:
            with self.subTest(role=user.profile.role):
                self.assertIs(permissions.can_request_quarterly_reports(user), may_request)
                self.assertIs(permissions.can_view_quarterly_requests(user), may_view)


class QuarterlyRequestCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff, cls.client_staff = factories.staff("qc_staff")
        cls.coordinator, cls.client_coordinator = factories.campus_coordinator(
            "qc_coord", campus="Main Campus"
        )

    def test_staff_can_ask_several_campuses_in_one_go(self):
        response = self.client_staff.post(
            reverse("accomplishment_request_create"),
            {
                "year": "2026",
                "quarter": "Q3",
                "campuses": ["Main Campus", "Satellite Campus"],
                "due_date": "2026-10-31",
                "instructions": "Attach the signed activity matrix.",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('accomplishment_requests_list')}?year=2026",
        )
        rows = QuarterlyReportRequest.objects.order_by("campus")
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows[0].status, QuarterlyReportRequest.Status.OPEN)
        self.assertEqual(rows[0].due_date, date(2026, 10, 31))
        self.assertEqual(rows[0].requested_by, self.staff)
        self.assertIn("signed activity matrix", rows[0].instructions)

    def test_asking_all_campuses_expands_to_every_campus_row(self):
        from accounts.campus_data import get_campus_choices

        self.client_staff.post(
            reverse("accomplishment_request_create"),
            {"year": "2026", "quarter": "Q4", "campuses": ["ALL"]},
        )

        self.assertEqual(
            set(QuarterlyReportRequest.objects.values_list("campus", flat=True)),
            {value for value, _label in get_campus_choices()},
        )

    def test_asking_again_reopens_and_never_duplicates(self):
        existing = make_request_row(
            campus="Main Campus",
            status=QuarterlyReportRequest.Status.CLOSED,
        )

        self.client_staff.post(
            reverse("accomplishment_request_create"),
            {"year": "2026", "quarter": "Q3", "campuses": ["Main Campus"]},
        )

        self.assertEqual(QuarterlyReportRequest.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.status, QuarterlyReportRequest.Status.OPEN)

    def test_a_request_without_a_quarter_is_rejected(self):
        self.client_staff.post(
            reverse("accomplishment_request_create"),
            {"year": "2026", "quarter": "", "campuses": ["Main Campus"]},
        )

        self.assertFalse(QuarterlyReportRequest.objects.exists())

    def test_the_coordinator_only_sees_their_own_campus_requests(self):
        make_request_row(campus="Main Campus")
        make_request_row(campus="Satellite Campus")

        response = self.client_coordinator.get(reverse("accomplishment_requests_list"))

        self.assertContains(response, "Main Campus")
        self.assertNotContains(response, "Satellite Campus")

    def test_close_and_reopen_toggles_the_request(self):
        row = make_request_row(campus="Main Campus")

        self.client_staff.post(reverse("accomplishment_request_close", args=[row.pk]))
        row.refresh_from_db()
        self.assertEqual(row.status, QuarterlyReportRequest.Status.CLOSED)

        self.client_staff.post(reverse("accomplishment_request_close", args=[row.pk]))
        row.refresh_from_db()
        self.assertEqual(row.status, QuarterlyReportRequest.Status.OPEN)

    def test_a_coordinator_cannot_close_a_request(self):
        row = make_request_row(campus="Main Campus")

        self.client_coordinator.post(reverse("accomplishment_request_close", args=[row.pk]))

        row.refresh_from_db()
        self.assertEqual(row.status, QuarterlyReportRequest.Status.OPEN)

    def test_pending_requests_are_surfaced_on_the_campus_dashboard(self):
        make_request_row(campus="Main Campus", due_date=date(2026, 10, 31))
        make_request_row(campus="Satellite Campus")

        response = self.client_coordinator.get(reverse("campus_coordinator_dashboard"))

        self.assertContains(response, "awaiting your campus")
        self.assertContains(response, "3rd Quarter 2026")

    def test_an_answered_request_stops_being_surfaced(self):
        row = make_request_row(campus="Main Campus")
        AccomplishmentReport.objects.create(
            title="Filed already",
            year=2026,
            quarter="Q3",
            campus="Main Campus",
            request=row,
        )

        response = self.client_coordinator.get(reverse("campus_coordinator_dashboard"))

        self.assertNotContains(response, "awaiting your campus")


class CoordinatorSubmissionTests(TestCase):
    """The upload plus the counts that answer the campus targets."""

    @classmethod
    def setUpTestData(cls):
        cls.coordinator, cls.client_coordinator = factories.campus_coordinator(
            "cs_coord", campus="Main Campus"
        )

    def setUp(self):
        self.report_request = make_request_row(
            campus="Main Campus",
            requested_by=None,
            due_date=date(2026, 10, 31),
        )

    def test_the_form_is_prefilled_from_the_request(self):
        response = self.client_coordinator.get(
            f"{reverse('accomplishment_report_create')}?request={self.report_request.pk}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3rd Quarter 2026")
        self.assertContains(response, f'value="{self.report_request.pk}"')
        self.assertContains(response, 'border-primary/20 bg-primary/5')
        # Each figure is asked for once, as a count on the report.
        for field in ("activities_count", "beneficiaries_count", "partners_count"):
            self.assertContains(response, f'name="{field}"')
        # The old second set of target inputs is gone.
        for metric in ("programs", "participants", "partners", "technology"):
            self.assertNotContains(response, f'name="target_{metric}"')
        # The form does not restate the filing scope.
        self.assertNotContains(response, "Filing for")

    def test_submission_links_the_request_and_records_the_quarter_actuals(self):
        Target.objects.create(
            year=2026, campus="Main Campus", metric="programs", target=100
        )

        response = self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"report-bytes"),
                activities_count="25",
                beneficiaries_count="40",
                partners_count="3",
            ),
        )

        self.assertRedirects(response, reverse("accomplishment_reports_list"))
        report = AccomplishmentReport.objects.get()
        self.assertEqual(report.request_id, self.report_request.pk)
        self.assertTrue(report.attachment.name.startswith("accomplishment_reports/q3"))
        self.assertTrue(report.attachment.name.endswith(".pdf"))
        self.assertEqual(report.submitted_by, self.coordinator)

        target = Target.objects.get(metric="programs")
        self.assertEqual(target.actual_q3, 25)
        self.assertEqual(target.actual_total, 25)
        self.assertEqual(target.completion_percentage, 25)

        self.assertEqual(
            {entry.metric: entry.value for entry in report.target_entries.all()},
            {"programs": 25, "participants": 40, "partners": 3},
        )

    def test_a_target_row_is_created_when_the_campus_has_none(self):
        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="12",
            ),
        )

        target = Target.objects.get(campus="Main Campus", metric="programs")
        self.assertEqual(target.target, 0, "an unset yearly target stays 0, not the answer")
        self.assertEqual(target.actual_q3, 12)

    def test_the_file_is_required_when_answering_a_request(self):
        before = AccomplishmentReport.objects.count()

        response = self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(request=str(self.report_request.pk), activities_count="5"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attach the quarterly report file")
        self.assertEqual(AccomplishmentReport.objects.count(), before)

    def test_resubmitting_replaces_the_quarter_figure_instead_of_adding(self):
        post = lambda value: self.client_coordinator.post(  # noqa: E731
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count=str(value),
            ),
        )

        post(25)
        post(40)

        target = Target.objects.get(campus="Main Campus", metric="programs")
        self.assertEqual(target.actual_q3, 40)
        self.assertEqual(target.actual_total, 40)

    def test_a_correction_only_touches_the_quarter_it_reports(self):
        Target.objects.create(
            year=2026,
            campus="Main Campus",
            metric="programs",
            target=100,
            actual_q1=10,
            actual_q2=20,
        )

        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="30",
            ),
        )

        target = Target.objects.get(campus="Main Campus", metric="programs")
        self.assertEqual((target.actual_q1, target.actual_q2, target.actual_q3), (10, 20, 30))
        self.assertEqual(target.actual_total, 60)

    def test_blank_answers_are_not_recorded_as_zero(self):
        Target.objects.create(year=2026, campus="Main Campus", metric="programs", target=100)

        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
            ),
        )

        target = Target.objects.get(campus="Main Campus", metric="programs")
        self.assertEqual(target.actual_q3, 0)
        self.assertFalse(AccomplishmentTargetEntry.objects.exists())

    def test_a_non_numeric_answer_is_rejected_with_a_message(self):
        before = AccomplishmentReport.objects.count()

        response = self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="many",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activities Count must be a whole number")
        self.assertEqual(AccomplishmentReport.objects.count(), before)

    def test_a_coordinator_cannot_file_for_another_campus(self):
        other = make_request_row(campus="Satellite Campus")
        before = AccomplishmentReport.objects.count()

        response = self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(campus="Satellite Campus", request=str(other.pk)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Main Campus")
        self.assertEqual(AccomplishmentReport.objects.count(), before)

    def test_a_request_from_another_campus_is_ignored_not_linked(self):
        other = make_request_row(campus="Satellite Campus")

        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(other.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="5",
            ),
        )

        report = AccomplishmentReport.objects.get()
        self.assertNotEqual(
            report.request_id,
            other.pk,
            "a hand-edited request id must not mark another campus as answered",
        )

    def test_technology_transfer_is_not_touched_by_the_counts(self):
        Target.objects.create(
            year=2026,
            campus="Main Campus",
            metric="technology",
            target=10,
            actual_q3=4,
        )

        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="15",
            ),
        )

        technology = Target.objects.get(metric="technology")
        self.assertEqual(technology.actual_q3, 4)

    def test_opening_an_answered_request_prefills_the_filed_counts(self):
        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="15",
                beneficiaries_count="30",
                partners_count="2",
            ),
        )

        response = self.client_coordinator.get(
            f"{reverse('accomplishment_report_create')}?request={self.report_request.pk}"
        )

        self.assertEqual(response.context["values"]["activities_count"], "15")
        self.assertEqual(response.context["values"]["beneficiaries_count"], "30")
        self.assertEqual(response.context["values"]["partners_count"], "2")
        self.assertContains(response, 'border-gray-200 bg-white')
        self.assertNotContains(response, 'border-primary/20 bg-primary/5')

    def test_resubmission_without_previous_counts_is_not_highlighted(self):
        AccomplishmentReport.objects.create(
            title="Report without counts",
            year=2026,
            quarter="Q3",
            campus="Main Campus",
            request=self.report_request,
        )

        response = self.client_coordinator.get(
            f"{reverse('accomplishment_report_create')}?request={self.report_request.pk}"
        )

        self.assertEqual(response.context["values"]["activities_count"], "")
        self.assertContains(response, 'name="activities_count"')
        self.assertContains(response, 'border-gray-200 bg-white')
        self.assertNotContains(response, 'border-primary/20 bg-primary/5')

    def test_filing_for_a_requested_quarter_links_it_without_the_query_string(self):
        Target.objects.create(year=2026, campus="Main Campus", metric="programs", target=50)

        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                attachment=SimpleUploadedFile("q3.pdf", b"x"),
                activities_count="15",
            ),
        )

        report = AccomplishmentReport.objects.get()
        self.assertEqual(report.request_id, self.report_request.pk)
        target = Target.objects.get(campus="Main Campus", metric="programs")
        self.assertEqual(target.actual_q3, 15)
        self.assertEqual(target.actual_total, 15)
        self.assertEqual(
            list(Target.objects.values_list("metric", flat=True)), ["programs"]
        )


class DepartmentCoordinatorSubmissionTests(TestCase):
    """A department filing must not write to the campus-level tracker."""

    @classmethod
    def setUpTestData(cls):
        cls.coordinator, cls.client_coordinator = factories.department_coordinator(
            "dc_coord"
        )

    def test_the_target_inputs_are_not_offered(self):
        response = self.client_coordinator.get(reverse("accomplishment_report_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="activities_count"')
        self.assertNotContains(response, 'name="target_programs"')

    def test_posted_counts_do_not_write_to_the_campus_tracker(self):
        response = self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                campus="Main Campus",
                activities_count="99",
            ),
        )

        self.assertRedirects(response, reverse("accomplishment_reports_list"))
        self.assertFalse(Target.objects.exists())
        self.assertFalse(AccomplishmentTargetEntry.objects.exists())

    def test_an_ad_hoc_report_still_needs_no_file(self):
        response = self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(campus="Main Campus"),
        )

        self.assertRedirects(response, reverse("accomplishment_reports_list"))
        report = AccomplishmentReport.objects.get()
        self.assertFalse(report.attachment)


class StaffAndDirectorVisibilityTests(TestCase):
    """Director and Staff see the file and the answers; nobody else's do."""

    @classmethod
    def setUpTestData(cls):
        cls.staff, cls.client_staff = factories.staff("vis_staff")
        cls.director, cls.client_director = factories.director("vis_director")
        cls.coordinator, cls.client_coordinator = factories.campus_coordinator(
            "vis_coord", campus="Main Campus"
        )
        cls.other_coordinator, cls.client_other = factories.campus_coordinator(
            "vis_coord2", campus="Satellite Campus"
        )
        cls.faculty, cls.client_faculty = factories.faculty("vis_faculty")

    def setUp(self):
        self.report_request = make_request_row(campus="Main Campus")
        Target.objects.create(year=2026, campus="Main Campus", metric="programs", target=80)
        self.client_coordinator.post(
            reverse("accomplishment_report_create"),
            report_payload(
                request=str(self.report_request.pk),
                title="Main Campus Q3",
                attachment=SimpleUploadedFile("main-q3.pdf", b"bytes"),
                activities_count="20",
            ),
        )
        self.report = AccomplishmentReport.objects.get()

    def test_staff_and_director_see_the_report_and_its_answers(self):
        for client in [self.client_staff, self.client_director]:
            with self.subTest(client=client):
                response = client.get(reverse("accomplishment_reports_list"))
                self.assertContains(response, "Main Campus Q3")
                self.assertContains(response, "20")
                self.assertContains(response, "Report Requests")

    def test_the_detail_page_shows_the_file_and_the_contribution(self):
        response = self.client_director.get(
            reverse("accomplishment_report_detail", args=[self.report.pk])
        )

        stored_name = self.report.attachment.name.rsplit("/", 1)[-1]
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, stored_name)
        self.assertContains(response, "View file")
        self.assertContains(response, "Target contributions")
        self.assertContains(response, "20")

    def test_the_requests_page_shows_who_has_filed(self):
        make_request_row(campus="Satellite Campus")

        response = self.client_staff.get(
            f"{reverse('accomplishment_requests_list')}?year=2026"
        )

        self.assertContains(response, "Report filed")
        self.assertContains(response, "Awaiting report")
        self.assertContains(response, reverse("accomplishment_report_detail", args=[self.report.pk]))

    def test_another_campus_coordinator_cannot_open_the_detail_page(self):
        response = self.client_other.get(
            reverse("accomplishment_report_detail", args=[self.report.pk])
        )

        self.assertIn(response.status_code, DENIED)

    def test_faculty_cannot_open_the_detail_page(self):
        response = self.client_faculty.get(
            reverse("accomplishment_report_detail", args=[self.report.pk])
        )

        self.assertIn(response.status_code, DENIED)

    def test_the_submitter_can_open_their_own_detail_page(self):
        response = self.client_coordinator.get(
            reverse("accomplishment_report_detail", args=[self.report.pk])
        )

        self.assertEqual(response.status_code, 200)


class QuarterlyHelperTests(TestCase):
    """The parsing and matching helpers, where the edge cases live."""

    def test_all_blank_counts_mean_nothing_was_filed(self):
        self.assertEqual(contributions_from_report_counts({}), {})

    def test_only_the_answered_counts_are_filed(self):
        parsed = contributions_from_report_counts({"activities_count": "7"})

        self.assertEqual(parsed, {"programs": 7})

    def test_each_count_answers_its_target_category(self):
        parsed = contributions_from_report_counts(
            {
                "activities_count": "7",
                "beneficiaries_count": "11",
                "partners_count": "2",
            }
        )

        self.assertEqual(parsed, {"programs": 7, "participants": 11, "partners": 2})

    def test_a_deliberate_zero_is_filed(self):
        self.assertEqual(
            contributions_from_report_counts({"activities_count": "0"}),
            {"programs": 0},
        )

    def test_negative_and_non_numeric_answers_raise(self):
        for payload in [{"activities_count": "-2"}, {"activities_count": "twelve"}]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    contributions_from_report_counts(payload)

    def test_a_report_without_a_campus_matches_no_request(self):
        """submissions_for keys on campus, so a blank campus cannot answer."""
        request = make_request_row(campus="Main Campus")
        AccomplishmentReport.objects.create(
            title="No campus", year=2026, quarter="Q3", campus=""
        )

        self.assertEqual(submissions_for([request]), {})

    def test_the_newest_matching_report_is_the_submission(self):
        request = make_request_row(campus="Main Campus")
        older = AccomplishmentReport.objects.create(
            title="Older", year=2026, quarter="Q3", campus="main campus"
        )
        newer = AccomplishmentReport.objects.create(
            title="Newer", year=2026, quarter="Q3", campus="Main Campus"
        )

        self.assertEqual(submissions_for([request])[request.pk], newer)

        older.narrative = "edited later"
        older.save()

        self.assertEqual(submissions_for([request])[request.pk].pk, older.pk)
