"""
Tests for admin-built dynamic form fields with depends_on conditions.

The form builder lets admins make a field visible only when a parent field
holds a particular value. The browser hides such fields, but the server-side
required-field checks used to ignore the condition — a *hidden* required
field blocked submission with an error the user could not resolve.
"""

from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import (
    DynamicFormAnswer,
    DynamicFormField,
    DynamicFormResponse,
    DynamicFormTemplate,
)

from .models import Proposal
from .views.wizard import (
    _is_dynamic_step_complete,
    _proposal_dynamic_requirements_missing,
    _save_dynamic_form_answers,
)


def build_form(step=3, blocks=True):
    form = DynamicFormTemplate.objects.create(
        name="Funding Checklist",
        slug="funding-checklist",
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step=step,
        blocks_proposal_submission=blocks,
    )
    parent = DynamicFormField.objects.create(
        form=form,
        label="Funding source",
        field_key="funding_source",
        field_type=DynamicFormField.FieldType.SELECT,
        required=True,
        choices_text="University|University\nExternal|External",
        order=1,
    )
    child = DynamicFormField.objects.create(
        form=form,
        label="External grant number",
        field_key="grant_number",
        field_type=DynamicFormField.FieldType.TEXT,
        required=True,
        depends_on_key="funding_source",
        depends_on_value="External",
        order=2,
    )
    return form, parent, child


class DynamicFieldDependencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("dyn_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner, current_step=3)
        self.factory = RequestFactory()

    def _post(self, data):
        return self.factory.post("/wizard/", data)

    def test_hidden_required_field_does_not_block(self):
        """Parent = University -> child field is hidden and must not block."""
        form, parent, child = build_form()
        request = self._post(
            {
                f"dynamic_field_{parent.id}": "University",
                f"dynamic_field_{child.id}": "",
            }
        )
        missing = _save_dynamic_form_answers(self.proposal, 3, self.owner, request)
        self.assertEqual(missing, [])
        self.assertTrue(_is_dynamic_step_complete(self.proposal, 3))
        self.assertEqual(_proposal_dynamic_requirements_missing(self.proposal), [])

    def test_visible_required_field_still_blocks(self):
        """Parent = External -> child field is visible and required."""
        form, parent, child = build_form()
        request = self._post(
            {
                f"dynamic_field_{parent.id}": "External",
                f"dynamic_field_{child.id}": "",
            }
        )
        missing = _save_dynamic_form_answers(self.proposal, 3, self.owner, request)
        self.assertEqual(missing, ["Funding Checklist: External grant number"])
        self.assertFalse(_is_dynamic_step_complete(self.proposal, 3))
        self.assertEqual(
            _proposal_dynamic_requirements_missing(self.proposal),
            ["Step 3 — Funding Checklist: External grant number"],
        )

    def test_filled_visible_field_passes(self):
        form, parent, child = build_form()
        request = self._post(
            {
                f"dynamic_field_{parent.id}": "External",
                f"dynamic_field_{child.id}": "GRANT-42",
            }
        )
        missing = _save_dynamic_form_answers(self.proposal, 3, self.owner, request)
        self.assertEqual(missing, [])
        self.assertTrue(_is_dynamic_step_complete(self.proposal, 3))

    def test_saved_answers_drive_dependencies(self):
        """The submission gate re-checks saved answers, not the live request."""
        form, parent, child = build_form()
        request = self._post(
            {
                f"dynamic_field_{parent.id}": "University",
                f"dynamic_field_{child.id}": "",
            }
        )
        _save_dynamic_form_answers(self.proposal, 3, self.owner, request)
        # Parent saved as University: the hidden child must not block the
        # final submission gate.
        self.assertEqual(_proposal_dynamic_requirements_missing(self.proposal), [])

    def test_checkbox_parent_matches_on_and_yes(self):
        """Checkbox parents submit 'on' but persist 'Yes'; both must satisfy."""
        form = DynamicFormTemplate.objects.create(
            name="Checkbox Checklist",
            slug="checkbox-checklist",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=4,
            blocks_proposal_submission=True,
        )
        parent = DynamicFormField.objects.create(
            form=form,
            label="Needs clearance",
            field_key="needs_clearance",
            field_type=DynamicFormField.FieldType.CHECKBOX,
            required=False,
            order=1,
        )
        child = DynamicFormField.objects.create(
            form=form,
            label="Clearance officer",
            field_key="clearance_officer",
            field_type=DynamicFormField.FieldType.TEXT,
            required=True,
            depends_on_key="needs_clearance",
            depends_on_value="on",
            order=2,
        )

        # Checked parent ('on' in POST): child is visible and required.
        request = self._post(
            {
                f"dynamic_field_{parent.id}": "on",
                f"dynamic_field_{child.id}": "",
            }
        )
        missing = _save_dynamic_form_answers(self.proposal, 4, self.owner, request)
        self.assertEqual(missing, ["Checkbox Checklist: Clearance officer"])

        # Unchecked parent: child is hidden and must not block.
        request = self._post({f"dynamic_field_{parent.id}": "", f"dynamic_field_{child.id}": ""})
        missing = _save_dynamic_form_answers(self.proposal, 4, self.owner, request)
        self.assertEqual(missing, [])

        # Persisted 'Yes' must behave like 'on' for the saved-answer gate.
        response = DynamicFormResponse.objects.get(proposal=self.proposal, form=form)
        answer = DynamicFormAnswer.objects.get(response=response, field=parent)
        answer.value = "Yes"
        answer.save()
        self.assertEqual(_proposal_dynamic_requirements_missing(self.proposal), [
            "Step 4 — Checkbox Checklist: Clearance officer"
        ])

    def test_dependency_on_native_wizard_field(self):
        """depends_on_key can reference a native wizard field stored on the
        Proposal model (e.g. extension_type)."""
        form = DynamicFormTemplate.objects.create(
            name="Type Checklist",
            slug="type-checklist",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=3,
            blocks_proposal_submission=True,
        )
        child = DynamicFormField.objects.create(
            form=form,
            label="Community detail",
            field_key="community_detail",
            field_type=DynamicFormField.FieldType.TEXT,
            required=True,
            depends_on_key="extension_type",
            depends_on_value="COMMUNITY_BASED",
            order=1,
        )

        # extension_type on the proposal is empty: not one of the expected
        # values, so the field counts as hidden and must not block.
        request = self._post({f"dynamic_field_{child.id}": ""})
        missing = _save_dynamic_form_answers(self.proposal, 3, self.owner, request)
        self.assertEqual(missing, [])
        self.assertEqual(_proposal_dynamic_requirements_missing(self.proposal), [])

        # With a matching extension_type the field becomes visible/required.
        self.proposal.extension_type = Proposal.ExtensionType.COMMUNITY_BASED
        self.proposal.save()
        self.assertEqual(
            _proposal_dynamic_requirements_missing(self.proposal),
            ["Step 3 — Type Checklist: Community detail"],
        )

    def test_missing_parent_treated_as_visible(self):
        """A depends_on_key pointing at a field that does not exist keeps the
        field visible (matching the browser), so it still blocks."""
        form = DynamicFormTemplate.objects.create(
            name="Orphan Checklist",
            slug="orphan-checklist",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=5,
            blocks_proposal_submission=True,
        )
        child = DynamicFormField.objects.create(
            form=form,
            label="Orphan detail",
            field_key="orphan_detail",
            field_type=DynamicFormField.FieldType.TEXT,
            required=True,
            depends_on_key="no_such_field_anywhere",
            depends_on_value="Whatever",
            order=1,
        )
        request = self._post({f"dynamic_field_{child.id}": ""})
        missing = _save_dynamic_form_answers(self.proposal, 5, self.owner, request)
        self.assertEqual(missing, ["Orphan Checklist: Orphan detail"])


class DynamicFieldRenderingTests(TestCase):
    """The wizard page must render the dependency wiring the browser script
    relies on (data-depends-on / data-depends-value attributes)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("render_owner", Profile.ROLE_FACULTY)
        # The wizard normalizes step numbers against visible step configs;
        # without them every step collapses to step 1. Seeded rows are fine:
        # the proposal picks a research type below so its steps stay visible.
        from details.models import ProposalWizardStepConfig
        from .views.wizard import _wizard_step_config_map

        sample = Proposal.objects.create(created_by=cls.owner, extension_type="RESEARCH_FACULTY", scope_type="ACTIVITY")
        _wizard_step_config_map(sample)

    def test_wizard_step_renders_dependency_attributes(self):
        proposal = Proposal.objects.create(
            created_by=self.owner,
            current_step=3,
            extension_type="RESEARCH_FACULTY",
            scope_type="ACTIVITY",
        )
        form = DynamicFormTemplate.objects.create(
            name="Render Checklist",
            slug="render-checklist",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=3,
            blocks_proposal_submission=False,
        )
        DynamicFormField.objects.create(
            form=form,
            label="Conditional detail",
            field_key="conditional_detail",
            field_type=DynamicFormField.FieldType.TEXT,
            required=False,
            depends_on_key="funding_source",
            depends_on_value="External",
            order=1,
        )

        client = factories.make_client(self.owner)
        response = client.get(reverse("proposal_wizard", args=[proposal.id, 3]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-depends-on="funding_source"')
        self.assertContains(response, 'data-depends-value="External"')
        # The normalising client script must be present.
        self.assertContains(response, "normaliseValue")
