"""Shared component adoption, separate from page-specific workflow behavior."""
import re
from html.parser import HTMLParser
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

    def test_django_admin_loads_the_same_native_select_layer(self):
        user, client = factories.admin('design_django_admin')
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=('is_staff', 'is_superuser'))

        response = client.get(reverse('admin:accounts_profile_add'))
        self.assertContains(response, 'css/nexus-select.css')
        self.assertContains(response, 'js/nexus-select.js')
        self.assertContains(response, '<select name="role"', html=False)

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

    def test_native_select_picker_is_branded_without_replacing_the_control(self):
        css = (settings.BASE_DIR / 'static/css/nexus-select.css').read_text()
        html = (settings.BASE_DIR / 'templates/base.html').read_text()
        admin_html = (settings.BASE_DIR / 'templates/admin/base_site.html').read_text()
        script = (settings.BASE_DIR / 'static/js/nexus-select.js').read_text()

        # Progressive enhancement: unsupported engines retain the working
        # native picker, while supporting engines expose its surface to CSS.
        self.assertIn('@supports (appearance: base-select)', css)
        self.assertIn('appearance: base-select', css)
        for selector in (
            '::picker(select)',
            '::picker-icon',
            'option::checkmark',
            'option:checked',
            'option:disabled',
            'option:focus-visible',
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)
        self.assertIn('color-scheme: light', css)
        self.assertIn('rgb(var(--nexus-primary-rgb, 16 59 7)', css)
        self.assertIn('prefers-reduced-motion', css)

        # The menu itself is CSS-only. The small progressive script adds the
        # browser-native selectedcontent slot for ellipsis; it never builds a
        # second menu or hides the actual form control like the old skin did.
        # Both the application and Django's separately generated admin load
        # this exact layer; neither shell may drift back to a native skin.
        for shell in (html, admin_html):
            self.assertIn('css/nexus-select.css', shell)
            self.assertIn('js/nexus-select.js', shell)
        self.assertIn('document.createElement("selectedcontent")', script)
        self.assertNotIn('custom-dropdown-container', html)
        self.assertNotIn('enhanceDropdowns', html)
        self.assertNotIn('custom-dropdown-container', script)

    def test_customizable_select_closed_state_keeps_table_controls_usable(self):
        css = (settings.BASE_DIR / 'static/css/nexus-select.css').read_text()
        enhanced = css.split('@supports (appearance: base-select)', 1)[1]
        closed_state = enhanced.split('select > button.nx-select__button', 1)[0]

        # Legacy .adm-input/.dir-input-style classes set display: block. The
        # shared enhancement must override that or the native picker icon wraps
        # below selectedcontent and doubles the closed control's height.
        for declaration in ('display: inline-flex', 'align-items: center', 'flex-wrap: nowrap', 'vertical-align: middle'):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, closed_state)

        # The other narrow-table failure is collapsing to the arrow alone.
        self.assertIn('@media (max-width: 640px)', closed_state)
        self.assertIn('.nexus-shell .nx-table select', closed_state)
        self.assertIn('min-width: 8rem', closed_state)

        # Invoker button must cover the full control surface (including behind
        # ::picker-icon) so clicking padding or the arrow never triggers a
        # light-dismiss + re-open flicker.
        self.assertIn('align-self: stretch', enhanced)
        self.assertIn('pointer-events: none', enhanced)
        self.assertIn('position-try-order: most-block-size', enhanced)

    def test_every_select_bearing_page_inherits_the_covered_application_shell(self):
        template_roots = tuple(
            settings.BASE_DIR / folder
            for folder in ('templates', 'accounts/templates', 'proposals/templates', 'details/templates')
        )
        templates = {
            path.relative_to(root).as_posix(): path
            for root in template_roots
            for path in root.rglob('*.html')
        }

        def reaches_base(path):
            visited = set()
            while path and path not in visited:
                visited.add(path)
                match = re.search(r'{%\s*extends\s+["\']([^"\']+)["\']', path.read_text())
                if not match:
                    return False
                parent = match.group(1)
                if parent == 'base.html':
                    return True
                path = templates.get(parent)
            return False

        # Partial field/repeater templates are inserted into these pages (and
        # are exercised by the observer tests). Every standalone page with a
        # select must still resolve to the base that loads the shared assets.
        select_pages = 0
        for name, path in templates.items():
            if not re.search(r'<select\b', path.read_text(), re.IGNORECASE) or path.name.startswith('_'):
                continue
            select_pages += 1
            with self.subTest(template=name):
                self.assertTrue(reaches_base(path), f'{name} is outside templates/base.html')
        self.assertGreater(select_pages, 20, 'the audit must cover the existing select page inventory')

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

    def test_all_dashboards_register_gauges_with_shared_lifecycle_controller(self):
        """Every gauge registers with window.nexusGauge so hidden panels/tabs replay."""
        for name in (
            'faculty_dashboard.html',
            'evaluator_dashboard.html',
            'staff_dashboard.html',
            'campus_coordinator_dashboard.html',
            'department_coordinator_dashboard.html',
            'director_dashboard.html',
            'dashboard_base.html',
        ):
            with self.subTest(dashboard=name):
                text = (self.dashboards / name).read_text()
                self.assertIn('window.nexusGauge.register(', text)
                self.assertIn('_nxGaugeRaf', text)

        for tabbed in ('director_dashboard.html', 'dashboard_base.html'):
            with self.subTest(tabbed=tabbed):
                text = (self.dashboards / tabbed).read_text()
                self.assertIn('window.nexusGauge.onPanelToggle(', text)
                self.assertIn("typeof Chart!=='undefined'", text)


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

    def test_evaluator_dashboard_uses_distinct_ids_when_own_proposal_is_in_review_queue(self):
        """Regression test: review queue cards must never collide with own-proposal gauge IDs."""
        from proposals.models import ProposalEvaluatorAssignment, ProposalReviewRound

        director, _ = factories.director('gauge_dir_assigner')
        evaluator, client = factories.evaluator('gauge_eval_unique')
        proposal = Proposal.objects.create(
            created_by=evaluator,
            title='Evaluator Own Submitted Proposal',
            proposal_status=Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
        )
        rr = ProposalReviewRound.objects.create(proposal=proposal)
        ProposalEvaluatorAssignment.objects.create(
            proposal=proposal,
            review_round=rr,
            evaluator=evaluator,
            assigned_by=director,
        )

        response = client.get(reverse('evaluator_dashboard'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn(f'id="gaugeChart-review-{proposal.id}"', html)
        self.assertIn(f'id="gaugeChart{proposal.id}"', html)

        ids = re.findall(r'\bid="([^"]+)"', html)
        duplicates = {item for item in ids if ids.count(item) > 1}
        self.assertEqual(duplicates, set(), f'unexpected duplicate HTML IDs: {duplicates}')

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

    def test_neutral_icon_actions_take_the_app_icon_color(self):
        """Icons use the brand green the rest of the app draws icons in.

        Secondary buttons set a slate text color; icon-only actions must not
        inherit it, or the row icons read as black next to the green nav/tile
        glyphs. Filled primary (white) and destructive (rose) stay semantic.
        """
        css = (settings.BASE_DIR / 'static/css/nexus-components.css').read_text()
        rule = re.search(
            r'\.nx-btn--icon:not\(\.nx-btn--primary\):not\(\.nx-btn--danger\)\s*\{([^}]*)\}',
            css,
        )
        self.assertIsNotNone(rule, 'neutral icon buttons get an explicit icon color')
        self.assertIn('var(--nexus-primary', rule.group(1))
        self.assertNotIn('#334155', rule.group(1))

        # The two semantic variants keep their own glyph color.
        primary = re.search(r'\.nx-btn--primary\s*\{([^}]*)\}', css).group(1)
        danger = re.search(r'\.nx-btn--danger\s*\{([^}]*)\}', css).group(1)
        self.assertIn('color: #fff', primary)
        self.assertIn('color: #9f1239', danger)

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

class _TableParser(HTMLParser):
    """Collect header and body cells per table, with their alignment classes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None
        self._buf = []
        self._in_thead = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get('class') or '').split()
        if tag == 'table':
            self._table = {'headers': [], 'rows': []}
        elif self._table is None:
            return
        elif tag == 'thead':
            self._in_thead = True
        elif tag == 'tr':
            self._row = []
        elif tag in ('th', 'td') and self._row is not None:
            self._cell = {
                'tag': tag,
                'classes': classes,
                'colspan': int(attributes.get('colspan') or 1),
            }
            self._buf = []

    def handle_data(self, data):
        if self._cell is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self._cell is not None:
            self._cell['text'] = ''.join(self._buf).strip()
            self._row.append(self._cell)
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            if self._in_thead:
                self._table['headers'] = self._row
            elif self._row:
                self._table['rows'].append(self._row)
            self._row = None
        elif tag == 'thead':
            self._in_thead = False
        elif tag == 'table' and self._table is not None:
            self.tables.append(self._table)
            self._table = None


class TableAlignmentTests(SimpleTestCase):
    """Headers and body cells agree on one alignment, table after table.

    A header that sits left while its column is centered (or an "Actions"
    heading that is left while the icon buttons hug the right edge) reads as
    a broken table. These tests resolve the same cascade a browser would:
    explicit ``text-*`` utility first, then the shared header classes that
    set left alignment (``nx-th``/``adm-th``), then the element default.
    """

    templates = settings.BASE_DIR / 'accounts/templates'
    details = settings.BASE_DIR / 'details/templates'

    LEFT_BY_CLASS = {'nx-th', 'adm-th', 'proposal-table__title'}
    ACTIONS = {'action', 'actions'}

    def _alignment(self, cell, header):
        for token in ('text-left', 'text-center', 'text-right'):
            if token in cell['classes']:
                return token.split('-', 1)[1]
        if header:
            if self.LEFT_BY_CLASS & set(cell['classes']):
                return 'left'
            # A <thead> th defaults to centered when nothing overrides it.
            return 'center'
        return 'left'

    def _tables(self):
        for root in (self.templates, self.details):
            for path in sorted(root.rglob('*.html')):
                text = path.read_text()
                if '<table' not in text:
                    continue
                parser = _TableParser()
                parser.feed(text)
                for table in parser.tables:
                    if table['headers']:
                        yield path, table

    def test_every_column_header_matches_its_cells(self):
        checked = 0
        for path, table in self._tables():
            width = len(table['headers'])
            rows = [r for r in table['rows'] if len(r) == width and not any(c['colspan'] > 1 for c in r)]
            if not rows:
                continue
            checked += 1
            for index, header in enumerate(table['headers']):
                expected = self._alignment(header, header=True)
                for row in rows:
                    actual = self._alignment(row[index], header=False)
                    with self.subTest(template=str(path.relative_to(settings.BASE_DIR)), column=header['text']):
                        self.assertEqual(
                            actual, expected,
                            f'"{header["text"]}" is {expected}-aligned but its cells are {actual}-aligned',
                        )
        self.assertGreater(checked, 30, 'the audit should cover the whole app, not one page')

    def test_every_actions_column_is_right_aligned(self):
        seen = 0
        for path, table in self._tables():
            width = len(table['headers'])
            for index, header in enumerate(table['headers']):
                if header['text'].lower() not in self.ACTIONS:
                    continue
                seen += 1
                with self.subTest(template=str(path.relative_to(settings.BASE_DIR))):
                    self.assertEqual(self._alignment(header, header=True), 'right')
                    for row in table['rows']:
                        if len(row) != width or row[index]['colspan'] > 1:
                            continue
                        self.assertEqual(self._alignment(row[index], header=False), 'right')
        # 30, down from 31: details/templates/details/admin/process.html was an
        # orphan (no view, and it linked a URL namespace that does not exist) and
        # was removed. Update this number deliberately, never to make a failure go
        # away: it is here to notice a table losing its Actions heading.
        self.assertEqual(seen, 30, 'every Actions column in the app is covered')

    def test_row_cells_share_one_vertical_alignment(self):
        css = (settings.BASE_DIR / 'static/css/nexus-components.css').read_text()
        self.assertIn('.nexus-shell .nx-table th,', css)
        self.assertIn('.nexus-shell .nx-table td { vertical-align: middle; }', css)
        # Header typography must not leak into <th scope="row"> data cells.
        self.assertNotIn('.nexus-shell .nx-table th {', css)
        self.assertIn('.nexus-shell .nx-table thead th {', css)

class IconButtonCenteringTests(SimpleTestCase):
    """Icon buttons are exact squares with the glyph centred on both axes."""

    css = settings.BASE_DIR / 'static/css/nexus-components.css'

    def _rule(self, body):
        css = self.css.read_text()
        match = re.search(body + r'\s*\{([^}]*)\}', css)
        self.assertIsNotNone(match, f'missing rule for {body}')
        return match.group(1)

    def test_icon_buttons_have_no_padding_and_centre_their_glyph(self):
        base = self._rule(r'\.nexus-shell \.nx-btn--icon')
        # A padded square drifts when the glyph size changes.
        self.assertIn('padding: 0;', base)
        self.assertIn('justify-content: center;', base)
        self.assertIn('align-items: center;', base)

        # The compact variant inherits the centring from the base class.
        compact = self._rule(r'\.nexus-shell \.nx-btn--icon\.nx-btn--compact')
        self.assertIn('padding: 0;', compact)

    def test_icon_buttons_are_square(self):
        for selector in (
            r'\.nexus-shell \.nx-btn--icon',
            r'\.nexus-shell \.nx-btn--icon\.nx-btn--compact',
        ):
            rule = self._rule(selector)
            widths = re.findall(r'(?:^|;)\s*width: (var\(--nx-control-[a-z]+\));', rule)
            heights = re.findall(r'min-height: (var\(--nx-control-[a-z]+\));', rule)
            self.assertTrue(widths, f'{selector} sets a width')
            self.assertTrue(heights, f'{selector} sets a min-height')
            self.assertEqual(widths[0], heights[0], 'width and height use the same token')

    def test_every_icon_button_holds_exactly_one_glyph_and_no_text(self):
        for path in sorted((settings.BASE_DIR / 'accounts/templates').rglob('*.html')):
            text = path.read_text()
            if 'nx-btn--icon' not in text:
                continue
            parser = _TableParser()
            parser.feed(text)
            # A text glyph inside an icon button would not sit on the icon grid.
            for match in re.finditer(r'<(?:a|button)\b[^>]*nx-btn--icon[^>]*>(.*?)</(?:a|button)>', text, re.S):
                body = match.group(1)
                with self.subTest(template=str(path.relative_to(settings.BASE_DIR))):
                    self.assertEqual(len(re.findall(r'<svg\b', body)), 1, 'exactly one glyph')
                    self.assertNotRegex(re.sub(r'<[^>]+>', '', body).strip(), r'\S', 'no text label inside')

    def test_row_action_groups_centre_their_members(self):
        rule = self._rule(r'\.nexus-shell \.nx-actions')
        self.assertIn('align-items: center;', rule)
