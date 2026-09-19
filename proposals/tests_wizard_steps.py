"""
The configurable wizards.

These tests hold the behaviour the office was given when the two wizards
stopped being hardcoded lists of screens:

* a step's **position** is separate from its **number**, so steps can be
  reordered without breaking anything stored against them;
* a step **names the part** it shows, so its template, its save logic, and its
  completion rule move together when the office re-points it;
* a step with **no part** is built entirely from the office's own forms;
* forms **attach to a step row**, so they follow the step when it moves, and a
  required field in one can hold the step — and submission — open.

They drive the real admin screens and the real wizard views, not the helpers
directly, so a regression in either shows up here.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from django.core.files.uploadedfile import SimpleUploadedFile

from details.models import (
    DynamicFormAnswer,
    DynamicFormField,
    DynamicFormResponse,
    DynamicFormTemplate,
    MOAWizardStepConfig,
    ProposalWizardStepConfig,
)

from .models import Proposal
from .views import is_step_complete
from .views.wizard_flows import moa_flow, proposal_flow


def simple_uploaded_file(name):
    return SimpleUploadedFile(
        name,
        b"PK\x03\x04 stub office document body",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


class WizardStepSeedingTests(TestCase):
    """A fresh install gets both wizards, with every step naming its part."""

    def test_the_proposal_wizard_seeds_nineteen_part_backed_steps(self):
        proposal_flow.ensure_defaults()

        steps = proposal_flow.ordered()

        self.assertEqual(len(steps), 19)
        self.assertEqual([s.section_key for s in steps][:3],
                         ["extension_type", "title", "proponents"])
        self.assertTrue(all(s.order for s in steps))

    def test_the_moa_wizard_seeds_four_part_backed_steps(self):
        moa_flow.ensure_defaults()

        steps = moa_flow.ordered()

        self.assertEqual(len(steps), 4)
        self.assertEqual([s.section_key for s in steps], [
            "agreement_basics",
            "parties_signatories",
            "scope_terms",
            "attachments_review",
        ])

    def test_seeding_never_overwrites_what_the_office_changed(self):
        proposal_flow.ensure_defaults()
        step = ProposalWizardStepConfig.objects.get(step_no=11)
        step.title = "Why this matters"
        step.is_required = False
        step.order = 2
        step.save()

        proposal_flow.ensure_defaults()
        step.refresh_from_db()

        self.assertEqual(step.title, "Why this matters")
        self.assertFalse(step.is_required)
        self.assertEqual(step.order, 2)

    def test_a_step_with_no_row_still_resolves_to_its_default_part(self):
        """Helpers called on an unseeded database must not fall over."""
        ProposalWizardStepConfig.objects.all().delete()

        self.assertEqual(proposal_flow.section(11).key, "rationale_background")
        self.assertEqual(
            proposal_flow.template_for(11), "services/wizard/step_11.html"
        )


class WizardOrderingTests(TestCase):
    """Position and number are different things, and both matter."""

    def setUp(self):
        proposal_flow.ensure_defaults()

    def test_moving_a_step_swaps_positions_and_keeps_numbers(self):
        before = proposal_flow.visible_step_nos()

        self.assertTrue(proposal_flow.move(11, "up"))

        after = proposal_flow.visible_step_nos()
        self.assertEqual(sorted(after), sorted(before), "no step was added or lost")
        self.assertEqual(after.index(11), before.index(11) - 1)

        eleven = ProposalWizardStepConfig.objects.get(step_no=11)
        twelve = ProposalWizardStepConfig.objects.get(step_no=12)
        self.assertEqual(eleven.step_no, 11, "the reference number never changes")
        self.assertLess(eleven.order, twelve.order)

    def test_navigation_follows_the_new_order(self):
        """Steps 11 and 10 swap places; nothing else moves."""
        proposal_flow.move(11, "up")

        self.assertEqual(proposal_flow.step_after(9), 11)
        self.assertEqual(proposal_flow.step_after(11), 10)
        self.assertEqual(proposal_flow.step_after(10), 12)
        self.assertEqual(proposal_flow.step_before(11), 9)

    def test_the_first_step_cannot_move_up_and_the_last_cannot_move_down(self):
        self.assertFalse(proposal_flow.move(1, "up"))
        self.assertFalse(proposal_flow.move(19, "down"))

    def test_hiding_a_step_shortens_the_wizard_without_renumbering(self):
        ProposalWizardStepConfig.objects.filter(step_no=9).update(is_visible=False)

        visible = proposal_flow.visible_step_nos()

        self.assertNotIn(9, visible)
        self.assertIn(10, visible)
        self.assertEqual(proposal_flow.total_visible(), 18)
        self.assertEqual(proposal_flow.position(10), 9)

    def test_the_dashboard_step_count_follows_the_table(self):
        from accounts.views.proposal_queries import _get_total_proposal_steps

        self.assertEqual(_get_total_proposal_steps(), 19)

        ProposalWizardStepConfig.objects.filter(step_no=18).update(is_visible=False)

        self.assertEqual(_get_total_proposal_steps(), 18)


class CustomProposalStepTests(TestCase):
    """A step the office builds itself: no built-in part at all."""

    def setUp(self):
        self.owner = factories.make_user("cw_owner", Profile.ROLE_FACULTY)
        self.client_owner = factories.make_client(self.owner)
        self.admin_user, self.admin_client = factories.admin("cw_admin")
        proposal_flow.ensure_defaults()
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def _create_step(self, **overrides):
        payload = {
            "step_no": "20",
            "title": "Partner Clearance",
            "description": "Clearance from the partner agency",
            "instructions": "Attach the signed clearance.",
            "section_key": "",
            "is_visible": "on",
            "is_required": "on",
            "field_id[]": [], "field_label[]": [], "field_key[]": [],
            "field_type[]": [], "field_placeholder[]": [], "field_help_text[]": [],
            "field_choices[]": [], "field_depends_on_key[]": [],
            "field_depends_on_value[]": [], "field_maps_to[]": [], "field_required[]": [],
        }
        payload.update(overrides)
        return self.admin_client.post(reverse("wizard_step_create"), payload)

    def test_the_office_can_add_a_step_the_code_has_never_heard_of(self):
        response = self._create_step()

        self.assertEqual(response.status_code, 302)
        step = ProposalWizardStepConfig.objects.get(step_no=20)
        self.assertEqual(step.section_key, "")
        self.assertTrue(step.is_visible)

        wizard = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 20])
        )

        self.assertEqual(wizard.status_code, 200)
        self.assertContains(wizard, "Partner Clearance")
        self.assertContains(wizard, "Attach the signed clearance.")
        self.assertEqual(proposal_flow.template_for(20), "services/wizard/step_dynamic.html")

    def test_a_required_field_on_the_new_step_holds_it_open(self):
        self._create_step()
        form = DynamicFormTemplate.objects.create(
            name="Clearance checklist",
            slug="clearance-checklist",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            is_active=True,
            blocks_proposal_submission=True,
        )
        form.attached_proposal_steps.add(ProposalWizardStepConfig.objects.get(step_no=20))
        field = DynamicFormField.objects.create(
            form=form, label="Clearance number", field_key="clearance_no",
            required=True, order=1,
        )

        url = reverse("proposal_wizard", args=[self.proposal.id, 20])

        blocked = self.client_owner.post(url, {"action": "next"}, follow=True)
        self.assertContains(blocked, "Please complete the required admin-managed field(s)")
        self.proposal.refresh_from_db()
        self.assertNotIn(20, self.proposal.completed_steps or [])
        self.assertFalse(is_step_complete(self.proposal, 20))

        self.client_owner.post(
            url, {"action": "next", f"dynamic_field_{field.id}": "CLR-2026-001"}
        )

        self.proposal.refresh_from_db()
        self.assertIn(20, self.proposal.completed_steps or [])
        self.assertTrue(is_step_complete(self.proposal, 20))

    def test_an_attached_required_form_blocks_final_submission(self):
        self._create_step()
        form = DynamicFormTemplate.objects.create(
            name="Clearance checklist",
            slug="clearance-checklist-2",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            is_active=True,
            blocks_proposal_submission=True,
        )
        form.attached_proposal_steps.add(ProposalWizardStepConfig.objects.get(step_no=20))
        DynamicFormField.objects.create(
            form=form, label="Clearance number", field_key="clearance_no",
            required=True, order=1,
        )

        # Every step is done except the office's new requirement.
        self.proposal.completed_steps = proposal_flow.required_step_nos()
        self.proposal.save(update_fields=["completed_steps"])

        response = self.client_owner.get(
            reverse("proposal_submit", args=[self.proposal.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("proposal_wizard", args=[self.proposal.id, 20]))

    def test_the_step_can_be_moved_between_the_built_in_ones(self):
        """The new step lands ahead of the last built-in one, and the wizard agrees."""
        self._create_step()
        self.assertTrue(proposal_flow.move(20, "up"))

        self.assertEqual(proposal_flow.step_after(18), 20)
        self.assertEqual(proposal_flow.step_before(19), 20)
        self.assertEqual(proposal_flow.position(20), 19)

        # "Save & Next" on the office's step now walks into the built-in step
        # that follows it, rather than ending the wizard.
        response = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 20]), {"action": "next"}
        )

        self.assertEqual(response.url, reverse("proposal_wizard", args=[self.proposal.id, 19]))

    def test_deleting_a_step_keeps_the_answers_already_given(self):
        self._create_step()
        step = ProposalWizardStepConfig.objects.get(step_no=20)
        form = DynamicFormTemplate.objects.create(
            name="Clearance checklist",
            slug="clearance-checklist-3",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            is_active=True,
        )
        form.attached_proposal_steps.add(step)
        field = DynamicFormField.objects.create(
            form=form, label="Clearance number", field_key="clearance_no", order=1
        )
        response = DynamicFormResponse.objects.create(form=form, proposal=self.proposal)
        DynamicFormAnswer.objects.create(response=response, field=field, value="CLR-1")

        deleted = self.admin_client.post(reverse("wizard_step_delete", args=[20]))

        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(ProposalWizardStepConfig.objects.filter(step_no=20).exists())
        form.refresh_from_db()
        self.assertEqual(form.attached_proposal_steps.count(), 0)
        self.assertEqual(
            DynamicFormAnswer.objects.get(response=response, field=field).value, "CLR-1"
        )


class StepPartReassignmentTests(TestCase):
    """Pointing a step at a different built-in part moves its whole behaviour."""

    def setUp(self):
        self.owner = factories.make_user("rp_owner", Profile.ROLE_FACULTY)
        self.client_owner = factories.make_client(self.owner)
        self.admin_user, self.admin_client = factories.admin("rp_admin")
        proposal_flow.ensure_defaults()
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_a_step_can_take_over_another_parts_inputs_and_rules(self):
        ProposalWizardStepConfig.objects.create(
            step_no=20, order=20, section_key="", title="Extra rationale",
            is_visible=True, is_required=True,
        )

        edited = self.admin_client.post(
            reverse("wizard_step_edit", args=[20]),
            {
                "title": "Extra rationale",
                "description": "Second rationale pass",
                "instructions": "",
                "section_key": "rationale_background",
                "is_visible": "on",
                "is_required": "on",
                "field_id[]": [], "field_label[]": [], "field_key[]": [],
                "field_type[]": [], "field_placeholder[]": [], "field_help_text[]": [],
                "field_choices[]": [], "field_depends_on_key[]": [],
                "field_depends_on_value[]": [], "field_maps_to[]": [], "field_required[]": [],
            },
        )

        self.assertEqual(edited.status_code, 302)
        self.assertEqual(proposal_flow.template_for(20), "services/wizard/step_11.html")

        # It renders the rationale inputs...
        page = self.client_owner.get(reverse("proposal_wizard", args=[self.proposal.id, 20]))
        self.assertContains(page, 'name="rationale_background"')

        # ...and saving it writes the rationale column, not a dynamic answer.
        self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 20]),
            {"action": "next", "rationale_background": "Because the barangay asked."},
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.rationale_background, "Because the barangay asked.")
        self.assertIn(20, self.proposal.completed_steps or [])

    def test_a_partial_post_cannot_silently_blank_a_steps_part(self):
        """The editor's controls must be present for them to change anything."""
        self.admin_client.post(
            reverse("wizard_step_edit", args=[11]),
            {
                "title": "Rationale / Background",
                "description": "Context",
                "instructions": "",
                "is_visible": "on",
                "is_required": "on",
                "field_id[]": [], "field_label[]": [], "field_key[]": [],
                "field_type[]": [], "field_placeholder[]": [], "field_help_text[]": [],
                "field_choices[]": [], "field_depends_on_key[]": [],
                "field_depends_on_value[]": [], "field_maps_to[]": [], "field_required[]": [],
            },
        )

        self.assertEqual(
            ProposalWizardStepConfig.objects.get(step_no=11).section_key,
            "rationale_background",
        )

    def test_the_proponents_step_is_found_by_its_part_not_its_title(self):
        from details.proponent_fields import is_proponents_step

        step = ProposalWizardStepConfig.objects.get(step_no=3)
        step.title = "Project Team"
        step.save(update_fields=["title"])

        self.assertTrue(is_proponents_step(3))

        step.section_key = "title"
        step.save(update_fields=["section_key"])

        self.assertFalse(is_proponents_step(3))


