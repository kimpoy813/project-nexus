from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Proposal


User = get_user_model()


class MOAAndImplementationWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", email="tester@example.com", password="secret123")
        self.proposal = Proposal.objects.create(created_by=self.user, requires_moa=True)

    def test_implementation_status_can_move_to_implementation_stage(self):
        self.proposal.mark_implementation_in_progress()
        self.proposal.refresh_from_db()

        self.assertEqual(
            self.proposal.implementation_status,
            Proposal.ImplementationStatus.IMPLEMENTATION,
        )

    def test_moa_workflow_view_updates_status(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("proposal_moa_workflow", args=[self.proposal.id]),
            {"action": "legal_review"},
        )

        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.moa_status, Proposal.MOAStatus.LEGAL_REVIEW)
