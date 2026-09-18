"""
Tests for the reconstructed (fully dynamic) proposal wizard steps.

Every step now has a *layout* (``ProposalWizardStepConfig.layout``):

* ``BUILTIN`` - the step keeps its classic system form; admin-built fields are
  extra questions. The seeded mirror fields (``extension_type``, ``title``,
  ...) are label overrides: they must render inside the system form's own
  inputs and must NEVER block the step - the bug these tests pin is that a
  fresh install's Step 1 could not be saved at all, because the seeded
  required mirrors were validated twice and never satisfied.
* ``DYNAMIC`` - the step shows only the admin-built form. A field mapped to a
  proposal column (``maps_to_proposal``) also writes that column, so the
  generated DOCX forms, review screens, and dashboards keep reading the value
  after the office rebuilds a step.

The admin-facing behaviour (the no-code manager persisting the layout, new
steps defaulting to custom) is covered here too.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import (
    DynamicFormField,
    DynamicFormResponse,
    DynamicFormTemplate,
    ProposalWizardStepConfig,
)

from .models import Proposal
from .views.wizard import is_step_complete
from .views.wizard_builtin import uses_builtin_form


def _seed_wizard():
    """Seed the step configs exactly like the wizard view does on first use."""
    from .views.wizard import _wizard_step_config_map

    return _wizard_step_config_map()


class FreshInstallWizardTests(TestCase):
    """A brand-new database must work before any admin touches the builder."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("fresh_owner", Profile.ROLE_FACULTY)

    def test_the_nineteen_steps_default_to_their_builtin_forms(self):
        _seed_wizard()
        for step_no in range(1, 20):
            self.assertTrue(
                uses_builtin_form(step_no),
                f"step {step_no} should keep its built-in form out of the box",
            )

    def test_step_one_saves_on_a_fresh_install(self):
        """Regression: required mirror fields used to block Step 1 forever."""
        _seed_wizard()
        proposal = Proposal.objects.create(created_by=self.owner, current_step=1)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("proposal_wizard", args=[proposal.id, 1]),
            {
                "extension_type": "REQUEST_BASED",
                "scope_type": "PROJECT",
                "action": "next",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/step/2/", response.url)

        proposal.refresh_from_db()
        self.assertEqual(proposal.completed_steps, [1])
        self.assertEqual(proposal.extension_type, "REQUEST_BASED")
        self.assertEqual(proposal.scope_type, "PROJECT")

    def test_mirror_fields_never_render_as_duplicate_inputs(self):
        """Regression: a step whose only fields are mirrors used to fall back
        to rendering *all* of them (Django's ``default`` filter fires on an
        empty list), printing the system form's inputs twice."""
        _seed_wizard()
        proposal = Proposal.objects.create(created_by=self.owner, current_step=1)
        self.client.force_login(self.owner)

        response = self.client.get(reverse("proposal_wizard", args=[proposal.id, 1]))
        body = response.content.decode()
        self.assertNotIn('name="dynamic_field_', body)
        # The system form's own inputs are there exactly once.
        self.assertIn('name="extension_type"', body)
        self.assertIn('name="scope_type"', body)
        # And no empty "additional fields" box is printed.
        self.assertNotIn("Admin-managed requirements", body)

    def test_mirror_fields_do_not_block_submission(self):
        _seed_wizard()
        proposal = Proposal.objects.create(created_by=self.owner, current_step=1)
        proposal.extension_type = "REQUEST_BASED"
        proposal.scope_type = "PROJECT"
        proposal.title = "Fresh install proposal"
        proposal.implementing_agency = "ISPSC Extension Unit"
        proposal.beneficiaries_count = 10
        proposal.beneficiaries_who = "Barangay residents"
        proposal.budgetary_requirement = "Internal funds"
        proposal.extension_venue = "Candon City"
        proposal.rationale_background = "Because."
        proposal.significance = "Very."
        proposal.general_objective = "Help."
        proposal.save()

        from .views.dynamic_answers import _proposal_dynamic_requirements_missing

        self.assertEqual(_proposal_dynamic_requirements_missing(proposal), [])

    def test_seeded_mirror_fields_carry_their_proposal_mapping(self):
        _seed_wizard()
        step_one_form = DynamicFormTemplate.objects.get(proposal_wizard_step=1)
        mapped = {
            f.field_key: f.maps_to_proposal
            for f in step_one_form.fields.all()
        }
        self.assertEqual(mapped["extension_type"], "extension_type")
        self.assertEqual(mapped["scope_type"], "scope_type")
        self.assertEqual(mapped["research_title"], "research_title")


class BuiltinLayoutStepTests(TestCase):
    """A built-in step keeps its system form; admin fields are extras."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("bi_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        _seed_wizard()
        self.proposal = Proposal.objects.create(created_by=self.owner, current_step=4)
        self.client.force_login(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 4])

        self.form = DynamicFormTemplate.objects.get(proposal_wizard_step=4)
        self.extra = DynamicFormField.objects.create(
            form=self.form,
            label="Office branch",
            field_key="office_branch",
            field_type=DynamicFormField.FieldType.TEXT,
            required=True,
            order=9,
        )

    def test_the_step_renders_its_builtin_input_plus_the_extra_field(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertIn('name="implementing_agency"', body)
        self.assertIn(f'name="dynamic_field_{self.extra.id}"', body)
        # The mirror field is a label override, not a second input.
        mirror = self.form.fields.get(field_key="implementing_agency")
        self.assertNotIn(f'name="dynamic_field_{mirror.id}"', body)

    def test_the_built_in_save_path_still_writes_the_proposal_column(self):
        self.client.post(self.url, {
            "implementing_agency": "ISPSC CTE",
            f"dynamic_field_{self.extra.id}": "Candon",
            "action": "next",
        })
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.implementing_agency, "ISPSC CTE")

    def test_a_required_extra_field_blocks_the_step(self):
        response = self.client.post(self.url, {
            "implementing_agency": "ISPSC CTE",
            f"dynamic_field_{self.extra.id}": "",
            "action": "next",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/step/4/", response.url)  # stays on the step
        self.proposal.refresh_from_db()
        self.assertNotIn(4, self.proposal.completed_steps or [])
        self.assertFalse(is_step_complete(self.proposal, 4))

    def test_filling_the_extra_field_completes_the_step(self):
        self.client.post(self.url, {
            "implementing_agency": "ISPSC CTE",
            f"dynamic_field_{self.extra.id}": "Candon",
            "action": "next",
        })
        self.proposal.refresh_from_db()
        self.assertIn(4, self.proposal.completed_steps)


class CustomLayoutStepTests(TestCase):
    """A step switched to a custom form is entirely admin-managed."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("cu_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        _seed_wizard()
        self.config = ProposalWizardStepConfig.objects.get(step_no=4)
        self.config.layout = ProposalWizardStepConfig.Layout.DYNAMIC
        self.config.save(update_fields=["layout"])

        self.proposal = Proposal.objects.create(
            created_by=self.owner,
            current_step=4,
            implementing_agency="Legacy unit",
        )
        self.client.force_login(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 4])

        # The seeded mirror field is what the office now owns: same label, but
        # rendered by the admin-built form and still writing the same column.
        self.form = DynamicFormTemplate.objects.get(proposal_wizard_step=4)
        self.mapped = self.form.fields.get(field_key="implementing_agency")
        self.mapped.label = "Lead unit"
        self.mapped.required = True
        self.mapped.save(update_fields=["label", "required"])

        # A brand-new unmapped field is a step answer only.
        self.plain = DynamicFormField.objects.create(
            form=self.form,
            label="Office branch",
            field_key="office_branch",
            field_type=DynamicFormField.FieldType.TEXT,
            required=False,
            order=10,
        )
        # A new field may also capture a *different* proposal column.
        self.other_mapped = DynamicFormField.objects.create(
            form=self.form,
            label="Partner unit",
            field_key="partner_unit",
            field_type=DynamicFormField.FieldType.TEXT,
            required=False,
            maps_to_proposal="significance",
            order=11,
        )

    def test_the_built_in_form_is_not_rendered(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertNotIn('name="implementing_agency"', body)
        self.assertIn(f'name="dynamic_field_{self.mapped.id}"', body)
        # Existing data is carried over through the mapping.
        self.assertIn("Legacy unit", body)

    def test_step_uses_the_dynamic_completion_rule(self):
        self.assertFalse(is_step_complete(self.proposal, 4))

    def test_the_mapped_field_writes_the_proposal_column(self):
        response = self.client.post(self.url, {
            f"dynamic_field_{self.mapped.id}": "ISPSC College of Computing",
            f"dynamic_field_{self.plain.id}": "Candon",
            f"dynamic_field_{self.other_mapped.id}": "MOA partner",
            "action": "next",
        })
        self.assertEqual(response.status_code, 302)

        self.proposal.refresh_from_db()
        self.assertEqual(
            self.proposal.implementing_agency, "ISPSC College of Computing"
        )
        self.assertEqual(self.proposal.significance, "MOA partner")
        self.assertIn(4, self.proposal.completed_steps)

        response = DynamicFormResponse.objects.get(
            form=self.form, proposal=self.proposal
        )
        answer = response.answers.get(field=self.mapped)
        self.assertEqual(answer.value, "ISPSC College of Computing")

    def test_a_required_custom_field_blocks_until_filled(self):
        response = self.client.post(self.url, {
            f"dynamic_field_{self.mapped.id}": "",
            f"dynamic_field_{self.plain.id}": "",
            f"dynamic_field_{self.other_mapped.id}": "",
            "action": "next",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/step/4/", response.url)
        self.proposal.refresh_from_db()
        self.assertNotIn(4, self.proposal.completed_steps or [])

        # The submission gate also blocks on it.
        gate_url = reverse("proposal_submit", args=[self.proposal.id])
        self.client.post(gate_url, {})
        # Not submitted: still drafting.
        self.proposal.refresh_from_db()
        self.assertEqual(
            self.proposal.proposal_status, Proposal.ProposalStatus.DRAFTING
        )

    def test_the_int_column_mapping_coerces_numbers(self):
        """Beneficiary-count style columns accept digits; garbage is ignored."""
        self.mapped.maps_to_proposal = "beneficiaries_count"
        self.mapped.field_type = DynamicFormField.FieldType.NUMBER
        self.mapped.save(update_fields=["maps_to_proposal", "field_type"])

        self.client.post(self.url, {
            f"dynamic_field_{self.mapped.id}": "42",
            f"dynamic_field_{self.plain.id}": "",
            f"dynamic_field_{self.other_mapped.id}": "",
            "action": "next",
        })
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.beneficiaries_count, 42)

        # A non-numeric value never reaches the integer column.
        self.client.post(self.url, {
            f"dynamic_field_{self.mapped.id}": "not a number",
            f"dynamic_field_{self.plain.id}": "",
            f"dynamic_field_{self.other_mapped.id}": "",
            "action": "next",
        })
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.beneficiaries_count, 42)

        # An empty value clears it again.
        self.client.post(self.url, {
            f"dynamic_field_{self.mapped.id}": "",
            f"dynamic_field_{self.plain.id}": "",
            f"dynamic_field_{self.other_mapped.id}": "",
            "action": "next",
        })
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.beneficiaries_count, None)

    def test_switching_back_to_builtin_keeps_the_entered_data(self):
        self.client.post(self.url, {
            f"dynamic_field_{self.mapped.id}": "Shared services unit",
            f"dynamic_field_{self.plain.id}": "",
            f"dynamic_field_{self.other_mapped.id}": "",
            "action": "next",
        })

        self.config.layout = ProposalWizardStepConfig.Layout.BUILTIN
        self.config.save(update_fields=["layout", "updated_at"])

        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertIn('name="implementing_agency"', body)
        self.assertIn("Shared services unit", body)
        self.assertTrue(is_step_complete(self.proposal, 4))


