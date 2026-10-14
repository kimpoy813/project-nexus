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
