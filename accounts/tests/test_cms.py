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
        # Achievements ships with a seeded Activities block. These tests are
        # about sections the test itself creates, so start from a bare page.
        PageSection.objects.filter(page__slug="achievements").delete()

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
        home = SitePage.get_for(SitePage.Slug.HOME)
        thrust_sec = home.sections.filter(anchor="thrust").first()
        self.assertIsNotNone(thrust_sec)

        thrust_sec.subheading = "NEW-SUBTITLE-MARKER"
        thrust_sec.save()

        response = self.client.get("/")
        self.assertContains(response, "NEW-SUBTITLE-MARKER")
        self.assertNotContains(response, "Isem Ni Aran")

    def test_a_section_can_be_hidden_from_the_home_page(self):
        home = SitePage.get_for(SitePage.Slug.HOME)
        sdg_sec = home.sections.filter(anchor="sdg").first()
        self.assertIsNotNone(sdg_sec)

        sdg_sec.is_visible = False
        sdg_sec.save()

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


class HomeInlineThrustEditorTests(TestCase):
    """Each Extension Thrust card is editable inside the Content Sections block."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("inline_thrust_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("inline_thrust_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _thrust_section(self):
        return PageSection.objects.get(page__slug="home", layout=PageSection.Layout.THRUST)

    def test_the_home_editor_lists_each_thrust_inside_the_section(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["home"]))
        self.assertContains(response, "Extension Thrust")
        self.assertContains(response, "home-thrust-inline")
        self.assertContains(response, reverse("home_inline_thrust_create"))

        for thrust in HomeThrust.objects.all():
            with self.subTest(title=thrust.title):
                self.assertContains(response, thrust.title)
                self.assertContains(
                    response, reverse("home_inline_thrust_update", args=[thrust.id])
                )

    def test_the_section_edit_form_lets_you_edit_each_thrust(self):
        section = self._thrust_section()
        response = self.client_admin.get(reverse("page_section_edit", args=[section.id]))
        thrust = HomeThrust.objects.order_by("order").first()

        self.assertContains(response, "The thrust cards maintained in the Extension Thrust builder.")
        self.assertContains(response, thrust.title)
        self.assertContains(response, reverse("home_inline_thrust_update", args=[thrust.id]))

    def test_inline_update_changes_the_public_card(self):
        thrust = HomeThrust.objects.order_by("order").first()
        self.client_admin.post(
            reverse("home_inline_thrust_update", args=[thrust.id]),
            {
                "title": "INLINE-THRUST-MARKER",
                "description": "Updated from the section editor.",
                "color_class": "text-teal-600",
                "is_visible": "on",
            },
        )

        self.assertContains(self.client.get("/"), "INLINE-THRUST-MARKER")

    def test_inline_update_returns_to_the_section_editor_when_next_is_set(self):
        section = self._thrust_section()
        next_url = reverse("page_section_edit", args=[section.id])
        thrust = HomeThrust.objects.order_by("order").first()

        response = self.client_admin.post(
            reverse("home_inline_thrust_update", args=[thrust.id]),
            {
                "title": thrust.title,
                "description": thrust.description,
                "color_class": thrust.color_class,
                "is_visible": "on",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)

    def test_an_external_next_url_is_ignored(self):
        thrust = HomeThrust.objects.order_by("order").first()
        response = self.client_admin.post(
            reverse("home_inline_thrust_update", args=[thrust.id]),
            {
                "title": thrust.title,
                "description": thrust.description,
                "color_class": thrust.color_class,
                "is_visible": "on",
                "next": "https://evil.example/",
            },
        )
        self.assertRedirects(response, reverse("page_content_edit", args=["home"]))

    def test_faculty_cannot_inline_update_a_thrust(self):
        client = factories.make_client(self.faculty)
        thrust = HomeThrust.objects.order_by("order").first()
        original = thrust.title

        status = client.post(
            reverse("home_inline_thrust_update", args=[thrust.id]),
            {
                "title": "SHOULD-NOT-SAVE",
                "description": "nope",
                "color_class": "text-teal-600",
                "is_visible": "on",
            },
        ).status_code
        self.assertIn(status, DENIED)

        thrust.refresh_from_db()
        self.assertEqual(thrust.title, original)


class HomeInlineSectionEditorTests(TestCase):
    """Personnel, Activities, Processes, and Targets nest under their sections."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("inline_sec_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("inline_sec_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _section(self, layout):
        return PageSection.objects.get(page__slug="home", layout=layout)

    def test_the_home_editor_nests_each_data_layout_inside_its_section(self):
        from details.models import Activity, ActivityDate, ExtensionProcess, Personnel, Target

        person = Personnel.objects.create(name="INLINE-PERSON-MARKER", position="Staff", photo="")
        activity = Activity.objects.create(title="INLINE-ACT-MARKER", description="d")
        ActivityDate.objects.create(activity=activity, date="2026-04-01")
        process = ExtensionProcess.objects.create(title="INLINE-PROC-MARKER")
        target = Target.objects.create(
            year=2026, campus="Main Campus", metric="programs",
            planned_total=1, actual_total=0,
        )

        response = self.client_admin.get(reverse("page_content_edit", args=["home"]))
        self.assertContains(response, "home-personnel-inline")
        self.assertContains(response, "home-activities-inline")
        self.assertContains(response, "home-processes-inline")
        self.assertContains(response, "home-targets-inline")
        self.assertContains(response, "INLINE-PERSON-MARKER")
        self.assertContains(response, reverse("home_inline_personnel_update", args=[person.id]))
        self.assertContains(response, "INLINE-ACT-MARKER")
        self.assertContains(response, reverse("home_inline_activity_update", args=[activity.id]))
        self.assertContains(response, "INLINE-PROC-MARKER")
        self.assertContains(response, reverse("home_inline_process_update", args=[process.id]))
        self.assertContains(response, reverse("home_inline_target_update", args=[target.id]))
        self.assertNotContains(response, "id=\"home-inline-personnel\"")

    def test_the_section_edit_form_lets_you_edit_each_item(self):
        from details.models import Personnel

        person = Personnel.objects.create(name="SECTION-PERSON-MARKER", position="Director", photo="")
        section = self._section(PageSection.Layout.PERSONNEL)
        response = self.client_admin.get(reverse("page_section_edit", args=[section.id]))

        self.assertContains(response, "Photos, names, and positions of the extension team.")
        self.assertContains(response, "SECTION-PERSON-MARKER")
        self.assertContains(response, reverse("home_inline_personnel_update", args=[person.id]))

    def test_inline_personnel_update_returns_to_the_section_editor_when_next_is_set(self):
        from details.models import Personnel

        person = Personnel.objects.create(name="Return Person", position="Staff", photo="")
        section = self._section(PageSection.Layout.PERSONNEL)
        next_url = reverse("page_section_edit", args=[section.id])

        response = self.client_admin.post(
            reverse("home_inline_personnel_update", args=[person.id]),
            {
                "name": "RETURNED-PERSON-MARKER",
                "position": "Coordinator",
                "email": "",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)
        person.refresh_from_db()
        self.assertEqual(person.name, "RETURNED-PERSON-MARKER")
        self.assertContains(self.client.get("/"), "RETURNED-PERSON-MARKER")

    def test_inline_activity_update_returns_to_the_section_editor_when_next_is_set(self):
        from details.models import Activity, ActivityDate

        activity = Activity.objects.create(title="Old Act", description="d")
        ActivityDate.objects.create(activity=activity, date="2026-01-01")
        section = self._section(PageSection.Layout.ACTIVITIES)
        next_url = reverse("page_section_edit", args=[section.id])

        response = self.client_admin.post(
            reverse("home_inline_activity_update", args=[activity.id]),
            {
                "title": "RETURNED-ACT-MARKER",
                "description": "Updated",
                "active": "on",
                "dates[]": "2026-05-01",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)
        self.assertContains(self.client.get("/"), "RETURNED-ACT-MARKER")

    def test_inline_process_update_returns_to_the_section_editor_when_next_is_set(self):
        from details.models import ExtensionProcess, ProcessStep

        process = ExtensionProcess.objects.create(title="Old Process")
        ProcessStep.objects.create(process=process, description="Step one")
        section = self._section(PageSection.Layout.PROCESSES)
        next_url = reverse("page_section_edit", args=[section.id])

        response = self.client_admin.post(
            reverse("home_inline_process_update", args=[process.id]),
            {
                "title": "RETURNED-PROC-MARKER",
                "step_id[]": "",
                "step_description[]": "New step",
                "step_order[]": "1",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)
        self.assertContains(self.client.get("/"), "RETURNED-PROC-MARKER")

    def test_inline_target_update_returns_to_the_section_editor_when_next_is_set(self):
        from details.models import Target

        target = Target.objects.create(
            year=2026, campus="Urdaneta", metric="programs",
            planned_total=4, actual_total=1,
        )
        section = self._section(PageSection.Layout.TARGETS)
        next_url = reverse("page_section_edit", args=[section.id])

        response = self.client_admin.post(
            reverse("home_inline_target_update", args=[target.id]),
            {
                "planned_q1": "10",
                "planned_q2": "0",
                "planned_q3": "0",
                "planned_q4": "0",
                "actual_q1": "5",
                "actual_q2": "0",
                "actual_q3": "0",
                "actual_q4": "0",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)
        target.refresh_from_db()
        self.assertEqual(target.planned_q1, 10)
        self.assertEqual(target.actual_q1, 5)

    def test_an_external_next_url_is_ignored_for_personnel(self):
        from details.models import Personnel

        person = Personnel.objects.create(name="Safe Person", position="Staff", photo="")
        response = self.client_admin.post(
            reverse("home_inline_personnel_update", args=[person.id]),
            {
                "name": "Safe Person",
                "position": "Staff",
                "next": "https://evil.example/",
            },
        )
        self.assertRedirects(response, reverse("page_content_edit", args=["home"]))

    def test_faculty_cannot_inline_update_personnel(self):
        from details.models import Personnel

        client = factories.make_client(self.faculty)
        person = Personnel.objects.create(name="Keep Me", position="Staff", photo="")
        status = client.post(
            reverse("home_inline_personnel_update", args=[person.id]),
            {"name": "SHOULD-NOT-SAVE", "position": "Hacker"},
        ).status_code
        self.assertIn(status, DENIED)
        person.refresh_from_db()
        self.assertEqual(person.name, "Keep Me")


class OtherPageInlineEditorTests(TestCase):
    """The same nested CRUD is available on Services, Reports, and Achievements."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("other_page_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_reports_editor_nests_targets_inside_the_section(self):
        from details.models import Target

        target = Target.objects.create(
            year=2026, campus="Main Campus", metric="programs",
            planned_total=8, actual_total=3,
        )
        response = self.client_admin.get(reverse("page_content_edit", args=["reports"]))
        self.assertContains(response, "home-targets-inline")
        self.assertContains(response, reverse("home_inline_target_update", args=[target.id]))
        self.assertFalse(
            PageSection.objects.filter(
                page__slug="reports", layout=PageSection.Layout.TARGETS, is_visible=False
            ).exists()
        )

    def test_the_achievements_editor_nests_activities_inside_the_section(self):
        from details.models import Activity, ActivityDate

        activity = Activity.objects.create(title="PAGE-ACT-MARKER", description="d")
        ActivityDate.objects.create(activity=activity, date="2026-06-01")
        response = self.client_admin.get(reverse("page_content_edit", args=["achievements"]))
        self.assertContains(response, "home-activities-inline")
        self.assertContains(response, "PAGE-ACT-MARKER")
        self.assertContains(response, reverse("home_inline_activity_update", args=[activity.id]))

    def test_the_services_editor_nests_processes_inside_the_section(self):
        from details.models import ExtensionProcess

        process = ExtensionProcess.objects.create(title="PAGE-PROC-MARKER")
        response = self.client_admin.get(reverse("page_content_edit", args=["services"]))
        self.assertContains(response, "home-processes-inline")
        self.assertContains(response, "PAGE-PROC-MARKER")
        self.assertContains(response, reverse("home_inline_process_update", args=[process.id]))
        # The block is what publishes processes now: the page no longer paints
        # its own accordion, so this section is visible rather than a hidden
        # editor-only row.
        self.assertTrue(
            PageSection.objects.get(
                page__slug="services", layout=PageSection.Layout.PROCESSES
            ).is_visible
        )
        # Every builder is reachable from the block itself, so the separate
        # "Linked Data" list is gone.
        self.assertNotContains(response, "Linked Data on This Page")
        self.assertContains(response, reverse("processes_list"))

    def test_inline_target_update_returns_to_the_reports_editor_when_next_is_set(self):
        from details.models import Target

        target = Target.objects.create(
            year=2026, campus="Sta. Maria", metric="partners",
            planned_total=2, actual_total=1,
        )
        next_url = reverse("page_content_edit", args=["reports"])
        response = self.client_admin.post(
            reverse("home_inline_target_update", args=[target.id]),
            {
                "planned_q1": "3",
                "planned_q2": "0",
                "planned_q3": "0",
                "planned_q4": "0",
                "actual_q1": "1",
                "actual_q2": "0",
                "actual_q3": "0",
                "actual_q4": "0",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)
        target.refresh_from_db()
        self.assertEqual(target.planned_q1, 3)


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
        """Put ``layout`` on ``slug`` as that page's only block.

        Pages now ship with seeded blocks, so the page is cleared first and
        these tests assert what the block under test renders, not what the
        seed happens to contain.
        """
        PageSection.objects.filter(page__slug=slug).delete()
        return self._append_block(slug, layout, **overrides)

    def _append_block(self, slug, layout, **overrides):
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

    def test_a_data_block_needs_no_heading_of_its_own(self):
        """A block renders its builder's data, so blank copy is not an empty section.

        Requiring a heading here is what made a populated block look invalid.
        Text sections still need a heading or a body - see
        ``test_a_section_with_no_heading_and_no_body_is_rejected``.
        """
        PageSection.objects.filter(page__slug="reports").delete()
        before = PageSection.objects.count()
        self._append_block("reports", "ACTIVITIES", heading="", body="")

        self.assertEqual(PageSection.objects.count(), before + 1)
        self.assertTrue(
            PageSection.objects.filter(
                page__slug="reports", layout=PageSection.Layout.ACTIVITIES
            ).exists()
        )


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

    def test_the_page_editor_has_direct_link_to_live_page(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["reports"]))
        self.assertContains(response, "View live page")
        self.assertNotContains(response, "Live Preview")
        self.assertNotContains(response, "nx-page-preview")

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
