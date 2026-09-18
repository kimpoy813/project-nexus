"""
The wizard follows the admin's layout, not hardcoded step numbers.

Before this suite, ``step == 7`` meant "budget" in four different places, so
renaming step 7 worked but moving, removing, or replacing it did not. These
tests pin the new contract: a step's behaviour comes from the *section* the
admin configured on it.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import DynamicFormField, DynamicFormTemplate, ProposalWizardStepConfig

from .models import Proposal
from .views.dynamic_answers import _proposal_dynamic_requirements_missing
from .views.sections import SECTIONS, section_key_for_step
from .views.wizard import is_step_complete
from .views.wizard_config import assign_section, ensure_wizard_steps, step_form


def _wizard(proposal, step):
    return reverse("proposal_wizard", args=[proposal.id, step])


class SectionRegistryTests(TestCase):
    def test_every_built_in_step_maps_to_a_registered_section(self):
        from details.wizard_defaults import DEFAULT_WIZARD_STEPS

        for _no, key, _title, _desc in DEFAULT_WIZARD_STEPS:
            with self.subTest(section=key):
                self.assertIn(key, SECTIONS)

    def test_every_section_has_a_template(self):
        from django.template.loader import get_template

        for key, section in SECTIONS.items():
            with self.subTest(section=key):
                get_template(section.template)

    def test_fresh_database_seeds_sections_onto_the_default_steps(self):
        ensure_wizard_steps()
        self.assertEqual(section_key_for_step(1), "extension_type")
        self.assertEqual(section_key_for_step(3), "proponents")
        self.assertEqual(section_key_for_step(19), "certificate")

    def test_seeding_gives_native_fields_to_sections_that_declare_them(self):
        ensure_wizard_steps()
        form = step_form(ProposalWizardStepConfig.objects.get(step_no=7), create=False)
        self.assertEqual(list(form.fields.values_list("field_key", flat=True)), ["budgetary_requirement"])


class NativeFieldsAreNotDoubleValidatedTests(TestCase):
    """The bug that motivated the rewrite.

    Seeded "native" fields (extension_type, title, ...) are rendered and saved
    by the section, but the dynamic-answer gate also required a
    ``dynamic_field_<id>`` answer for them - which the page never posts. On
    a fresh install "Save & Next" on Step 1 therefore bounced straight back.
    """

    def setUp(self):
        self.owner = factories.make_user("nf_owner", Profile.ROLE_FACULTY)
        self.client_owner = factories.make_client(self.owner)
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_saving_step_one_advances_and_marks_it_complete(self):
        self.client_owner.get(_wizard(self.proposal, 1))
        response = self.client_owner.post(
            _wizard(self.proposal, 1),
            {"extension_type": "REQUEST_BASED", "scope_type": "PROJECT", "action": "next"},
        )
        self.assertRedirects(response, _wizard(self.proposal, 2), fetch_redirect_response=False)
        self.proposal.refresh_from_db()
        self.assertIn(1, self.proposal.completed_steps)

    def test_native_fields_do_not_appear_in_the_submission_gate(self):
        ensure_wizard_steps()
        self.proposal.extension_type = "REQUEST_BASED"
        self.proposal.scope_type = "PROJECT"
        self.proposal.save()
        missing = _proposal_dynamic_requirements_missing(self.proposal)
        self.assertEqual([m for m in missing if "Extension Type" in m or "Title" in m], [])

    def test_an_admin_added_required_field_still_blocks(self):
        ensure_wizard_steps()
        form = step_form(ProposalWizardStepConfig.objects.get(step_no=7))
        DynamicFormField.objects.create(
            form=form, label="Fund code", field_key="fund_code", required=True, order=9
        )
        self.client_owner.post(
            _wizard(self.proposal, 7),
            {"budgetary_requirement": "LGU 30,000", "action": "next"},
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.budgetary_requirement, "LGU 30,000")
        self.assertNotIn(7, self.proposal.completed_steps)

    def test_unrequiring_a_native_field_relaxes_completion(self):
        ensure_wizard_steps()
        self.proposal.extension_type = "RESEARCH_FACULTY"
        self.proposal.scope_type = "PROJECT"
        self.proposal.save()
        self.assertFalse(is_step_complete(self.proposal, 1))

        form = step_form(ProposalWizardStepConfig.objects.get(step_no=1))
        form.fields.filter(field_key="research_title").update(required=False)
        self.assertTrue(is_step_complete(self.proposal, 1))


class MovableSectionTests(TestCase):
    """A section keeps working wherever the admin puts it."""

    def setUp(self):
        self.owner = factories.make_user("mv_owner", Profile.ROLE_FACULTY)
        self.client_owner = factories.make_client(self.owner)
        self.proposal = Proposal.objects.create(created_by=self.owner)
        ensure_wizard_steps()

    def _move(self, section_key, to_step):
        """Do what the admin editor does: clear the old step, assign the new."""
        for config in ProposalWizardStepConfig.objects.filter(section_key=section_key):
            assign_section(config, "")
        assign_section(ProposalWizardStepConfig.objects.get(step_no=to_step), section_key)

    def test_budget_moved_to_step_two_saves_from_step_two(self):
        self._move("budget", 2)
        response = self.client_owner.get(_wizard(self.proposal, 2))
        self.assertContains(response, 'name="budgetary_requirement"')

        self.client_owner.post(_wizard(self.proposal, 2), {"budgetary_requirement": "CTE Fund", "action": "next"})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.budgetary_requirement, "CTE Fund")
        self.assertIn(2, self.proposal.completed_steps)

    def test_the_old_step_no_longer_saves_the_moved_section(self):
        self._move("budget", 2)
        self.client_owner.post(_wizard(self.proposal, 7), {"budgetary_requirement": "ignored", "action": "next"})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.budgetary_requirement, "")

    def test_moving_a_section_swaps_the_native_fields_on_both_forms(self):
        self._move("budget", 2)
        keys_on_2 = set(step_form(ProposalWizardStepConfig.objects.get(step_no=2)).fields.values_list("field_key", flat=True))
        keys_on_7 = set(step_form(ProposalWizardStepConfig.objects.get(step_no=7)).fields.values_list("field_key", flat=True))
        self.assertIn("budgetary_requirement", keys_on_2)
        self.assertNotIn("title", keys_on_2)
        self.assertNotIn("budgetary_requirement", keys_on_7)

    def test_moving_a_section_keeps_the_admins_extra_fields(self):
        form2 = step_form(ProposalWizardStepConfig.objects.get(step_no=2))
        DynamicFormField.objects.create(form=form2, label="Acronym", field_key="acronym", required=False, order=5)
        self._move("budget", 2)
        keys = set(form2.fields.values_list("field_key", flat=True))
        self.assertEqual(keys, {"acronym", "budgetary_requirement"})

    def test_proponents_section_follows_its_step(self):
        self._move("proponents", 5)
        response = self.client_owner.get(_wizard(self.proposal, 5))
        self.assertContains(response, "Add Proponent")
        # The repeatable group is created on the new step, not on step 3.
        self.assertTrue(
            DynamicFormTemplate.objects.filter(proposal_wizard_step=5, row_store="PROPONENT").exists()
        )
        self.assertFalse(
            DynamicFormTemplate.objects.filter(proposal_wizard_step=3, row_store="PROPONENT").exists()
        )

    def test_a_step_with_no_section_renders_only_admin_fields(self):
        config = ProposalWizardStepConfig.objects.create(
            step_no=20, section_key="", title="Ethics clearance", description="", is_visible=True, is_required=True
        )
        form = step_form(config)
        DynamicFormField.objects.create(form=form, label="Clearance no.", field_key="clearance_no", required=True, order=1)

        response = self.client_owner.get(_wizard(self.proposal, 20))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ethics clearance")
        self.assertContains(response, "Clearance no.")

        field = form.fields.get(field_key="clearance_no")
        self.client_owner.post(_wizard(self.proposal, 20), {f"dynamic_field_{field.id}": "EC-2026-01", "action": "next"})
        self.proposal.refresh_from_db()
        self.assertIn(20, self.proposal.completed_steps)

    def test_an_empty_custom_step_says_so_instead_of_crashing(self):
        ProposalWizardStepConfig.objects.create(step_no=21, section_key="", title="Placeholder", is_visible=True)
        response = self.client_owner.get(_wizard(self.proposal, 21))
        self.assertContains(response, "This step has no fields yet.")

    def test_step_navigation_skips_hidden_steps(self):
        ProposalWizardStepConfig.objects.filter(step_no=2).update(is_visible=False)
        self.client_owner.get(_wizard(self.proposal, 1))
        response = self.client_owner.post(
            _wizard(self.proposal, 1),
            {"extension_type": "REQUEST_BASED", "scope_type": "PROJECT", "action": "next"},
        )
        self.assertRedirects(response, _wizard(self.proposal, 3), fetch_redirect_response=False)


class AdminSectionEditingTests(TestCase):
    def setUp(self):
        self.admin_user, self.admin_client = factories.admin()
        ensure_wizard_steps()

    def test_step_editor_offers_the_section_picker(self):
        response = self.admin_client.get(reverse("wizard_step_edit", args=[7]))
        self.assertContains(response, 'name="section_key"')
        self.assertContains(response, 'value="budget"')

    def test_admin_can_change_a_steps_section(self):
        ProposalWizardStepConfig.objects.filter(step_no=7).update(section_key="")
        self.admin_client.post(
            reverse("wizard_step_edit", args=[12]),
            {"title": "Budget", "description": "", "instructions": "", "is_visible": "on", "is_required": "on", "section_key": "budget"},
        )
        self.assertEqual(ProposalWizardStepConfig.objects.get(step_no=12).section_key, "budget")

    def test_a_section_cannot_sit_on_two_steps(self):
        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[12]),
            {"title": "Budget again", "is_visible": "on", "is_required": "on", "section_key": "budget"},
            follow=True,
        )
        self.assertContains(response, "already used by Step 7")
        self.assertEqual(ProposalWizardStepConfig.objects.get(step_no=12).section_key, "significance")

    def test_creating_a_fields_only_step(self):
        self.admin_client.post(
            reverse("wizard_step_create"),
            {"step_no": 20, "title": "Ethics", "section_key": "", "is_visible": "on", "is_required": "on"},
        )
        config = ProposalWizardStepConfig.objects.get(step_no=20)
        self.assertTrue(config.is_custom)
        self.assertIsNotNone(step_form(config, create=False))

    def test_manager_lists_unplaced_sections(self):
        ProposalWizardStepConfig.objects.filter(step_no=9).delete()
        response = self.admin_client.get(reverse("wizard_steps_manager"))
        self.assertContains(response, "Built-in sections not on any step")
        self.assertContains(response, "Gender issues / mandates")

    def test_moving_a_step_swaps_numbers_and_carries_fields(self):
        form7 = step_form(ProposalWizardStepConfig.objects.get(step_no=7))
        self.admin_client.post(reverse("wizard_steps_reorder"), {"action": "up", "step_no": 7})
        self.assertEqual(ProposalWizardStepConfig.objects.get(step_no=6).section_key, "budget")
        self.assertEqual(ProposalWizardStepConfig.objects.get(step_no=7).section_key, "sdg_thrust")
        form7.refresh_from_db()
        self.assertEqual(form7.proposal_wizard_step, 6)

    def test_compacting_closes_gaps(self):
        ProposalWizardStepConfig.objects.filter(step_no=2).delete()
        self.admin_client.post(reverse("wizard_steps_reorder"), {"action": "compact"})
        numbers = list(ProposalWizardStepConfig.objects.values_list("step_no", flat=True).order_by("step_no"))
        self.assertEqual(numbers, list(range(1, 19)))
        self.assertEqual(ProposalWizardStepConfig.objects.get(step_no=2).section_key, "proponents")
