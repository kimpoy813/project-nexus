"""
Tests for the admin-managed public content:

  * SitePage / PageSection  - Home, Services, Reports, Achievements
  * HomeSectionHeading      - built-in Home section titles ("Isem Ni Aran")
  * HomeThrust              - the Extension Thrust cards
  * WorkflowPhase           - Proposal / MOA / Implementation cards

Each area is checked end to end: an admin saves a change, and the public page
reflects it.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from details.models import (
    HomeSectionHeading,
    HomeThrust,
    PageSection,
    SitePage,
    WorkflowPhase,
)

from . import factories


DENIED = (302, 403)


class SeedDataTests(TestCase):
    """Migrations seed the previously hardcoded copy verbatim."""

    def test_all_four_editable_pages_exist(self):
        slugs = set(SitePage.objects.values_list("slug", flat=True))
        self.assertEqual(slugs, {"home", "services", "reports", "achievements"})

    def test_home_thrust_cards_are_seeded(self):
        self.assertEqual(HomeThrust.objects.count(), 8)
        self.assertEqual(
            HomeThrust.objects.order_by("order").first().title,
            "Sustainable Community Development and Livelihood Enhancement",
        )

    def test_isem_ni_aran_is_seeded_as_the_thrust_subtitle(self):
        thrust = HomeSectionHeading.objects.get(section="thrust")
        self.assertEqual(thrust.subtitle, "Isem Ni Aran")
        self.assertEqual(thrust.caption, "Approved BR No. 95-1517, S. 2022")

    def test_all_six_home_sections_are_seeded(self):
        self.assertEqual(HomeSectionHeading.objects.count(), 6)

    def test_workflow_phases_are_seeded_with_their_weights(self):
        weights = dict(WorkflowPhase.objects.values_list("key", "weight_percent"))
        self.assertEqual(weights, {"proposal": 50, "moa": 20, "implementation": 30})

    def test_the_seeded_weights_add_up_to_a_whole(self):
        """The rings on the Services page are shares of one 100% total."""
        self.assertEqual(sum(WorkflowPhase.weight_map().values()), 100)


class PublicPageTests(TestCase):
    """The four public pages render, including the two that used to 404."""

    def test_every_public_page_returns_200(self):
        for url in ["/", "/reports/", "/achievements/", "/proposals/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_reports_and_achievements_are_routed(self):
        """Regression guard: these were linked in the navbar but had no routes."""
        self.assertEqual(self.client.get(reverse("reports_page")).status_code, 200)
        self.assertEqual(self.client.get(reverse("achievements_page")).status_code, 200)

    def test_home_renders_the_seeded_thrust_cards(self):
        response = self.client.get("/")
        self.assertContains(response, "Isem Ni Aran")
        self.assertContains(response, "Sustainable Community Development and Livelihood Enhancement")


class PageContentEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("cms_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("cms_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_non_admins_cannot_open_the_editor(self):
        client = factories.make_client(self.faculty)
        self.assertIn(client.get(reverse("page_content_list")).status_code, DENIED)

    def test_editing_the_hero_updates_the_public_page(self):
        self.client_admin.post(
            reverse("page_content_edit", args=["reports"]),
            {
                "title": "Reports",
                "hero_eyebrow": "EYEBROW-MARKER",
                "hero_heading": "HEADING-MARKER",
                "hero_subheading": "SUBHEADING-MARKER",
                "is_published": "on",
            },
        )

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "EYEBROW-MARKER")
        self.assertContains(response, "HEADING-MARKER")
        self.assertContains(response, "SUBHEADING-MARKER")

    def test_hero_text_is_escaped(self):
        self.client_admin.post(
            reverse("page_content_edit", args=["reports"]),
            {"title": "Reports", "hero_heading": "<script>alert(1)</script>", "is_published": "on"},
        )

        response = self.client.get(reverse("reports_page"))
        self.assertNotContains(response, "<script>alert(1)</script>", html=False)
        self.assertContains(response, "&lt;script&gt;")

    def test_unpublished_pages_are_hidden_from_visitors_but_visible_to_admins(self):
        self.client_admin.post(
            reverse("page_content_edit", args=["achievements"]),
            {"title": "Achievements", "hero_heading": "Draft"},  # no is_published
        )

        self.assertEqual(self.client.get(reverse("achievements_page")).status_code, 404)

        admin_response = self.client_admin.get(reverse("achievements_page"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "Draft preview")

    def test_unknown_page_slug_returns_404(self):
        self.assertEqual(
            self.client_admin.get(reverse("page_content_edit", args=["nonsense"])).status_code,
            404,
        )


class PageSectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("sec_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _create(self, **overrides):
        payload = {
            "heading": "Section One",
            "subheading": "",
            "body": "<p>Body text</p>",
            "layout": "RICH_TEXT",
            "anchor": "",
            "is_visible": "on",
        }
        payload.update(overrides)
        return self.client_admin.post(
            reverse("page_section_create", args=["achievements"]), payload
        )

    def test_a_section_can_be_created_and_appears_publicly(self):
        self._create(heading="SECTION-MARKER", body="<p>Hello <strong>world</strong></p>")

        response = self.client.get(reverse("achievements_page"))
        self.assertContains(response, "SECTION-MARKER")
        self.assertContains(response, "<strong>world</strong>", html=False)

    def test_a_free_text_anchor_is_slugified_rather_than_rejected(self):
        """Regression: 'Our Impact' used to fail SlugField validation silently."""
        self._create(heading="Anchored", anchor="Our Impact")

        section = PageSection.objects.get(heading="Anchored")
        self.assertEqual(section.anchor, "our-impact")

    def test_a_section_with_no_heading_and_no_body_is_rejected(self):
        before = PageSection.objects.count()
        response = self._create(heading="", body="")

        self.assertEqual(PageSection.objects.count(), before)
        self.assertContains(response, "Add a heading or some content")

    def test_hidden_sections_do_not_appear_publicly(self):
        self._create(heading="HIDDEN-MARKER")
        section = PageSection.objects.get(heading="HIDDEN-MARKER")

        self.client_admin.post(
            reverse("page_section_edit", args=[section.id]),
            {"heading": "HIDDEN-MARKER", "body": "<p>x</p>", "layout": "RICH_TEXT"},
        )

        self.assertNotContains(self.client.get(reverse("achievements_page")), "HIDDEN-MARKER")

    def test_sections_can_be_reordered(self):
        self._create(heading="First")
        self._create(heading="Second")

        second = PageSection.objects.get(heading="Second")
        self.client_admin.post(
            reverse("page_section_move", args=[second.id]), {"direction": "up"}
        )

        order = list(
            PageSection.objects.filter(page__slug="achievements")
            .order_by("order", "id")
            .values_list("heading", flat=True)
        )
        self.assertEqual(order, ["Second", "First"])

    def test_moving_the_first_section_up_is_a_no_op(self):
        self._create(heading="First")
        self._create(heading="Second")

        first = PageSection.objects.get(heading="First")
        self.client_admin.post(
            reverse("page_section_move", args=[first.id]), {"direction": "up"}
        )

        order = list(
            PageSection.objects.filter(page__slug="achievements")
            .order_by("order", "id")
            .values_list("heading", flat=True)
        )
        self.assertEqual(order, ["First", "Second"])

    def test_deleting_a_section_requires_post(self):
        self._create(heading="Doomed")
        section = PageSection.objects.get(heading="Doomed")

        self.assertEqual(
            self.client_admin.get(reverse("page_section_delete", args=[section.id])).status_code,
            405,
        )
        self.assertTrue(PageSection.objects.filter(pk=section.pk).exists())

    def test_deleting_a_section_works_via_post(self):
        self._create(heading="Doomed")
        section = PageSection.objects.get(heading="Doomed")

        self.client_admin.post(reverse("page_section_delete", args=[section.id]))
        self.assertFalse(PageSection.objects.filter(pk=section.pk).exists())


class HomeSectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("home_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _heading_payload(self, **overrides):
        payload = {}
        for row in HomeSectionHeading.objects.all():
            prefix = f"section_{row.section}"
            payload[f"{prefix}_heading"] = row.heading
            payload[f"{prefix}_subtitle"] = row.subtitle
            payload[f"{prefix}_caption"] = row.caption
            payload[f"{prefix}_nav_label"] = row.nav_label
            payload[f"{prefix}_is_visible"] = "on"
        payload.update(overrides)
        return payload

    def test_isem_ni_aran_can_be_changed_by_an_admin(self):
        self.client_admin.post(
            reverse("home_sections_manager"),
            self._heading_payload(section_thrust_subtitle="NEW-SUBTITLE-MARKER"),
        )

        response = self.client.get("/")
        self.assertContains(response, "NEW-SUBTITLE-MARKER")
        self.assertNotContains(response, "Isem Ni Aran")

    def test_a_section_can_be_hidden_from_the_home_page(self):
        payload = self._heading_payload()
        payload.pop("section_sdg_is_visible")

        self.client_admin.post(reverse("home_sections_manager"), payload)

        response = self.client.get("/")
        self.assertNotContains(response, "Sustainable Development Goals")
        self.assertNotContains(response, 'href="#sdg"')

    def test_a_thrust_card_can_be_added(self):
        self.client_admin.post(
            reverse("home_thrust_create"),
            {
                "title": "NEW-THRUST-MARKER",
                "description": "Description",
                "color_class": "text-teal-600",
                "is_visible": "on",
            },
        )

        self.assertContains(self.client.get("/"), "NEW-THRUST-MARKER")

    def test_an_invalid_colour_class_falls_back_to_the_default(self):
        """Colour lands in a class attribute, so only the allow-list is accepted."""
        self.client_admin.post(
            reverse("home_thrust_create"),
            {"title": "Coloured", "color_class": "bg-red-500 injected", "is_visible": "on"},
        )

        thrust = HomeThrust.objects.get(title="Coloured")
        self.assertEqual(thrust.color_class, "text-green-600")

    def test_a_thrust_card_with_no_title_is_rejected(self):
        before = HomeThrust.objects.count()
        self.client_admin.post(
            reverse("home_thrust_create"), {"title": "", "color_class": "text-teal-600"}
        )
        self.assertEqual(HomeThrust.objects.count(), before)

    def test_hidden_thrust_cards_are_not_shown(self):
        thrust = HomeThrust.objects.order_by("order").first()
        self.client_admin.post(
            reverse("home_thrust_edit", args=[thrust.id]),
            {"title": thrust.title, "color_class": thrust.color_class},  # no is_visible
        )

        self.assertNotContains(self.client.get("/"), thrust.title)

    def test_thrust_cards_can_be_reordered(self):
        original = list(HomeThrust.objects.order_by("order").values_list("title", flat=True))
        second = HomeThrust.objects.order_by("order")[1]

        self.client_admin.post(
            reverse("home_thrust_move", args=[second.id]), {"direction": "up"}
        )

        reordered = list(HomeThrust.objects.order_by("order").values_list("title", flat=True))
        self.assertEqual(reordered[0], original[1])
        self.assertEqual(reordered[1], original[0])


class WorkflowPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("wf_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("wf_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _payload(self, **overrides):
        payload = {}
        for phase in WorkflowPhase.objects.all():
            prefix = f"phase_{phase.id}"
            payload[f"{prefix}_label"] = phase.label
            payload[f"{prefix}_summary"] = phase.summary
            payload[f"{prefix}_weight_label"] = phase.weight_label
            payload[f"{prefix}_weight_percent"] = phase.weight_percent
            payload[f"{prefix}_is_visible"] = "on"
        payload.update(overrides)
        return payload

    def test_non_admins_cannot_open_the_manager(self):
        client = factories.make_client(self.faculty)
        self.assertIn(client.get(reverse("workflow_phases_manager")).status_code, DENIED)

    def test_a_phase_label_can_be_changed(self):
        phase = WorkflowPhase.objects.get(key="proposal")
        self.client_admin.post(
            reverse("workflow_phases_manager"),
            self._payload(**{f"phase_{phase.id}_label": "PHASE-LABEL-MARKER"}),
        )

        self.assertContains(self.client.get("/proposals/"), "PHASE-LABEL-MARKER")

    def test_the_progress_weight_drives_the_ring(self):
        phase = WorkflowPhase.objects.get(key="proposal")
        self.client_admin.post(
            reverse("workflow_phases_manager"),
            self._payload(**{f"phase_{phase.id}_weight_percent": "55"}),
        )

        self.assertContains(self.client.get("/proposals/"), "--nx-ring-pct: 55")

    def test_the_services_page_represents_weights_as_rings(self):
        """Regression guard: the phase percentages used to be flat bars."""
        response = self.client.get("/proposals/")

        for phase in WorkflowPhase.objects.order_by("order"):
            with self.subTest(phase=phase.key):
                self.assertContains(
                    response,
                    f'aria-label="{phase.label}: {phase.weight_percent}% of overall progress"',
                )

        self.assertNotContains(response, "services-status-bar")
        self.assertContains(response, "total 100% of overall progress")

    def test_an_out_of_range_weight_is_clamped(self):
        phase = WorkflowPhase.objects.get(key="proposal")
        self.client_admin.post(
            reverse("workflow_phases_manager"),
            self._payload(**{f"phase_{phase.id}_weight_percent": "999"}),
        )

        phase.refresh_from_db()
        self.assertEqual(phase.weight_percent, 100)

    def test_a_non_numeric_weight_leaves_the_previous_value(self):
        phase = WorkflowPhase.objects.get(key="proposal")
        original = phase.weight_percent

        self.client_admin.post(
            reverse("workflow_phases_manager"),
            self._payload(**{f"phase_{phase.id}_weight_percent": "not-a-number"}),
        )

        phase.refresh_from_db()
        self.assertEqual(phase.weight_percent, original)

    def test_a_hidden_phase_disappears_from_the_services_page(self):
        phase = WorkflowPhase.objects.get(key="moa")
        payload = self._payload(**{f"phase_{phase.id}_label": "HIDDEN-PHASE-MARKER"})
        payload.pop(f"phase_{phase.id}_is_visible")

        self.client_admin.post(reverse("workflow_phases_manager"), payload)

        self.assertNotContains(self.client.get("/proposals/"), "HIDDEN-PHASE-MARKER")

    def test_status_flows_still_render_from_the_model(self):
        """Presentation is editable; the underlying statuses stay in code."""
        response = self.client.get("/proposals/")
        self.assertContains(response, "Draft")


class MissingMediaTests(TestCase):
    """The public site must look intentional on a fresh install.

    Uploaded media is no longer committed, so a new deployment starts with no
    files on disk. Personnel rows may still exist (restored from a database
    dump) while their photos do not — that combination previously rendered a
    broken image icon.
    """

    def test_the_home_page_renders_with_no_personnel_at_all(self):
        from details.models import Personnel

        Personnel.objects.all().delete()
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_a_personnel_row_without_a_photo_renders_initials(self):
        from details.models import Personnel

        Personnel.objects.all().delete()
        Personnel.objects.create(name="Maria Santos", position="Coordinator", photo="")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maria Santos")
        self.assertNotContains(response, "<img src=\"\"", html=False)

    def test_several_photoless_personnel_all_render(self):
        from details.models import Personnel

        Personnel.objects.all().delete()
        for name in ["Ana Cruz", "Ben Reyes", "Carla Lim"]:
            Personnel.objects.create(name=name, position="Staff", photo="")

        response = self.client.get("/")
        for name in ["Ana Cruz", "Ben Reyes", "Carla Lim"]:
            with self.subTest(name=name):
                self.assertContains(response, name)

    def test_the_home_page_renders_with_no_activities(self):
        from details.models import Activity

        Activity.objects.all().delete()
        self.assertEqual(self.client.get("/").status_code, 200)


class PageBlockTests(TestCase):
    """Data-driven section blocks render live data from the system's models."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("block_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _add_block(self, slug, layout, **overrides):
        payload = {
            "heading": "Block Heading",
            "subheading": "",
            "body": "",
            "layout": layout,
            "anchor": "",
            "is_visible": "on",
        }
        payload.update(overrides)
        return self.client_admin.post(reverse("page_section_create", args=[slug]), payload)

    def test_activities_block_renders_activities_on_a_public_page(self):
        from details.models import Activity, ActivityDate

        activity = Activity.objects.create(
            title="BLOCK-ACTIVITY-MARKER", description="A community programme."
        )
        ActivityDate.objects.create(activity=activity, date="2026-08-15")

        self._add_block("reports", "ACTIVITIES")

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "BLOCK-ACTIVITY-MARKER")

    def test_activities_block_respects_limit_count(self):
        from details.models import Activity, ActivityDate

        # Newest first: FIRST, then SECOND, then THIRD.
        for name, date in [
            ("FIRST-ACT", "2026-03-01"),
            ("SECOND-ACT", "2026-02-01"),
            ("THIRD-ACT", "2026-01-01"),
        ]:
            activity = Activity.objects.create(title=name, description="d")
            ActivityDate.objects.create(activity=activity, date=date)

        self._add_block("reports", "ACTIVITIES", limit_count="2")

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "FIRST-ACT")
        self.assertContains(response, "SECOND-ACT")
        self.assertNotContains(response, "THIRD-ACT")

    def test_activities_block_shows_an_empty_state(self):
        self._add_block("reports", "ACTIVITIES")

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "No activities to show yet.")

    def test_targets_block_defaults_to_the_latest_year_with_data(self):
        from details.models import Target

        Target.objects.create(
            year=2025, campus="Main Campus", metric="programs",
            planned_total=10, actual_total=9,
        )
        Target.objects.create(
            year=2026, campus="Main Campus", metric="programs",
            planned_total=20, actual_total=11,
        )

        self._add_block("reports", "TARGETS")

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "2026 targets")
        self.assertContains(response, "Planned: 20")
        self.assertNotContains(response, "Planned: 10")

    def test_targets_block_respects_target_year(self):
        from details.models import Target

        Target.objects.create(
            year=2025, campus="Main Campus", metric="programs",
            planned_total=10, actual_total=9,
        )
        Target.objects.create(
            year=2026, campus="Main Campus", metric="programs",
            planned_total=20, actual_total=11,
        )

        self._add_block("reports", "TARGETS", target_year="2025")

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "2025 targets")
        self.assertContains(response, "Planned: 10")
        self.assertNotContains(response, "Planned: 20")

    def test_targets_block_shows_progress_percentages(self):
        from details.models import Target

        Target.objects.create(
            year=2026, campus="Main Campus", metric="participants",
            planned_total=200, actual_total=50,
        )

        self._add_block("reports", "TARGETS")

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, "25%")

    def test_processes_block_renders_steps(self):
        from details.models import ExtensionProcess, ProcessStep

        process = ExtensionProcess.objects.create(title="BLOCK-PROCESS-MARKER")
        ProcessStep.objects.create(process=process, description="BLOCK-STEP-MARKER")

        self._add_block("services", "PROCESSES")

        response = self.client.get(reverse("services_home"))
        self.assertContains(response, "BLOCK-PROCESS-MARKER")
        self.assertContains(response, "BLOCK-STEP-MARKER")

    def test_templates_block_renders_only_active_templates(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from details.models import DocumentTemplate

        upload = SimpleUploadedFile("form.docx", b"fake docx bytes")
        DocumentTemplate.objects.create(
            title="BLOCK-TEMPLATE-MARKER", file=upload, is_active=True
        )
        DocumentTemplate.objects.create(
            title="HIDDEN-TEMPLATE-MARKER", file=upload, is_active=False
        )

        self._add_block("services", "TEMPLATES")

        response = self.client.get(reverse("services_home"))
        self.assertContains(response, "BLOCK-TEMPLATE-MARKER")
        self.assertNotContains(response, "HIDDEN-TEMPLATE-MARKER")

    def test_personnel_block_renders_persons(self):
        from details.models import Personnel

        Personnel.objects.create(name="Rosa Villanueva", position="Director")

        self._add_block("achievements", "PERSONNEL")

        response = self.client.get(reverse("achievements_page"))
        self.assertContains(response, "Rosa Villanueva")
        self.assertContains(response, "Director")

    def test_cta_block_renders_its_button(self):
        self._add_block(
            "reports", "CTA",
            heading="Ready to start?",
            cta_label="Start a proposal",
            cta_url="/proposals/",
        )

        response = self.client.get(reverse("reports_page"))
        self.assertContains(response, 'href="/proposals/"')
        self.assertContains(response, "Start a proposal")

    def test_cta_url_must_be_a_site_path_or_https_url(self):
        self._add_block(
            "reports", "CTA",
            heading="Bad CTA",
            cta_label="Click",
            cta_url="javascript:alert(1)",
        )

        self.assertFalse(PageSection.objects.filter(heading="Bad CTA").exists())
        self.assertNotContains(
            self.client.get(reverse("reports_page")), "javascript:alert(1)", html=False
        )

    def test_a_data_block_with_no_heading_is_rejected(self):
        before = PageSection.objects.count()
        self._add_block("reports", "ACTIVITIES", heading="", body="")

        self.assertEqual(PageSection.objects.count(), before)


class PageContentLogTests(TestCase):
    """Every hero/section edit is recorded with before and after values."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("log_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("log_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_editing_the_hero_writes_an_audit_log(self):
        self.client_admin.post(
            reverse("page_content_edit", args=["reports"]),
            {
                "title": "Reports",
                "hero_heading": "OLD-HEADING",
                "is_published": "on",
            },
        )
        self.client_admin.post(
            reverse("page_content_edit", args=["reports"]),
            {
                "title": "Reports",
                "hero_heading": "NEW-HEADING",
                "is_published": "on",
            },
        )

        from details.models import PageContentLog

        log = PageContentLog.objects.filter(
            action=PageContentLog.Action.UPDATE_PAGE, page_slug="reports"
        ).latest("created_at", "id")
        self.assertEqual(log.before["hero_heading"], "OLD-HEADING")
        self.assertEqual(log.after["hero_heading"], "NEW-HEADING")
        self.assertEqual(log.changed_by, self.admin)

    def test_the_section_lifecycle_is_logged(self):
        from details.models import PageContentLog

        self.client_admin.post(
            reverse("page_section_create", args=["achievements"]),
            {"heading": "Lifecycle", "body": "<p>v1</p>", "layout": "RICH_TEXT"},
        )
        # A second section so the move has a neighbour to swap with.
        self.client_admin.post(
            reverse("page_section_create", args=["achievements"]),
            {"heading": "Lifecycle-Second", "body": "<p>x</p>", "layout": "RICH_TEXT"},
        )
        section = PageSection.objects.get(heading="Lifecycle")

        self.client_admin.post(
            reverse("page_section_edit", args=[section.id]),
            {"heading": "Lifecycle", "body": "<p>v2</p>", "layout": "RICH_TEXT"},
        )
        self.client_admin.post(
            reverse("page_section_move", args=[section.id]), {"direction": "down"}
        )
        self.client_admin.post(reverse("page_section_delete", args=[section.id]))

        actions = list(
            PageContentLog.objects.filter(page_slug="achievements")
            .order_by("created_at", "id")
            .values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [
                PageContentLog.Action.ADD_SECTION,
                PageContentLog.Action.ADD_SECTION,  # the helper section
                PageContentLog.Action.EDIT_SECTION,
                PageContentLog.Action.MOVE_SECTION,
                PageContentLog.Action.DELETE_SECTION,
            ],
        )

        edit_log = PageContentLog.objects.get(action=PageContentLog.Action.EDIT_SECTION)
        self.assertIn("v1", edit_log.before["body"])
        self.assertIn("v2", edit_log.after["body"])

        delete_log = PageContentLog.objects.get(action=PageContentLog.Action.DELETE_SECTION)
        self.assertEqual(delete_log.before["heading"], "Lifecycle")
        self.assertEqual(delete_log.after, {})

    def test_the_logs_view_requires_admin(self):
        client = factories.make_client(self.faculty)
        self.assertIn(
            client.get(reverse("page_content_logs")).status_code, DENIED
        )

    def test_the_logs_view_filters_by_page(self):
        self.client_admin.post(
            reverse("page_section_create", args=["reports"]),
            {"heading": "On-Reports", "body": "<p>x</p>", "layout": "RICH_TEXT"},
        )
        self.client_admin.post(
            reverse("page_section_create", args=["achievements"]),
            {"heading": "On-Achievements", "body": "<p>x</p>", "layout": "RICH_TEXT"},
        )

        response = self.client_admin.get(
            reverse("page_content_logs"), {"page": "reports"}
        )
        self.assertContains(response, "On-Reports")
        self.assertNotContains(response, "On-Achievements")

    def test_the_logs_view_shows_before_and_after(self):
        self.client_admin.post(
            reverse("page_content_edit", args=["reports"]),
            {"title": "Reports", "hero_heading": "OLD-VALUE", "is_published": "on"},
        )

        response = self.client_admin.get(reverse("page_content_logs"))
        self.assertContains(response, "OLD-VALUE")
        self.assertContains(response, "Before")
        self.assertContains(response, "After")


class PagePreviewTests(TestCase):
    """Admins can preview sections before they touch the public page."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("preview_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_page_editor_embeds_a_live_preview(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["reports"]))
        self.assertContains(response, "Live Preview")
        self.assertContains(response, "nx-page-preview")

    def test_the_section_form_previews_data_blocks(self):
        from details.models import Activity, ActivityDate

        activity = Activity.objects.create(
            title="PREVIEW-ACTIVITY-MARKER", description="d"
        )
        ActivityDate.objects.create(activity=activity, date="2026-09-01")

        response = self.client_admin.get(
            reverse("page_section_create", args=["reports"]),
            {"layout": "ACTIVITIES", "heading": "Latest"},
        )
        self.assertContains(response, "Preview")
        self.assertContains(response, "PREVIEW-ACTIVITY-MARKER")
