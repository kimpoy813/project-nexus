import json

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

    def _ordered_step_nos(self):
        return list(
            ProposalWizardStepConfig.objects.order_by("display_order", "step_no").values_list(
                "step_no", flat=True
            )
        )

    def test_the_manager_offers_drag_handles_for_reordering(self):
        response = self.admin_client.get(reverse("wizard_steps_manager"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "wizard-steps-list")
        self.assertContains(response, "js-step-handle")
        self.assertContains(response, "sortablejs")
        self.assertContains(response, reverse("wizard_steps_reorder"))

    def test_steps_can_be_reordered(self):
        self.admin_client.get(reverse("wizard_steps_manager"))
        original = self._ordered_step_nos()
        self.assertGreaterEqual(len(original), 3)
        rotated = original[1:] + original[:1]

        response = self.admin_client.post(
            reverse("wizard_steps_reorder"),
            data=json.dumps({"step_nos": rotated}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(self._ordered_step_nos(), rotated)

    def test_reordering_changes_the_wizard_sequence(self):
        from accounts.models import Profile
        from proposals.models import Proposal
        from proposals.views.wizard import (
            get_visible_wizard_step_numbers,
            next_visible_wizard_step,
        )

        self.admin_client.get(reverse("wizard_steps_manager"))
        original = self._ordered_step_nos()
        self.assertIn(6, original)
        new_order = [6] + [no for no in original if no != 6]

        self.admin_client.post(
            reverse("wizard_steps_reorder"),
            data=json.dumps({"step_nos": new_order}),
            content_type="application/json",
        )

        visible = get_visible_wizard_step_numbers()
        self.assertEqual(visible[0], 6)
        self.assertEqual(next_visible_wizard_step(6), new_order[1])

        owner = factories.make_user("wiz_order_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=owner)
        html = factories.make_client(owner).get(
            reverse("proposal_wizard", args=[proposal.id, 6])
        ).content.decode()
        first_title = ProposalWizardStepConfig.objects.get(step_no=6).title
        second_title = ProposalWizardStepConfig.objects.get(step_no=new_order[1]).title
        title_index = html.find(first_title)
        second_index = html.find(second_title)
        self.assertNotEqual(title_index, -1)
        self.assertNotEqual(second_index, -1)
        self.assertLess(title_index, second_index)

    def test_a_partial_reorder_payload_is_rejected(self):
        self.admin_client.get(reverse("wizard_steps_manager"))
        original = self._ordered_step_nos()
        response = self.admin_client.post(
            reverse("wizard_steps_reorder"),
            data=json.dumps({"step_nos": original[:2]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._ordered_step_nos(), original)

    def test_non_admins_cannot_reorder_wizard_steps(self):
        from accounts.models import Profile

        self.admin_client.get(reverse("wizard_steps_manager"))
        original = self._ordered_step_nos()
        faculty = factories.make_user("wiz_order_faculty", Profile.ROLE_FACULTY)
        client = factories.make_client(faculty)
        response = client.post(
            reverse("wizard_steps_reorder"),
            data=json.dumps({"step_nos": list(reversed(original))}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(self._ordered_step_nos(), original)

    def test_a_new_step_is_appended_to_the_sequence(self):
        self.admin_client.get(reverse("wizard_steps_manager"))
        highest = (
            ProposalWizardStepConfig.objects.order_by("-display_order").first().display_order
        )
        self.admin_client.post(
            reverse("wizard_step_create"),
            {
                "step_no": 100,
                "title": "Trailing custom step",
                "description": "Should appear last",
                "is_visible": "on",
                "is_required": "on",
            },
        )
        created = ProposalWizardStepConfig.objects.get(step_no=100)
        self.assertEqual(created.display_order, highest + 1)
        self.assertEqual(self._ordered_step_nos()[-1], 100)