class AttachedFormFollowsStepTests(TestCase):
    """Forms bind to the step row, so reordering does not orphan them."""

    def setUp(self):
        self.owner = factories.make_user("af_owner", Profile.ROLE_FACULTY)
        self.client_owner = factories.make_client(self.owner)
        proposal_flow.ensure_defaults()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.form = DynamicFormTemplate.objects.create(
            name="Budget breakdown",
            slug="budget-breakdown",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            is_active=True,
            blocks_proposal_submission=True,
        )
        self.field = DynamicFormField.objects.create(
            form=self.form, label="Line items", field_key="line_items",
            field_type=DynamicFormField.FieldType.TEXTAREA, required=True, order=1,
        )
        self.form.attached_proposal_steps.add(
            ProposalWizardStepConfig.objects.get(step_no=7)
        )

    def test_the_form_renders_on_the_step_it_is_attached_to(self):
        page = self.client_owner.get(reverse("proposal_wizard", args=[self.proposal.id, 7]))

        self.assertContains(page, "Budget breakdown")
        self.assertContains(page, f'dynamic_field_{self.field.id}')

    def test_the_form_still_renders_after_the_step_is_moved(self):
        proposal_flow.move(7, "up")
        self.assertEqual(proposal_flow.step_after(5), 7)

        page = self.client_owner.get(reverse("proposal_wizard", args=[self.proposal.id, 7]))

        self.assertContains(page, "Budget breakdown")

    def test_a_form_attached_to_a_built_in_step_holds_that_step_open(self):
        url = reverse("proposal_wizard", args=[self.proposal.id, 7])

        self.client_owner.post(url, {"action": "next", "budgetary_requirement": "P100,000"})
        self.proposal.refresh_from_db()
        self.assertNotIn(
            7, self.proposal.completed_steps or [],
            "the office's required field must be able to hold a built-in step open",
        )

        self.client_owner.post(
            url,
            {"action": "next", "budgetary_requirement": "P100,000",
             f"dynamic_field_{self.field.id}": "Supplies - 60,000; Meals - 40,000"},
        )
        self.proposal.refresh_from_db()
        self.assertIn(7, self.proposal.completed_steps or [])


