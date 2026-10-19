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

    def test_the_switch_sits_beside_the_panel_title(self):
        """The switch shares the header row instead of taking its own row."""
        css = (settings.BASE_DIR / 'static/css/dashboard-views.css').read_text()
        self.assertIn('.dashboard-panel-head {', css)
        self.assertIn('.dashboard-panel-head .dashboard-view-toolbar {', css)
        self.assertIn('margin-left: auto', css)
        # Every proposal panel leaves a slot for the switch in its header.
        for name in (
            'evaluator_dashboard.html',
            'staff_dashboard.html',
            'campus_coordinator_dashboard.html',
            'department_coordinator_dashboard.html',
        ):
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                self.assertEqual(text.count('class="dashboard-panel-head border-b'), 3)
                self.assertEqual(text.count('data-proposal-view-slot'), 3)
        # The faculty dashboard ships its switch inside the header, above the
        # layouts it drives rather than below the heading.
        faculty = (self.dashboards / 'faculty_dashboard.html').read_text()
        head = faculty.index('dashboard-panel-head')
        toolbar = faculty.index('class="dashboard-view-toolbar"')
        layout = faculty.index('data-proposal-layout')
        self.assertLess(head, toolbar)
        self.assertLess(toolbar, layout)
        # The fallback placement above a bare table still keeps its inset.
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


class ActionIconTests(SimpleTestCase):
    """Table actions draw from one icon set, in the style of the app's icons.

    The add / edit / delete icons these pages already shipped are Heroicons
    v1.0.6 20/solid glyphs. Row actions reuse that exact set (one 20x20 grid,
    solid fill, currentColor) instead of mixing in outline or 24px icons.
    """

    sprite = settings.BASE_DIR / 'templates/partials/_icon_sprite.html'
    templates = settings.BASE_DIR / 'accounts/templates'

    def test_every_symbol_is_a_20px_solid_currentcolor_glyph(self):
        text = self.sprite.read_text()
        symbols = re.findall(r'<symbol id="([^"]+)"([^>]*)>(.*?)</symbol>', text, re.S)
        self.assertTrue(symbols, 'the shared sprite ships icons')
        for name, attributes, body in symbols:
            with self.subTest(icon=name):
                self.assertIn('viewBox="0 0 20 20"', attributes)
                self.assertIn('fill="currentColor"', attributes)
                self.assertIn('<path', body)
                # Outline glyphs carry stroke geometry; this set must not.
                self.assertNotIn('stroke=', body)

    def test_the_edit_and_delete_glyphs_are_the_ones_already_in_use(self):
        text = self.sprite.read_text()
        # Verbatim Heroicons v1.0.6 20/solid pencil and trash, i.e. the same
        # glyphs the admin tables drew before the icons were centralised.
        self.assertIn('M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793z', text)
        self.assertIn('M9 2a1 1 0 00-.894.553L7.382 4H4', text)

    def test_the_sprite_is_loaded_once_for_the_whole_app(self):
        base = (settings.BASE_DIR / 'templates/base.html').read_text()
        self.assertEqual(base.count('partials/_icon_sprite.html'), 1)
        # It must sit inside <body> so every page that extends base.html has it.
        self.assertLess(base.index('<body'), base.index('partials/_icon_sprite.html'))

    def test_every_table_action_is_an_icon_button_with_a_tooltip(self):
        pattern = re.compile(r'<th[^>]*>\s*Actions?\s*</th>', re.I)
        for path in self.templates.rglob('*.html'):
            text = path.read_text()
            if not pattern.search(text):
                continue
            with self.subTest(template=str(path.relative_to(self.templates))):
                # Each action is one sprite icon, never a bare text control.
                for tag in re.findall(r'<(?:a|button)\b[^>]*>', text):
                    if 'nx-btn--icon' not in tag:
                        continue
                    self.assertIn('data-nx-tooltip=', tag)
                    self.assertIn('aria-label=', tag)

    def test_the_admin_user_table_uses_icons_instead_of_text_links(self):
        text = (self.templates / 'dashboard/admin_dashboard.html').read_text()
        self.assertIn('data-nx-tooltip="View user details"', text)
        self.assertIn('data-nx-tooltip="Edit user"', text)
        self.assertNotIn('class="adm-link" data-nx-skeleton="record"', text)
        self.assertNotIn('class="adm-link" data-nx-skeleton="form"', text)

    def test_icon_buttons_all_take_their_glyph_from_the_sprite(self):
        for name in (
            'dashboard/admin/campuses_list.html',
            'dashboard/admin/colleges_list.html',
            'dashboard/admin/departments_list.html',
            'dashboard/admin/activities_list.html',
            'dashboard/admin/personnel_list.html',
            'dashboard/admin/targets_list.html',
            'dashboard/admin/processes_list.html',
            'dashboard/admin/signatories_list.html',
            'dashboard/admin/wizard_steps_manager.html',
            'dashboard/admin/document_templates_list.html',
            'dashboard/accomplishment_reports_list.html',
            'dashboard/staff_dashboard.html',
            'dashboard/evaluator_dashboard.html',
        ):
            with self.subTest(template=name):
                text = (self.templates / name).read_text()
                uses = re.findall(r'<use href="#([^"]+)"></use>', text)
                self.assertTrue(uses, 'icons come from the shared sprite')
                self.assertIn('data-nx-tooltip=', text)
                self.assertIn('aria-label=', text)
                # The old hand-drawn 20px solids are gone.
                self.assertNotIn('d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h3.828l8.38-8.379-2.83-2.828z"', text)