class CustomStepThreeTests(TestCase):
    """A custom-layout Step 3 still saves its repeatable proponent group."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("cu3_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        _seed_wizard()
        from details.proponent_fields import ensure_proponent_repeater_form

        self.form = ensure_proponent_repeater_form(3)
        self.config = ProposalWizardStepConfig.objects.get(step_no=3)
        self.config.layout = ProposalWizardStepConfig.Layout.DYNAMIC
        self.config.save(update_fields=["layout"])

        self.proposal = Proposal.objects.create(created_by=self.owner, current_step=3)
        self.client.force_login(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 3])

    def _row_data(self, index, name):
        return {
            f"repeater_{self.form.id}_row_id_{index}": "",
            f"repeater_{self.form.id}_row_{index}_field_{self.form.fields.get(field_key='full_name').id}": name,
            f"repeater_{self.form.id}_row_{index}_field_{self.form.fields.get(field_key='role').id}": "Proponent",
            f"repeater_{self.form.id}_rows": "1",
        }

    def test_the_proponent_group_renders_and_saves_on_a_custom_step(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        # The generic repeater renderer is used (not step_3.html's inline one).
        self.assertIn(f'data-form-id="{self.form.id}"', body)

        data = self._row_data(0, "Juan Dela Cruz")
        data["action"] = "next"
        self.client.post(self.url, data)

        self.proposal.refresh_from_db()
        proponents = self.proposal.proponents.filter(user__isnull=True)
        self.assertTrue(proponents.exists())
        self.assertEqual(proponents.first().full_name, "Juan Dela Cruz")

    def test_row_buttons_stay_on_the_step_instead_of_advancing(self):
        from .models import ProposalProponent

        existing = ProposalProponent.objects.create(
            proposal=self.proposal,
            full_name="Maria Santos",
            role="Proponent",
        )
        response = self.client.post(self.url, {
            f"repeater_{self.form.id}_row_id_0": existing.id,
            f"repeater_{self.form.id}_row_0_field_{self.form.fields.get(field_key='full_name').id}": "Maria Santos",
            f"repeater_{self.form.id}_row_0_field_{self.form.fields.get(field_key='role').id}": "Proponent",
            f"repeater_{self.form.id}_rows": "1",
            f"repeater_{self.form.id}_remove": str(existing.id),
            "action": "save_members",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/step/3/", response.url)


class WizardLayoutAdminTests(TestCase):
    """The no-code manager owns the step layout."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user, cls.admin_client = factories.admin()

    def test_editing_a_step_persists_the_layout(self):
        _seed_wizard()
        step4 = ProposalWizardStepConfig.objects.get(step_no=4)
        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[4]),
            {
                "title": step4.title,
                "description": step4.description,
                "instructions": "",
                "layout": "DYNAMIC",
                "is_visible": "on",
                "is_required": "on",
                # keep the seeded field rows as they are
                "field_id[]": [str(f.id) for f in step4 and DynamicFormTemplate.objects.get(proposal_wizard_step=4).fields.all()],
                "field_label[]": ["Implementing Agency / Unit"],
                "field_key[]": ["implementing_agency"],
                "field_type[]": ["TEXT"],
                "field_placeholder[]": [""],
                "field_help_text[]": [""],
                "field_choices[]": [""],
                "field_depends_on_key[]": [""],
                "field_depends_on_value[]": [""],
                "field_maps_to[]": [""],
                "field_maps_to_proposal[]": ["implementing_agency"],
            },
        )
        self.assertEqual(response.status_code, 302)
        step4.refresh_from_db()
        self.assertEqual(
            step4.layout, ProposalWizardStepConfig.Layout.DYNAMIC
        )

        field = DynamicFormTemplate.objects.get(
            proposal_wizard_step=4
        ).fields.get(field_key="implementing_agency")
        self.assertEqual(field.maps_to_proposal, "implementing_agency")

    def test_builtin_layout_is_rejected_for_a_step_without_a_system_form(self):
        _seed_wizard()
        step20 = ProposalWizardStepConfig.objects.create(
            step_no=20,
            title="Extra office checklist",
            layout=ProposalWizardStepConfig.Layout.BUILTIN,
        )
        self.admin_client.post(
            reverse("wizard_step_edit", args=[20]),
            {
                "title": step20.title,
                "description": "",
                "instructions": "",
                "layout": "BUILTIN",
                "is_visible": "on",
                "is_required": "on",
            },
        )
        step20.refresh_from_db()
        self.assertEqual(
            step20.layout, ProposalWizardStepConfig.Layout.DYNAMIC
        )

    def test_new_steps_default_to_a_custom_form(self):
        _seed_wizard()
        response = self.admin_client.post(
            reverse("wizard_step_create"),
            {
                "step_no": 21,
                "title": "New office form",
                "description": "",
                "instructions": "",
                "is_visible": "on",
                "is_required": "on",
                # no layout in the POST: the default must apply
                "field_label[]": [""],
            },
        )
        self.assertEqual(response.status_code, 302)
        step21 = ProposalWizardStepConfig.objects.get(step_no=21)
        self.assertEqual(
            step21.layout, ProposalWizardStepConfig.Layout.DYNAMIC
        )
        self.assertFalse(uses_builtin_form(21))

    def test_the_manager_lists_the_content_type_per_step(self):
        _seed_wizard()
        # One rebuilt step so both badges appear.
        ProposalWizardStepConfig.objects.filter(step_no=12).update(
            layout=ProposalWizardStepConfig.Layout.DYNAMIC
        )
        response = self.admin_client.get(reverse("wizard_steps_manager"))
        body = response.content.decode()
        self.assertIn("Custom form", body)
        self.assertIn("Built-in form", body)
