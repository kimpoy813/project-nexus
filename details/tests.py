"""
Model-level tests for the content app.

View-level coverage of these models lives in ``accounts/tests/test_cms.py``;
this file covers behaviour that belongs to the models themselves.
"""

from django.test import TestCase

from .models import (
    HomeSectionHeading,
    HomeThrust,
    PageSection,
    SitePage,
    WorkflowPhase,
)


class SitePageModelTests(TestCase):
    def test_get_for_returns_the_seeded_page(self):
        page = SitePage.get_for(SitePage.Slug.HOME)
        self.assertEqual(page.slug, "home")

    def test_get_for_creates_a_page_that_is_somehow_missing(self):
        SitePage.objects.filter(slug="reports").delete()

        page = SitePage.get_for(SitePage.Slug.REPORTS)
        self.assertEqual(page.slug, "reports")
        self.assertTrue(SitePage.objects.filter(slug="reports").exists())

    def test_visible_sections_excludes_hidden_ones(self):
        page = SitePage.get_for(SitePage.Slug.HOME)
        PageSection.objects.create(page=page, heading="Shown", is_visible=True)
        PageSection.objects.create(page=page, heading="Hidden", is_visible=False)

        headings = list(page.visible_sections.values_list("heading", flat=True))
        self.assertEqual(headings, ["Shown"])


class PageSectionModelTests(TestCase):
    def setUp(self):
        self.page = SitePage.get_for(SitePage.Slug.ACHIEVEMENTS)

    def test_order_is_assigned_automatically(self):
        first = PageSection.objects.create(page=self.page, heading="First", order=0)
        second = PageSection.objects.create(page=self.page, heading="Second", order=0)

        self.assertEqual(first.order, 1)
        self.assertEqual(second.order, 2)

    def test_sections_are_ordered_by_their_order_field(self):
        PageSection.objects.create(page=self.page, heading="B", order=2)
        PageSection.objects.create(page=self.page, heading="A", order=1)

        headings = list(self.page.sections.values_list("heading", flat=True))
        self.assertEqual(headings, ["A", "B"])


class HomeThrustModelTests(TestCase):
    def test_new_thrusts_are_appended_to_the_end(self):
        highest = HomeThrust.objects.order_by("-order").first().order

        thrust = HomeThrust.objects.create(title="Appended", order=0)
        self.assertEqual(thrust.order, highest + 1)

    def test_thrusts_are_ordered_by_their_order_field(self):
        titles = list(HomeThrust.objects.values_list("title", flat=True))
        orders = list(HomeThrust.objects.values_list("order", flat=True))
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(titles[0], "Indigenous Heritage Protection")


class HomeSectionHeadingModelTests(TestCase):
    def test_as_map_is_keyed_by_section(self):
        mapping = HomeSectionHeading.as_map()

        self.assertIn("thrust", mapping)
        self.assertEqual(mapping["thrust"].subtitle, "Isem Ni Aran")

    def test_get_for_creates_a_missing_section(self):
        HomeSectionHeading.objects.filter(section="sdg").delete()

        row = HomeSectionHeading.get_for(HomeSectionHeading.Section.SDG)
        self.assertEqual(row.section, "sdg")


class WorkflowPhaseModelTests(TestCase):
    def test_weight_is_clamped_to_the_0_100_range(self):
        phase = WorkflowPhase.objects.get(key="proposal")

        phase.weight_percent = 250
        phase.save()
        self.assertEqual(phase.weight_percent, 100)

    def test_ordered_visible_excludes_hidden_phases(self):
        phase = WorkflowPhase.objects.get(key="moa")
        phase.is_visible = False
        phase.save()

        keys = list(WorkflowPhase.ordered_visible().values_list("key", flat=True))
        self.assertNotIn("moa", keys)
        self.assertIn("proposal", keys)
