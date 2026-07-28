"""
Proposal lifecycle tests.

Covers the progress model that drives every dashboard percentage and the
Services page, plus access control on the proposal wizard.

Note: this file previously contained two tests referencing
``Proposal.mark_implementation_in_progress()`` and a ``proposal_moa_workflow``
URL. Neither exists any more — both had been renamed in an earlier refactor
and the tests had been failing ever since. They are replaced here with tests
written against the current API.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories

from .models import Proposal


User = get_user_model()


class ProposalProgressTests(TestCase):
    """``overall_progress`` weights the three phases differently."""

    def setUp(self):
        self.user = factories.make_user("prop_owner", Profile.ROLE_FACULTY)

    def test_a_new_proposal_starts_at_the_drafting_status(self):
        proposal = Proposal.objects.create(created_by=self.user)
        self.assertEqual(proposal.proposal_status, Proposal.ProposalStatus.DRAFTING)

    def test_proposal_progress_follows_the_status_map(self):
        proposal = Proposal.objects.create(created_by=self.user)

        for status, expected in Proposal.PROPOSAL_PROGRESS_MAP.items():
            with self.subTest(status=status):
                proposal.proposal_status = status
                self.assertEqual(proposal.proposal_progress, expected)

    def test_progress_is_split_50_50_when_no_moa_is_required(self):
        proposal = Proposal.objects.create(created_by=self.user, requires_moa=False)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.NOT_STARTED

        # 100 * 0.50 + 0 * 0.50
        self.assertEqual(proposal.overall_progress, 50)

    def test_progress_is_split_40_20_40_when_an_moa_is_required(self):
        proposal = Proposal.objects.create(created_by=self.user, requires_moa=True)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.moa_status = Proposal.MOAStatus.NOT_STARTED
        proposal.implementation_status = Proposal.ImplementationStatus.NOT_STARTED

        # 100 * 0.40 + 0 * 0.20 + 0 * 0.40
        self.assertEqual(proposal.overall_progress, 40)

    def test_a_fully_completed_proposal_reaches_100_percent(self):
        proposal = Proposal.objects.create(created_by=self.user, requires_moa=True)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.moa_status = Proposal.MOAStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED

        self.assertEqual(proposal.overall_progress, 100)

    def test_cancelled_and_rejected_proposals_report_zero(self):
        for status in [Proposal.OverallStatus.REJECTED, Proposal.OverallStatus.CANCELLED]:
            with self.subTest(status=status):
                proposal = Proposal.objects.create(created_by=self.user)
                proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
                proposal.status = status
                self.assertEqual(proposal.overall_progress, 0)

    def test_progress_never_exceeds_100(self):
        proposal = Proposal.objects.create(created_by=self.user, requires_moa=True)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.moa_status = Proposal.MOAStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED

        self.assertLessEqual(proposal.overall_progress, 100)


class ProposalPhaseLabelTests(TestCase):
    def setUp(self):
        self.user = factories.make_user("phase_owner", Profile.ROLE_FACULTY)

    def test_a_new_proposal_is_in_the_proposal_phase(self):
        proposal = Proposal.objects.create(created_by=self.user)
        self.assertEqual(proposal.current_phase_label, "Proposal")

    def test_a_proposal_moves_to_the_moa_phase_once_moa_work_starts(self):
        proposal = Proposal.objects.create(created_by=self.user, requires_moa=True)
        proposal.moa_status = Proposal.MOAStatus.DRAFT
        self.assertEqual(proposal.current_phase_label, "MOA")

    def test_a_proposal_moves_to_implementation_once_implementation_starts(self):
        proposal = Proposal.objects.create(created_by=self.user, requires_moa=True)
        proposal.moa_status = Proposal.MOAStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.IMPLEMENTATION
        self.assertEqual(proposal.current_phase_label, "Implementation")

    def test_a_completed_proposal_reports_as_finished(self):
        proposal = Proposal.objects.create(created_by=self.user)
        proposal.status = Proposal.OverallStatus.COMPLETED
        self.assertEqual(proposal.current_phase_label, "Extension Finished")


class ProposalAccessTests(TestCase):
    """Proposals must not be readable or editable by unrelated users."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("acc_owner", Profile.ROLE_FACULTY)
        cls.other = factories.make_user("acc_other", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_anonymous_users_cannot_open_the_wizard(self):
        response = self.client.get(
            reverse("proposal_wizard", args=[self.proposal.id, 1])
        )
        self.assertIn(response.status_code, (302, 403))

    def test_the_owner_can_open_their_own_proposal(self):
        client = factories.make_client(self.owner)
        response = client.get(reverse("proposal_wizard", args=[self.proposal.id, 1]))
        self.assertIn(response.status_code, (200, 302))

    def test_an_unrelated_user_cannot_open_someone_elses_proposal(self):
        client = factories.make_client(self.other)
        response = client.get(reverse("proposal_wizard", args=[self.proposal.id, 1]))
        self.assertIn(response.status_code, (302, 403, 404))

    def test_the_services_page_is_public(self):
        self.assertEqual(self.client.get(reverse("services_home")).status_code, 200)


class ProposalCreationTests(TestCase):
    def test_creating_a_proposal_requires_login(self):
        response = self.client.get(reverse("proposal_create"))
        self.assertIn(response.status_code, (302, 403))

    def test_a_logged_in_user_can_reach_the_create_view(self):
        user = factories.make_user("create_user", Profile.ROLE_FACULTY)
        client = factories.make_client(user)

        response = client.get(reverse("proposal_create"))
        self.assertIn(response.status_code, (200, 302))
