"""
Tests for the content-source registry and the drag-and-drop page composer.

Four things are pinned here:

  * **The registry is complete.** A source that is declared but whose template
    or manager does not exist is exactly the failure that left the SDG section
    rendering nothing — so every source is checked end to end.
  * **Dropping a builder onto a page publishes its data.** The block shows the
    builder's rows, not a copy of them.
  * **Reordering is drag-and-drop**, for sections and for the items inside a
    source, and both refuse a payload that does not match what is stored.
  * **The canvas rows collapse and drag as a whole**, with the block palette in
    a rail on the right of the content — so a long page of blocks stays compact,
    rearrangeable by grabbing any row, and a tile only travels a short hop into
    the list it feeds.
"""

import json
from html.parser import HTMLParser

from django.template.loader import get_template
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import Profile
from details.content_sources import (
    CONTENT_SOURCES,
    all_content_sources,
    get_content_source,
    orderable_source,
    resolve_order_model,
)
from details.models import (
    ExtensionProcess,
    HomeThrust,
    PageSection,
    SitePage,
    SustainableDevelopmentGoal,
    resolve_section_data,
)

from . import factories


DENIED = (302, 403)

#: Tags that never receive an end tag, so the walk below must not count them.
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "source", "track", "wbr"}


class SortableAncestry(HTMLParser):
    """Records the container classes wrapped around each ``data-sortable`` list.

    Enough to ask a layout question of rendered HTML: two lists that share a
    container are laid out next to each other, and two that do not are stacked.
    """

    def __init__(self):
        super().__init__()
        self.stack = []
        self.ancestors = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        key = attrs.get("data-sortable")
        if key and key not in self.ancestors:
            self.ancestors[key] = list(self.stack)
        if tag not in VOID_TAGS:
            self.stack.append(attrs.get("class", ""))

    def handle_endtag(self, tag):
        if tag not in VOID_TAGS and self.stack:
            self.stack.pop()


class RegistryIntegrityTests(TestCase):
    """Every declared source must be renderable, editable, and reachable."""

    def test_every_source_key_is_a_real_page_layout(self):
        layouts = set(dict(PageSection.Layout.choices))
        for source in all_content_sources():
            with self.subTest(source=source.key):
                self.assertIn(source.key, layouts)

    def test_every_data_layout_has_a_registered_source(self):
        """No layout may be a data layout without a source behind it."""
        for layout in PageSection.DATA_LAYOUTS:
            with self.subTest(layout=layout):
                self.assertIsNotNone(get_content_source(layout))

    def test_every_source_block_template_exists(self):
        for source in all_content_sources():
            with self.subTest(source=source.key):
                self.assertIsNotNone(get_template(source.block_template))

    def test_every_source_editor_template_exists(self):
        for source in all_content_sources():
            if not source.editor_template:
                continue
            with self.subTest(source=source.key):
                self.assertIsNotNone(get_template(source.editor_template))

    def test_every_source_manager_url_resolves(self):
        for source in all_content_sources():
            if not source.manager_url_name:
                continue
            with self.subTest(source=source.key):
                try:
                    reverse(source.manager_url_name)
                except NoReverseMatch:  # pragma: no cover - the assert reports it
                    self.fail(f"{source.key} points at a manager that is not routed")

    def test_every_source_resolves_without_data(self):
        """A brand-new install has empty tables; no block may crash on that."""
        for source in all_content_sources():
            section = PageSection(page=SitePage.get_for("home"), layout=source.key)
            with self.subTest(source=source.key):
                self.assertIsInstance(resolve_section_data(section), dict)

    def test_orderable_sources_point_at_a_model_with_an_order_column(self):
        for source in all_content_sources():
            if not source.is_orderable:
                continue
            with self.subTest(source=source.key):
                model = resolve_order_model(source)
                self.assertIn("order", [f.name for f in model._meta.get_fields()])

    def test_a_section_bound_to_an_unknown_source_renders_as_text(self):
        """A stale layout must not take a public page down."""
        section = PageSection(page=SitePage.get_for("home"), layout="NOT_A_SOURCE")
        self.assertIsNone(resolve_section_data(section))
        self.assertEqual(section.block_template, "details/blocks/text.html")


