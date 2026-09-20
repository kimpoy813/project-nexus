from django.test import TestCase
from django.urls import reverse
from details.models import ProposalWizardStepConfig
from . import factories


class WizardAdminTests(TestCase):
    def setUp(self):
        self.admin_user, self.admin_client = factories.admin()

    def test_manager_seeds_defaults_if_empty(self):
        ProposalWizardStepConfig.objects.all().delete()
        self.assertEqual(ProposalWizardStepConfig.objects.count(), 0)

        response = self.admin_client.get(reverse("wizard_steps_manager"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ProposalWizardStepConfig.objects.count() >= 20)

    def test_create_and_delete_wizard_step(self):
        self.admin_client.get(reverse("wizard_steps_manager"))
        initial_count = ProposalWizardStepConfig.objects.count()

        # Create step 100
        response = self.admin_client.post(reverse("wizard_step_create"), {
            "step_no": 100,
            "title": "Custom Test Step",
            "description": "This is a custom test step",
            "instructions": "Please follow instructions for step 100.",
            "is_visible": "on",
            "is_required": "on"
        })
        self.assertEqual(response.status_code, 302) # Redirects to manager
        self.assertEqual(ProposalWizardStepConfig.objects.count(), initial_count + 1)

        # Verify step 100 exists
        step_100 = ProposalWizardStepConfig.objects.get(step_no=100)
        self.assertEqual(step_100.title, "Custom Test Step")
        self.assertEqual(step_100.description, "This is a custom test step")
        self.assertTrue(step_100.is_visible)
        self.assertTrue(step_100.is_required)

        # Delete step 100
        response = self.admin_client.post(reverse("wizard_step_delete", args=[100]))
        self.assertEqual(response.status_code, 302) # Redirects to manager
        self.assertEqual(ProposalWizardStepConfig.objects.count(), initial_count)
        self.assertFalse(ProposalWizardStepConfig.objects.filter(step_no=100).exists())

    def test_create_legacy_proposal(self):
        # Create a legacy proposal
        response = self.admin_client.post(reverse("admin_legacy_proposal_create"), {
            "title": "My Historical Proposal",
            "extension_type": "REQUEST_BASED",
            "scope_type": "PROJECT",
            "campus": "Candon",
            "college": "College of Computing",
            "department": "BSCS",
            "implementing_agency": "ISPSC CTE",
            "beneficiaries_count": 100,
            "beneficiaries_who": "Barangay residents",
            "estimated_month": "October",
            "estimated_year": 2023,
            "extension_venue": "San Juan",
            "proposal_status": "APPROVED",
        })
        self.assertEqual(response.status_code, 302) # Redirects to admin dashboard
        
        from proposals.models import Proposal
        prop = Proposal.objects.get(title="My Historical Proposal")
        self.assertTrue(prop.is_legacy)
        self.assertEqual(prop.proposal_status, "APPROVED")
