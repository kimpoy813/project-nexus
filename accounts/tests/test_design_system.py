"""Shared component adoption, separate from page-specific workflow behavior."""
import re
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from accounts.tests import factories
from proposals.models import Proposal


class SharedComponentRenderingTests(TestCase):
    def test_main_page_families_load_the_same_component_layer(self):
        _, client = factories.admin('design_admin')
        for name in ('admin_dashboard', 'campuses_list', 'campus_create', 'page_content_list', 'proposal_templates_list', 'admin_create_account'):
            with self.subTest(name=name):
                response = client.get(reverse(name))
                self.assertContains(response, 'css/nexus-components.css')
                self.assertContains(response, 'nx-btn')
                self.assertContains(response, 'nx-page-title')
                self.assertContains(response, 'nx-panel')

    def test_auth_keeps_its_layout_but_uses_shared_panels_and_actions(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'data-nx-page-kind="auth"')
        self.assertContains(response, 'nx-auth')
        self.assertContains(response, 'nx-panel')
        self.assertContains(response, 'nx-btn--primary')

    def test_wizard_and_tracker_use_shared_actions_and_surfaces(self):
        owner, client = factories.faculty('design_owner')
        proposal = Proposal.objects.create(created_by=owner)
        for name, args in (('proposal_wizard', [proposal.id, 1]), ('proposal_moa_tracker', [proposal.id]), ('proposal_implementation_tracker', [proposal.id])):
            with self.subTest(name=name):
                response = client.get(reverse(name, args=args))
                self.assertContains(response, 'nx-btn')
                self.assertContains(response, 'nx-panel')
        self.assertContains(client.get(reverse('proposal_wizard', args=[proposal.id, 1])), 'id="wizard-step-navigation"')

    def test_draft_moa_status_is_not_an_empty_card(self):
        owner, client = factories.faculty('design_moa')
        proposal = Proposal.objects.create(created_by=owner)
        response = client.get(reverse('proposal_moa_tracker', args=[proposal.id]))
        self.assertContains(response, 'Your MOA has not started yet.')

    def test_revision_dashboard_renders_its_real_summary_link(self):
        owner, client = factories.faculty('design_revision')
        proposal = Proposal.objects.create(created_by=owner, proposal_status=Proposal.ProposalStatus.FOR_REVISION)
        response = client.get(reverse('faculty_dashboard'))
        self.assertContains(response, reverse('proposal_comment_summary', args=[proposal.id]))


class ComponentContractTests(SimpleTestCase):
    def test_color_utility_does_not_gain_button_interaction_styles(self):
        css = (settings.BASE_DIR / 'static/css/nexus-ui.css').read_text()
        self.assertNotRegex(css, r'(?m)^\.bg-primary(?::hover)?\s*[,\{]')
        self.assertNotIn('buttona.', css)

    def test_shared_styles_define_geometry_and_semantic_variants(self):
        css = (settings.BASE_DIR / 'static/css/nexus-components.css').read_text()
        for token in ('--nx-control-height: 2.75rem', '--nx-control-radius: .75rem', '--nx-panel-radius: 1rem', '.nx-btn--primary', '.nx-btn--secondary', '.nx-btn--danger', '.nx-btn--compact', '.nx-page-header', '.nx-badge', '.nx-table'):
            self.assertIn(token, css)

    def test_shared_layer_loads_after_legacy_component_styles(self):
        html = (settings.BASE_DIR / 'templates/base.html').read_text()
        self.assertGreater(html.index('nexus-components.css'), html.index('dashboard-views.css'))
        self.assertGreater(html.index('nexus-components.css'), html.index('block extra_head'))

    def test_explicit_component_adoption_covers_template_families(self):
        counts = dict.fromkeys(('nx-btn', 'nx-panel', 'nx-page-title', 'nx-table', 'nx-badge'), 0)
        for folder in ('accounts/templates', 'proposals/templates', 'details/templates'):
            for path in (settings.BASE_DIR / folder).rglob('*.html'):
                for classes in re.findall(r'class="([^"]*)"', path.read_text()):
                    for component in counts:
                        counts[component] += component in classes.split()
        for component, minimum in {'nx-btn': 400, 'nx-panel': 200, 'nx-page-title': 70, 'nx-table': 30, 'nx-badge': 150}.items():
            self.assertGreaterEqual(counts[component], minimum, component)


