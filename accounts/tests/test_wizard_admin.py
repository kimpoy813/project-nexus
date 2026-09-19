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
        self.assertTrue(ProposalWizardStepConfig.objects.count() >= 19)

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


class WizardStepManagerTests(TestCase):
    """The screens the office uses to reshape the wizards."""

    def setUp(self):
        self.admin_user, self.admin_client = factories.admin("mgr_admin")

    def test_the_manager_lists_every_step_with_its_part(self):
        response = self.admin_client.get(reverse("wizard_steps_manager"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Proposal Wizard Steps")
        self.assertContains(response, "Rationale / Background")
        # Every step names the built-in part it renders...
        self.assertContains(response, "Extension Type and Scope")
        # ...and the manager can move it.
        self.assertContains(response, reverse("wizard_step_move", args=[1]))

    def test_the_manager_marks_a_step_the_office_built_itself(self):
        ProposalWizardStepConfig.objects.create(
            step_no=20, order=20, section_key="", title="Partner Clearance",
            is_visible=True, is_required=True,
        )

        response = self.admin_client.get(reverse("wizard_steps_manager"))

        self.assertContains(response, "Partner Clearance")
        self.assertContains(response, "Office-built only")

    def test_the_moa_manager_lists_the_moa_steps(self):
        response = self.admin_client.get(reverse("moa_wizard_steps_manager"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MOA Drafting Wizard Steps")
        self.assertContains(response, "Parties and Signatories")

    def test_the_step_editor_offers_the_parts_and_the_form_picker(self):
        response = self.admin_client.get(reverse("wizard_step_edit", args=[11]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="section_key"')
        self.assertContains(response, 'name="attachment_picker"')
        self.assertContains(response, 'value="rationale_background"')
        self.assertContains(response, "Office-built forms only")

    def test_moving_a_step_through_the_manager_reorders_it(self):
        self.admin_client.get(reverse("wizard_steps_manager"))
        before = list(
            ProposalWizardStepConfig.objects.order_by("order", "step_no")
            .values_list("step_no", flat=True)
        )

        response = self.admin_client.post(
            reverse("wizard_step_move", args=[11]), {"direction": "up"}
        )

        self.assertEqual(response.status_code, 302)
        after = list(
            ProposalWizardStepConfig.objects.order_by("order", "step_no")
            .values_list("step_no", flat=True)
        )
        self.assertEqual(sorted(after), sorted(before))
        self.assertEqual(after.index(11), before.index(11) - 1)

    def test_an_admin_form_can_be_attached_to_a_step_from_the_editor(self):
        from details.models import DynamicFormTemplate

        form = DynamicFormTemplate.objects.create(
            name="Partner clearance",
            slug="partner-clearance",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            is_active=True,
        )

        self.admin_client.post(
            reverse("wizard_step_edit", args=[12]),
            {
                "title": "Significance",
                "description": "Importance of the proposed extension",
                "instructions": "",
                "section_key": "significance",
                "is_visible": "on",
                "is_required": "on",
                "attachment_picker": "1",
                "attached_form_ids": [str(form.id)],
                "field_id[]": [], "field_label[]": [], "field_key[]": [],
                "field_type[]": [], "field_placeholder[]": [], "field_help_text[]": [],
                "field_choices[]": [], "field_depends_on_key[]": [],
                "field_depends_on_value[]": [], "field_maps_to[]": [], "field_required[]": [],
            },
        )

        step = ProposalWizardStepConfig.objects.get(step_no=12)
        self.assertIn(step, form.attached_proposal_steps.all())

    def test_only_an_admin_can_open_the_builders(self):
        faculty_user, faculty_client = factories.faculty("mgr_faculty")

        for url in [
            reverse("wizard_steps_manager"),
            reverse("moa_wizard_steps_manager"),
            reverse("wizard_step_edit", args=[1]),
            reverse("moa_wizard_step_create"),
        ]:
            with self.subTest(url=url):
                self.assertIn(faculty_client.get(url).status_code, (302, 403))
