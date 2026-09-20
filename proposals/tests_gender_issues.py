"""Tests for the predefined, multi-select Gender Issues / Mandates checklist."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from proposals.models import Proposal, ProposalGenderIssue
from proposals.views.constants import GENDER_ISSUE_LIST
from proposals.views.wizard import is_step_complete


class GenderIssuesChecklistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("gender_checklist_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 10])

    def test_the_step_has_only_predefined_multi_select_choices(self):
        response = self.client_owner.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "you may select more than one")
        self.assertNotContains(response, 'value="others"')
        self.assertNotContains(response, "Others Description")
        self.assertNotContains(response, "gender_issue_other_text")
        self.assertEqual(
            response.content.decode().count('name="gender_issue_keys"'),
            len(GENDER_ISSUE_LIST),
        )

    def test_multiple_predefined_choices_are_saved(self):
        selected = [GENDER_ISSUE_LIST[0][0], GENDER_ISSUE_LIST[2][0]]
        response = self.client_owner.post(
            self.url,
            {
                "action": "next",
                "gender_issue_keys": selected,
            },
        )
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 11]),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            set(
                ProposalGenderIssue.objects.filter(proposal=self.proposal).values_list(
                    "issue_key", flat=True
                )
            ),
            set(selected),
        )
        self.assertTrue(is_step_complete(self.proposal, 10))

    def test_the_removed_other_choice_is_ignored_if_submitted_by_an_old_client(self):
        self.client_owner.post(
            self.url,
            {
                "action": "next",
                "gender_issue_keys": ["others", GENDER_ISSUE_LIST[1][0]],
                "gender_issue_other_text": "A user-entered issue",
            },
        )
        self.assertEqual(
            list(
                ProposalGenderIssue.objects.filter(proposal=self.proposal).values_list(
                    "issue_key", flat=True
                )
            ),
            [GENDER_ISSUE_LIST[1][0]],
        )