class MOAWizardStepTests(TestCase):
    """The MOA drafting wizard is configurable the same way."""

    def setUp(self):
        self.owner = factories.make_user("moa_owner", Profile.ROLE_FACULTY)
        self.client_owner = factories.make_client(self.owner)
        self.admin_user, self.admin_client = factories.admin("moa_admin")
        moa_flow.ensure_defaults()
        self.proposal = Proposal.objects.create(
            created_by=self.owner, title="Barangay Literacy Program"
        )

    def _url(self, step):
        return reverse("proposal_moa_step", args=[self.proposal.id, step])

    def test_a_built_in_step_saves_onto_the_proposal(self):
        response = self.client_owner.post(self._url(1), {
            "moa_title": "MOA with Barangay San Juan",
            "moa_reference_no": "ISPSC-MOA-2026-001",
            "purpose": "Joint literacy program.",
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._url(2))
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.moa_title, "MOA with Barangay San Juan")
        self.assertEqual(self.proposal.moa_reference_no, "ISPSC-MOA-2026-001")

    def test_the_stepper_shows_positions_and_the_office_can_reorder(self):
        page = self.client_owner.get(self._url(1))
        self.assertContains(page, "Step 1 of 4")

        self.assertTrue(moa_flow.move(3, "up"))

        page = self.client_owner.get(self._url(1))
        self.assertContains(page, "Scope and Terms")
        self.assertEqual(moa_flow.step_after(1), 3)

    def test_the_office_can_add_a_moa_step_of_their_own(self):
        created = self.admin_client.post(reverse("moa_wizard_step_create"), {
            "step_no": "5",
            "order": "5",
            "title": "Legal Review Checklist",
            "description": "Cleared by the legal office",
            "instructions": "Tick every item the legal office requires.",
            "section_key": "",
            "is_visible": "on",
            "is_required": "on",
            "field_id[]": [], "field_label[]": [], "field_key[]": [],
            "field_type[]": [], "field_placeholder[]": [], "field_help_text[]": [],
            "field_choices[]": [], "field_depends_on_key[]": [],
            "field_depends_on_value[]": [], "field_maps_to[]": [], "field_required[]": [],
        })
        self.assertEqual(created.status_code, 302)

        step = MOAWizardStepConfig.objects.get(step_no=5)
        form = DynamicFormTemplate.objects.create(
            name="Legal checklist",
            slug="legal-checklist",
            applies_to=DynamicFormTemplate.AppliesTo.MOA,
            is_active=True,
            blocks_proposal_submission=True,
        )
        form.attached_moa_steps.add(step)
        field = DynamicFormField.objects.create(
            form=form, label="Legal reference", field_key="legal_ref",
            required=True, order=1,
        )

        page = self.client_owner.get(self._url(5))
        self.assertContains(page, "Legal Review Checklist")
        self.assertContains(page, "Legal checklist")
        self.assertEqual(moa_flow.template_for(5), "services/moa/step_dynamic.html")

        # A required field on the new step blocks moving on...
        blocked = self.client_owner.post(
            self._url(5), {"action": "next"}, follow=True
        )
        self.assertContains(blocked, "Please complete the required admin-managed field(s)")

        # ...and filling it saves an answer against the proposal.
        saved = self.client_owner.post(
            self._url(5), {f"dynamic_field_{field.id}": "LEGAL-2026-11"}
        )
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(
            DynamicFormAnswer.objects.get(field=field).value, "LEGAL-2026-11"
        )

    def test_the_final_step_still_closes_the_draft(self):
        for step, payload in [
            (1, {"moa_title": "MOA", "purpose": "Purpose."}),
            (2, {"party_one_name": "ISPSC", "party_two_name": "Partner"}),
            (3, {"obligations": "Both parties will cooperate."}),
        ]:
            self.client_owner.post(self._url(step), payload)

        response = self.client_owner.post(self._url(4), {})

        self.assertEqual(
            response.url, reverse("proposal_moa_summary", args=[self.proposal.id])
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.moa_status, Proposal.MOAStatus.DRAFT)

    def test_a_step_added_after_the_upload_part_delays_closing_the_draft(self):
        """The last step the office kept is the one that closes the draft."""
        MOAWizardStepConfig.objects.create(
            step_no=5, order=5, section_key="", title="Legal check",
            is_visible=True, is_required=True,
        )

        response = self.client_owner.post(
            self._url(4),
            {"moa_draft_file": simple_uploaded_file("moa.docx")},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], self._url(5))
        # The draft is still open: the uploads part is no longer the end.
        self.proposal.refresh_from_db()
        self.assertNotEqual(self.proposal.moa_status, Proposal.MOAStatus.DRAFT)

        self.client_owner.post(self._url(5), {})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.moa_status, Proposal.MOAStatus.DRAFT)

    def test_an_out_of_range_moa_step_is_snapped_onto_a_real_one(self):
        response = self.client_owner.get(self._url(99))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Step 4 of 4")
