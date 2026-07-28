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
        self.assertEqual(HomeThrust.objects.count(), 14)
        self.assertEqual(
            HomeThrust.objects.order_by("order").first().title,
            "Indigenous Heritage Protection",
        )

    def test_isem_ni_aran_is_seeded_as_the_thrust_subtitle(self):
        thrust = HomeSectionHeading.objects.get(section="thrust")
        self.assertEqual(thrust.subtitle, "Isem Ni Aran")
        self.assertEqual(thrust.caption, "Approved BR No. 95-1517, S. 2022")

    def test_all_six_home_sections_are_seeded(self):
        self.assertEqual(HomeSectionHeading.objects.count(), 6)

    def test_workflow_phases_are_seeded_with_their_weights(self):
        weights = dict(WorkflowPhase.objects.values_list("key", "weight_percent"))
        self.assertEqual(weights, {"proposal": 40, "moa": 20, "implementation": 40})


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
        self.assertContains(response, "Indigenous Heritage Protection")


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

    def test_the_progress_weight_drives_the_bar_width(self):
        phase = WorkflowPhase.objects.get(key="proposal")
        self.client_admin.post(
            reverse("workflow_phases_manager"),
            self._payload(**{f"phase_{phase.id}_weight_percent": "55"}),
        )

        self.assertContains(self.client.get("/proposals/"), "width: 55%")

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