class ProposalPresentationTests(SimpleTestCase):
    """The table/card switch belongs to proposal tables only.

    Matrix tables (extension targets, campus statistics, user lists) lose
    their meaning when each row becomes a card, so they stay tables.
    """

    dashboards = settings.BASE_DIR / 'accounts/templates/dashboard'

    def test_only_proposal_tables_are_marked_for_the_card_switch(self):
        expected = {
            'evaluator_dashboard.html': 3,
            'staff_dashboard.html': 3,
            'campus_coordinator_dashboard.html': 3,
            'department_coordinator_dashboard.html': 3,
            'faculty_dashboard.html': 1,
        }
        for name, count in expected.items():
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                marked = re.findall(r'<table[^>]*data-proposal-table[^>]*>', text)
                self.assertEqual(len(marked), count)

    def test_tables_that_are_not_proposals_are_left_alone(self):
        for name in ('admin_dashboard.html', 'director_dashboard.html', 'dashboard_base.html'):
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                self.assertNotIn('data-proposal-table', text)

    def test_the_switch_is_icon_only(self):
        faculty = (self.dashboards / 'faculty_dashboard.html').read_text()
        self.assertIn('data-proposal-view="table"', faculty)
        self.assertIn('data-proposal-view="cards"', faculty)
        self.assertIn('aria-label="Table view"', faculty)
        self.assertIn('aria-label="Card view"', faculty)
        self.assertNotIn('Table View', faculty)
        self.assertNotIn('Card View', faculty)
        # The glyphs are the same inline icons the rest of the system draws.
        self.assertIn('viewBox="0 0 20 20" fill="currentColor"', faculty)

    def test_the_template_and_the_script_ship_the_same_glyphs(self):
        """One pair of glyphs: the hand-built switch and the injected one.

        The table glyph is a framed grid with a filled header row and the
        card glyph a pair of content cards, so the two are told apart at a
        glance; keeping them identical in both places keeps that true
        everywhere the switch appears.
        """
        script = (settings.BASE_DIR / 'static/js/dashboard-views.js').read_text()
        faculty = (self.dashboards / 'faculty_dashboard.html').read_text()
        # The template pretty-prints the markup the script keeps on one line,
        # so compare the glyphs with their whitespace folded away.
        flat = re.sub(r'\s+', '', faculty)
        for view in ('table', 'cards'):
            with self.subTest(view=view):
                glyph = re.search(r"%s: '(<svg .*?</svg>)'" % view, script)
                self.assertIsNotNone(glyph, 'the script ships a %s glyph' % view)
                self.assertIn(re.sub(r'\s+', '', glyph.group(1)), flat)

    def test_the_switch_is_a_pill_with_a_sliding_thumb(self):
        css = (settings.BASE_DIR / 'static/css/dashboard-views.css').read_text()
        # A single track with a thumb that slides under the pressed icon.
        self.assertIn('.dashboard-view-toolbar::before', css)
        self.assertIn(':has([data-proposal-view="cards"][aria-pressed="true"])::before', css)
        # The segments stay transparent so the thumb shows through them; the
        # pressed segment is told by its icon colour, not its own fill.
        self.assertIn('.dashboard-view-toggle[aria-pressed="true"],', css)
        self.assertIn('.dashboard-view-toggle[aria-pressed="true"]:hover { color: #fff; }', css)
        # Browsers without :has() still get a switch, just without the slide.
        self.assertIn('@supports not selector(:has(*))', css)
        # Motion-sensitive visitors get the switch without the slide.
        self.assertIn('prefers-reduced-motion', css)
        # The shared control geometry no longer squares off the pill.
        shared = (settings.BASE_DIR / 'static/css/nexus-components.css').read_text()
        self.assertNotIn('.nexus-shell .dashboard-view-toggle[aria-pressed="true"]', shared)
        self.assertNotIn(':is(.dashboard-view-toggle, .quick-tab-btn, .nx-step-btn)', shared)

    def test_the_switch_keeps_clear_of_the_panel_edge(self):
        css = (settings.BASE_DIR / 'static/css/dashboard-views.css').read_text()
        # Switches injected into a bare card carry their own inset instead of
        # hugging the header rule and the panel edge.
        self.assertIn('.nx-card > .dashboard-view-toolbar', css)
        self.assertIn('--switch-inset-x: 1.25rem', css)

    def test_the_switch_ships_no_text_caption(self):
        script = (settings.BASE_DIR / 'static/js/dashboard-views.js').read_text()
        self.assertNotIn('dashboard-view-toolbar__label', script)
        self.assertNotIn('>View<', script)

    def test_card_view_is_scoped_to_the_switched_tables(self):
        css = (settings.BASE_DIR / 'static/css/dashboard-views.css').read_text()
        self.assertIn('.dashboard-data-table.dashboard-cards-view', css)
        self.assertNotIn('[data-dashboard-view]', css)


