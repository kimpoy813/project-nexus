from django.test import TestCase
from django.urls import reverse
from accounts.tests import factories
from proposals.models import Proposal, ProposalCollaborator


class WizardInputValidationTests(TestCase):
    def setUp(self):
        self.owner, self.client = factories.faculty('wizard_input_owner')
        self.proposal = Proposal.objects.create(created_by=self.owner, extension_type='COMMUNITY_BASED', scope_type='ACTIVITY')
        self.url = reverse('proposal_wizard', args=[self.proposal.pk, 1])

    def test_forged_choice_does_not_persist_or_advance(self):
        response = self.client.post(self.url, {'extension_type': "('REQUEST_BASED', 'Request-based')", 'scope_type': 'PROJECT', 'action': 'next'})
        self.assertContains(response, 'Choose a valid extension type.')
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.extension_type, 'COMMUNITY_BASED')
        self.assertEqual(self.proposal.scope_type, 'ACTIVITY')

    def test_missing_research_title_preserves_selected_values_in_the_form(self):
        response = self.client.post(self.url, {'extension_type': 'RESEARCH_FACULTY', 'scope_type': 'PROJECT', 'action': 'next'})
        self.assertContains(response, 'Research Title is required')
        self.assertContains(response, 'id="extensionTypeValue" value="RESEARCH_FACULTY"')
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.extension_type, 'COMMUNITY_BASED')

    def test_readonly_collaborator_sees_no_edit_actions(self):
        viewer, client = factories.faculty('readonly_ui')
        ProposalCollaborator.objects.create(proposal=self.proposal, user=viewer, can_edit=False)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_edit_mode'])
        self.assertNotContains(response, 'Save &amp; Next')
        self.assertNotContains(response, 'Save & Next')

    def test_skip_still_allows_an_unfinished_step(self):
        response = self.client.post(self.url, {'extension_type': '', 'scope_type': '', 'action': 'skip'})
        self.assertEqual(response.status_code, 302)

    def test_readonly_collaborator_cannot_save_by_forging_a_post(self):
        viewer, client = factories.faculty('readonly_post')
        ProposalCollaborator.objects.create(proposal=self.proposal, user=viewer, can_edit=False)
        client.post(self.url, {'extension_type': 'REQUEST_BASED', 'scope_type': 'PROJECT'})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.extension_type, 'COMMUNITY_BASED')

    def test_unrelated_user_still_cannot_read_or_modify_the_proposal(self):
        _, client = factories.faculty('unrelated_viewer')
        self.assertEqual(client.get(self.url).status_code, 302)
        client.post(self.url, {'extension_type': 'REQUEST_BASED', 'scope_type': 'PROJECT'})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.extension_type, 'COMMUNITY_BASED')