class SDGSourceTests(TestCase):
    """The SDG section renders rows, which is what made it editable at last."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("sdg_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("sdg_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_seventeen_goals_are_seeded(self):
        self.assertEqual(SustainableDevelopmentGoal.objects.count(), 17)
        self.assertEqual(
            SustainableDevelopmentGoal.objects.order_by("order").first().title,
            "No Poverty",
        )

    def test_the_home_sdg_section_renders_the_seeded_goals(self):
        """Regression: this section used to look empty in the editor.

        The cards were hardcoded in the template, so the block had no data
        behind it and nothing an admin could edit.
        """
        response = self.client.get("/")
        self.assertContains(response, "Sustainable Development Goals")
        self.assertContains(response, "No Poverty")
        self.assertContains(response, "Partnerships for the Goals")

    def test_the_page_editor_lists_each_goal_inside_the_sdg_section(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["home"]))
        self.assertContains(response, "inline-sdgs")
        goal = SustainableDevelopmentGoal.objects.order_by("order").first()
        self.assertContains(response, reverse("sdg_goal_update", args=[goal.id]))

    def test_renaming_a_goal_changes_the_public_card(self):
        goal = SustainableDevelopmentGoal.objects.get(code="01")
        self.client_admin.post(
            reverse("sdg_goal_update", args=[goal.id]),
            {"title": "SDG-RENAMED-MARKER", "summary": "", "is_visible": "on"},
        )
        self.assertContains(self.client.get("/"), "SDG-RENAMED-MARKER")

    def test_renaming_a_goal_also_changes_the_proposal_checklist(self):
        """One list of goals: the block and the wizard cannot drift apart."""
        goal = SustainableDevelopmentGoal.objects.get(code="05")
        goal.title = "WIZARD-SDG-MARKER"
        goal.save()

        self.assertIn(
            ("05", "WIZARD-SDG-MARKER"),
            SustainableDevelopmentGoal.as_choices(),
        )

    def test_a_hidden_goal_disappears_from_the_public_card_grid(self):
        goal = SustainableDevelopmentGoal.objects.get(code="02")
        self.client_admin.post(
            reverse("sdg_goal_update", args=[goal.id]),
            {"title": goal.title, "summary": ""},  # no is_visible
        )
        self.assertNotContains(self.client.get("/"), "Zero Hunger")

    def test_a_goal_can_be_added_and_deleted(self):
        self.client_admin.post(
            reverse("sdg_goal_create"),
            {"code": "18", "title": "NEW-GOAL-MARKER", "is_visible": "on"},
        )
        goal = SustainableDevelopmentGoal.objects.get(code="18")
        self.assertContains(self.client.get("/"), "NEW-GOAL-MARKER")

        self.client_admin.post(reverse("sdg_goal_delete", args=[goal.id]))
        self.assertFalse(SustainableDevelopmentGoal.objects.filter(code="18").exists())

    def test_a_duplicate_code_is_rejected(self):
        before = SustainableDevelopmentGoal.objects.count()
        self.client_admin.post(
            reverse("sdg_goal_create"),
            {"code": "01", "title": "Duplicate", "is_visible": "on"},
        )
        self.assertEqual(SustainableDevelopmentGoal.objects.count(), before)

    def test_as_choices_falls_back_to_the_builtin_list_when_empty(self):
        SustainableDevelopmentGoal.objects.all().delete()
        self.assertEqual(len(SustainableDevelopmentGoal.as_choices()), 17)

    def test_non_admins_cannot_edit_a_goal(self):
        goal = SustainableDevelopmentGoal.objects.get(code="01")
        client = factories.make_client(self.faculty)
        status = client.post(
            reverse("sdg_goal_update", args=[goal.id]),
            {"title": "nope", "is_visible": "on"},
        ).status_code
        self.assertIn(status, DENIED)

        goal.refresh_from_db()
        self.assertEqual(goal.title, "No Poverty")


class BlockPaletteTests(TestCase):
    """Dragging a builder onto a page binds the section to its live data."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("palette_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("palette_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_editor_offers_every_registered_builder(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["reports"]))
        for source in all_content_sources():
            with self.subTest(source=source.key):
                self.assertContains(response, source.label)

    def test_dropping_a_builder_creates_a_section_bound_to_it(self):
        self.client_admin.post(
            reverse("page_section_add_source", args=["reports"]), {"source": "THRUST"}
        )
        section = PageSection.objects.get(page__slug="reports", layout="THRUST")
        self.assertEqual(section.heading, CONTENT_SOURCES["THRUST"].label)
        self.assertTrue(section.is_visible)

    def test_a_dropped_block_publishes_the_builders_rows(self):
        HomeThrust.objects.create(title="DROPPED-THRUST-MARKER", is_visible=True)
        self.client_admin.post(
            reverse("page_section_add_source", args=["reports"]), {"source": "THRUST"}
        )
        self.assertContains(self.client.get(reverse("reports_page")), "DROPPED-THRUST-MARKER")

    def test_the_same_builder_can_be_published_on_two_pages(self):
        """One body of data, two pages — not a copy."""
        HomeThrust.objects.create(title="SHARED-THRUST-MARKER", is_visible=True)
        for slug in ("reports", "achievements"):
            self.client_admin.post(
                reverse("page_section_add_source", args=[slug]), {"source": "THRUST"}
            )

        self.assertContains(self.client.get(reverse("reports_page")), "SHARED-THRUST-MARKER")
        self.assertContains(self.client.get(reverse("achievements_page")), "SHARED-THRUST-MARKER")
        self.assertEqual(HomeThrust.objects.filter(title="SHARED-THRUST-MARKER").count(), 1)

    def test_the_palette_is_a_rail_on_the_right_of_the_section_list(self):
        """Drag-and-drop only works if the tile and its row are on screen together.

        A palette stacked above a page of dozens of rows means dragging a block
        the length of the page, so the rail and the canvas must share one split
        container — and the rail must be sticky to stay in view. The content is
        the main column on the left and the blocks sit in the rail on the right,
        so a tile is a short sideways drag from the row it becomes.
        """
        html = self.client_admin.get(
            reverse("page_content_edit", args=["home"])
        ).content.decode()
        finder = SortableAncestry()
        finder.feed(html)

        palette, sections = finder.ancestors["palette"], finder.ancestors["sections"]
        self.assertIn("nx-split__rail nx-split__rail--sticky", palette)
        self.assertTrue(
            set(palette) & set(sections) & {"nx-split nx-split--rail-right mb-6"},
            f"palette {palette} and sections {sections} share no split container",
        )
        self.assertTrue(
            any("nx-split__main" in cls for cls in sections),
            f"the section list must be the main (left) column, got {sections}",
        )

    def test_a_block_dropped_at_a_position_lands_there(self):
        self.client_admin.post(
            reverse("page_section_add_source", args=["reports"]),
            {"source": "THRUST", "position": "1"},
        )
        first = PageSection.objects.filter(page__slug="reports").order_by("order", "id").first()
        self.assertEqual(first.layout, "THRUST")

    def test_an_unknown_source_is_rejected(self):
        before = PageSection.objects.filter(page__slug="reports").count()
        self.client_admin.post(
            reverse("page_section_add_source", args=["reports"]), {"source": "NOPE"}
        )
        self.assertEqual(PageSection.objects.filter(page__slug="reports").count(), before)

    def test_adding_a_block_requires_post(self):
        self.assertEqual(
            self.client_admin.get(reverse("page_section_add_source", args=["reports"])).status_code,
            405,
        )

    def test_non_admins_cannot_add_a_block(self):
        client = factories.make_client(self.faculty)
        status = client.post(
            reverse("page_section_add_source", args=["reports"]), {"source": "THRUST"}
        ).status_code
        self.assertIn(status, DENIED)


class SectionDragOrderTests(TestCase):
    """Sections are reordered by dragging, in one request."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("drag_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("drag_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)
        self.page = SitePage.get_for("achievements")
        self.page.sections.all().delete()
        self.a = PageSection.objects.create(page=self.page, heading="A", order=1)
        self.b = PageSection.objects.create(page=self.page, heading="B", order=2)
        self.c = PageSection.objects.create(page=self.page, heading="C", order=3)

    def _reorder(self, ids, client=None):
        return (client or self.client_admin).post(
            reverse("page_sections_reorder", args=["achievements"]),
            data=json.dumps({"section_ids": ids}),
            content_type="application/json",
        )

    def _headings(self):
        return list(self.page.sections.order_by("order", "id").values_list("heading", flat=True))

    def test_a_dragged_order_is_saved(self):
        response = self._reorder([self.c.id, self.a.id, self.b.id])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(self._headings(), ["C", "A", "B"])

    def test_the_new_order_shows_on_the_public_page(self):
        self._reorder([self.c.id, self.b.id, self.a.id])
        html = self.client.get(reverse("achievements_page")).content.decode()
        self.assertLess(html.index(">C<"), html.index(">B<"))
        self.assertLess(html.index(">B<"), html.index(">A<"))

    def test_a_partial_payload_is_refused(self):
        response = self._reorder([self.c.id, self.a.id])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._headings(), ["A", "B", "C"])

    def test_a_section_from_another_page_is_refused(self):
        other = PageSection.objects.create(page=SitePage.get_for("reports"), heading="X")
        response = self._reorder([self.a.id, self.b.id, other.id])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._headings(), ["A", "B", "C"])

    def test_malformed_json_is_refused(self):
        response = self.client_admin.post(
            reverse("page_sections_reorder", args=["achievements"]),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_the_drag_is_recorded_in_the_audit_trail(self):
        from details.models import PageContentLog

        self._reorder([self.b.id, self.a.id, self.c.id])
        self.assertTrue(
            PageContentLog.objects.filter(
                page_slug="achievements", action=PageContentLog.Action.MOVE_SECTION
            ).exists()
        )

    def test_non_admins_cannot_reorder(self):
        status = self._reorder(
            [self.c.id, self.b.id, self.a.id], client=factories.make_client(self.faculty)
        ).status_code
        self.assertIn(status, DENIED)
        self.assertEqual(self._headings(), ["A", "B", "C"])

    def test_the_legacy_one_step_move_still_updates_section_order(self):
        """Older/direct clients can still request a one-position move."""
        self.client_admin.post(
            reverse("page_section_move", args=[self.c.id]), {"direction": "up"}
        )
        self.assertEqual(self._headings(), ["A", "C", "B"])


class SectionCanvasTests(TestCase):
    """Rows collapse to slim bars and drag by themselves.

    Tall rows with open nested editors make it hard to drop a block between
    rows or to see where a dragged row will land, so every row folds to its
    header bar on demand — and any row can be picked up anywhere, not just by
    its grip, while controls and nested editors stay click-through.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("canvas_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)
        self.page = SitePage.get_for("achievements")
        self.page.sections.all().delete()
        self.section = PageSection.objects.create(
            page=self.page, heading="Canvas Row", subheading="Sub line", order=1
        )

    def _editor_html(self):
        return self.client_admin.get(
            reverse("page_content_edit", args=["achievements"])
        ).content.decode()

    def test_each_section_row_can_be_collapsed(self):
        html = self._editor_html()
        self.assertIn(f'aria-controls="pc-section-body-{self.section.id}"', html)
        self.assertIn(f'id="pc-section-body-{self.section.id}"', html)
        self.assertIn("pc-row__body", html)
        self.assertIn("js-section-toggle", html)

    def test_the_canvas_offers_collapse_all_and_expand_all(self):
        html = self._editor_html()
        self.assertIn("data-collapse-all", html)
        self.assertIn("data-expand-all", html)

    def test_a_row_is_grabbable_anywhere_except_its_controls(self):
        """Whole-row drag, with the nested editors opted out of starting one."""
        html = self._editor_html()
        self.assertNotIn('handle: ".js-section-handle"', html)
        self.assertIn("preventOnFilter: false", html)
        self.assertIn(".pc-row__editor", html)

    def test_keyboard_reordering_uses_ajax_without_submitting_the_page(self):
        html = self._editor_html()
        start = html.index("window.nxKeyboardMove = function (event, sectionId)")
        end = html.index("};", start) + 2
        keyboard_handler = html[start:end]

        self.assertIn("postOrder(", keyboard_handler)
        self.assertNotIn(".submit(", keyboard_handler)
        self.assertNotIn('id="keyboard-move-form"', html)
        self.assertIn("fetch(url", html)

    def test_orderable_blocks_can_be_dragged_into_order_inside_their_section(self):
        """The items inside a source reorder by drag, where the model allows it."""
        HomeThrust.objects.create(title="Draggable Thrust", is_visible=True)
        ExtensionProcess.objects.create(title="Draggable Process")
        for key in ("THRUST", "PROCESSES", "SDG"):
            with self.subTest(source=key):
                self.client_admin.post(
                    reverse("page_section_add_source", args=["achievements"]),
                    {"source": key},
                )
                html = self._editor_html()
                self.assertIn(
                    f'data-reorder-url="{reverse("content_source_reorder", args=[key])}"',
                    html,
                )
                self.assertIn("js-item-handle", html)


class SourceItemDragOrderTests(TestCase):
    """The items inside a source are dragged into order too."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("item_drag_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("item_drag_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _reorder(self, key, ids, client=None):
        return (client or self.client_admin).post(
            reverse("content_source_reorder", args=[key]),
            data=json.dumps({"item_ids": ids}),
            content_type="application/json",
        )

    def test_sdg_goals_can_be_dragged_into_a_new_order(self):
        ids = list(
            SustainableDevelopmentGoal.objects.order_by("order").values_list("id", flat=True)
        )
        response = self._reorder("SDG", list(reversed(ids)))
        self.assertEqual(response.status_code, 200)

        reordered = list(
            SustainableDevelopmentGoal.objects.order_by("order").values_list("code", flat=True)
        )
        self.assertEqual(reordered[0], "17")
        self.assertEqual(reordered[-1], "01")

    def test_the_new_goal_order_shows_on_the_public_page(self):
        ids = list(
            SustainableDevelopmentGoal.objects.order_by("order").values_list("id", flat=True)
        )
        self._reorder("SDG", list(reversed(ids)))

        html = self.client.get("/").content.decode()
        self.assertLess(html.index("Partnerships for the Goals"), html.index("No Poverty"))

    def test_thrust_cards_can_be_dragged_into_a_new_order(self):
        ids = list(HomeThrust.objects.order_by("order").values_list("id", flat=True))
        titles = list(HomeThrust.objects.order_by("order").values_list("title", flat=True))

        self._reorder("THRUST", [ids[1], ids[0]] + ids[2:])

        reordered = list(HomeThrust.objects.order_by("order").values_list("title", flat=True))
        self.assertEqual(reordered[0], titles[1])
        self.assertEqual(reordered[1], titles[0])

    def test_the_thrusts_screen_offers_a_handle_and_no_arrow_buttons(self):
        """Dragging is the reorder control, so no ↑/↓ buttons sit beside it."""
        html = self.client_admin.get(reverse("home_sections_manager")).content.decode()
        self.assertIn("js-item-handle", html)
        self.assertIn(
            f'data-reorder-url="{reverse("content_source_reorder", args=["THRUST"])}"', html
        )
        self.assertNotIn("↑", html)
        self.assertNotIn("↓", html)
        thrust = HomeThrust.objects.order_by("order").first()
        self.assertNotIn(reverse("home_thrust_move", args=[thrust.id]), html)

    def test_the_nested_thrust_editor_keeps_only_the_handle(self):
        """The same editor inside a page's section drags; it has no arrows."""
        thrust = HomeThrust.objects.order_by("order").first()
        self.client_admin.post(
            reverse("page_section_add_source", args=["achievements"]), {"source": "THRUST"}
        )
        html = self.client_admin.get(
            reverse("page_content_edit", args=["achievements"])
        ).content.decode()
        self.assertIn("js-item-handle", html)
        self.assertNotIn("↑", html)
        self.assertNotIn("↓", html)
        self.assertNotIn(reverse("home_inline_thrust_move", args=[thrust.id]), html)

    def test_a_source_that_is_not_orderable_is_refused(self):
        self.assertIsNone(orderable_source("TEMPLATES"))
        response = self._reorder("TEMPLATES", [1, 2])
        self.assertEqual(response.status_code, 400)

    def test_a_partial_payload_is_refused(self):
        ids = list(
            SustainableDevelopmentGoal.objects.order_by("order").values_list("id", flat=True)
        )
        response = self._reorder("SDG", ids[:3])
        self.assertEqual(response.status_code, 400)

        first = SustainableDevelopmentGoal.objects.order_by("order").first()
        self.assertEqual(first.code, "01")

    def test_non_admins_cannot_reorder_a_source(self):
        ids = list(
            SustainableDevelopmentGoal.objects.order_by("order").values_list("id", flat=True)
        )
        status = self._reorder(
            "SDG", list(reversed(ids)), client=factories.make_client(self.faculty)
        ).status_code
        self.assertIn(status, DENIED)


class ServicesPageCompositionTests(TestCase):
    """Services is composed of blocks, so nothing is published twice."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("services_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_services_page_owns_its_blocks(self):
        layouts = set(
            PageSection.objects.filter(page__slug="services").values_list("layout", flat=True)
        )
        # The Office Forms block was dropped together with the Form Builder.
        self.assertEqual(layouts, {"PROCESSES", "TEMPLATES"})

    def test_a_template_is_listed_once_on_the_services_page(self):
        """Regression: the Template Library was rendered twice.

        Once by the page's own hardcoded section and once by the block, so the
        same file appeared under both, with no way to reorder or hide either.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from details.models import DocumentTemplate

        DocumentTemplate.objects.create(
            title="SERVICES-TEMPLATE-MARKER",
            file=SimpleUploadedFile("f.docx", b"bytes"),
            is_active=True,
        )

        html = self.client.get(reverse("services_home")).content.decode()
        self.assertEqual(html.count("SERVICES-TEMPLATE-MARKER"), 1)

    def test_dynamic_forms_are_no_longer_published_on_the_services_page(self):
        """The Form Builder was removed, so its output has no public block."""
        from details.models import DynamicFormTemplate

        DynamicFormTemplate.objects.create(
            name="SERVICES-FORM-MARKER", slug="services-form-marker", is_active=True
        )

        html = self.client.get(reverse("services_home")).content.decode()
        self.assertEqual(html.count("SERVICES-FORM-MARKER"), 0)

    def test_a_process_is_listed_once_on_the_services_page(self):
        from details.models import ExtensionProcess

        ExtensionProcess.objects.create(title="SERVICES-PROCESS-MARKER")

        html = self.client.get(reverse("services_home")).content.decode()
        self.assertEqual(html.count("SERVICES-PROCESS-MARKER"), 1)

    def test_hiding_the_template_block_removes_it_from_the_page(self):
        """What used to be hardcoded is now genuinely admin-controlled."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from details.models import DocumentTemplate

        DocumentTemplate.objects.create(
            title="HIDEABLE-TEMPLATE-MARKER",
            file=SimpleUploadedFile("f.docx", b"bytes"),
            is_active=True,
        )
        section = PageSection.objects.get(page__slug="services", layout="TEMPLATES")
        section.is_visible = False
        section.save()

        self.assertNotContains(
            self.client.get(reverse("services_home")), "HIDEABLE-TEMPLATE-MARKER"
        )

    def test_the_workflow_phases_still_render(self):
        """The parts that genuinely belong to this page are untouched."""
        response = self.client.get(reverse("services_home"))
        self.assertContains(response, "From proposal to implementation")
        self.assertContains(response, "total 100% of overall progress")

    def test_the_jump_links_follow_the_blocks(self):
        section = PageSection.objects.get(page__slug="services", layout="TEMPLATES")
        section.heading = "JUMP-LINK-MARKER"
        section.save()

        response = self.client.get(reverse("services_home"))
        self.assertContains(response, "JUMP-LINK-MARKER")
        self.assertContains(response, f'href="#{section.anchor}"')