class SpeedometerGaugeCardTests(SimpleTestCase):
    """The faculty speedometer gauge card is the proposal card everywhere.

    Every role dashboard that lists proposals pairs its table with the same
    gauge card: a doughnut banded into the Proposal / MOA / Implementation
    phase zones that counts up to the proposal's overall progress.
    """

    dashboards = settings.BASE_DIR / 'accounts/templates/dashboard'

    gauge_dashboards = (
        'faculty_dashboard.html',
        'evaluator_dashboard.html',
        'staff_dashboard.html',
        'campus_coordinator_dashboard.html',
        'department_coordinator_dashboard.html',
        'director_dashboard.html',
        'dashboard_base.html',
    )

    def test_every_proposal_dashboard_ships_the_gauge_card(self):
        for name in self.gauge_dashboards:
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                self.assertIn('gaugeChart', text)
                self.assertIn('function createDoughnutGauge', text)
                self.assertIn('animateDoughnutGauge', text)

    def test_the_card_shows_the_phase_zones_and_the_progress_readout(self):
        for name in self.gauge_dashboards:
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                self.assertIn('nexusPhaseShares', text)
                self.assertIn('>Progress<', text)
                for zone in ('>Proposal<', '>MOA<', '>Implementation<'):
                    self.assertIn(zone, text)

    def test_the_gauge_arc_matches_the_faculty_card(self):
        """Zone colours, arc geometry and the white unfinished mask are shared."""
        faculty = (self.dashboards / 'faculty_dashboard.html').read_text()
        for token in (
            "#103b07",  # Proposal zone
            "#5a1113",  # MOA zone
            "#facc15",  # Implementation zone
            "rgba(255,255,255,0.92)",  # unfinished mask
            "(-234 * Math.PI) / 180",  # speedometer start angle
            "(288 * Math.PI) / 180",  # speedometer sweep
        ):
            self.assertIn(token, faculty)
            for name in (
                'evaluator_dashboard.html',
                'staff_dashboard.html',
                'campus_coordinator_dashboard.html',
                'department_coordinator_dashboard.html',
            ):
                with self.subTest(dashboard=name, token=token):
                    self.assertIn(token, (self.dashboards / name).read_text())

    def test_proposal_tables_are_paired_with_gauge_card_panels(self):
        for name in (
            'evaluator_dashboard.html',
            'staff_dashboard.html',
            'campus_coordinator_dashboard.html',
            'department_coordinator_dashboard.html',
        ):
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                self.assertEqual(text.count('data-proposal-layout'), 3)
                self.assertEqual(text.count('data-proposal-panel="table"'), 3)
                self.assertEqual(text.count('data-proposal-panel="cards"'), 3)


class GaugeCardRenderingTests(TestCase):
    """Each role dashboard renders a gauge per proposal it lists."""

    def test_your_own_proposals_render_the_gauge_card(self):
        cases = (
            (factories.evaluator, 'evaluator_dashboard'),
            (factories.department_coordinator, 'department_coordinator_dashboard'),
            (factories.campus_coordinator, 'campus_coordinator_dashboard'),
            (factories.faculty, 'faculty_dashboard'),
        )
        for factory, name in cases:
            with self.subTest(dashboard=name):
                user, client = factory(f'gauge_{name[:14]}')
                proposal = Proposal.objects.create(created_by=user, title='Gauge Proposal')
                response = client.get(reverse(name))
                self.assertContains(response, f'id="gaugeChart{proposal.id}"')
                self.assertContains(response, 'data-proposal-layout')

    def test_staff_queue_proposals_render_the_gauge_card(self):
        user, client = factories.staff('gauge_staff')
        response = client.get(reverse('staff_dashboard'))
        self.assertContains(response, 'function createDoughnutGauge')
        self.assertContains(response, 'data-proposal-layout')
        self.assertContains(response, 'data-proposal-panel="cards"')
