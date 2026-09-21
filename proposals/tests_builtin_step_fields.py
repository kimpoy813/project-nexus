"""
Admin edits to the built-in wizard steps must EDIT the hardcoded inputs, not
add a second "Admin-managed requirements" copy of them.

The wizard steps that have built-in inputs (Title, Implementing Agency, ...)
are seeded with a "Fields for Step N" form whose field keys mirror the native
input names. Saving that form from the admin step editor must:

* change the label / placeholder / help text of the *existing* hardcoded
  input (rendered through ``step_fields`` in the step template);
* never render a duplicate input for the same value in the extra-fields
  section at the bottom of the step;
* never demand a separate ``dynamic_field_<id>`` answer for it — the value is
  stored on the ``Proposal`` record by the step's own save handler, so the
  old behaviour ("Please complete the required admin-managed field(s): ...")
  asked the proponent for input they had already given, repeatedly.
"""

import re

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import DynamicFormAnswer, DynamicFormTemplate, ProposalWizardStepConfig
from proposals.models import Proposal
from proposals.views.wizard import _wizard_step_config_map, is_step_complete
from proposals.views.dynamic_answers import (
    _is_dynamic_step_complete,
    _proposal_dynamic_requirements_missing,
)


def seed_default_steps():
    """Seed the built-in steps plus their default 'Fields for Step N' forms."""
    ProposalWizardStepConfig.objects.all().delete()
    DynamicFormTemplate.objects.all().delete()
    _wizard_step_config_map()


class MirrorFieldRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("mirror_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def _get(self, step):
        return self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, step])
        )

    def test_step_2_title_is_rendered_once(self):
        """The seeded 'title' mirror must not print a second Title input."""
        response = self._get(2)
        html = response.content.decode()
        self.assertEqual(html.count('name="title"'), 1)
        # The mirror is the form's only field, so the admin-managed panel
        # has nothing of its own to show.
        self.assertNotContains(response, "Admin-managed requirements")

    def test_step_4_implementing_agency_is_rendered_once(self):
        response = self._get(4)
        html = response.content.decode()
        self.assertEqual(html.count('name="implementing_agency"'), 1)
        self.assertNotContains(response, "Admin-managed requirements")

    def test_admin_label_edit_applies_to_the_hardcoded_input(self):
        """Relabelling the mirror field changes the existing input's label."""
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        field = form.fields.get(field_key="title")
        field.label = "Official PPA Title"
        field.save(update_fields=["label"])

        response = self._get(2)
        self.assertContains(response, "Official PPA Title")
        html = response.content.decode()
        self.assertEqual(html.count('name="title"'), 1)

    def test_extra_admin_field_still_renders_below_the_builtin_ones(self):
        """A genuinely new field is an *additional* question, shown once."""
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        form.fields.create(
            label="Acronym of the PPA",
            field_key="ppa_acronym",
            field_type="TEXT",
            required=False,
            order=99,
        )
        response = self._get(2)
        self.assertContains(response, "Admin-managed requirements")
        self.assertContains(response, "Acronym of the PPA")
        html = response.content.decode()
        self.assertEqual(html.count('name="title"'), 1)


class MirrorFieldSaveTests(TestCase):
    """'Save & Next' must accept the native inputs — no repeated re-asking."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("mirror_saver", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def _post(self, step, data):
        payload = {"action": "next"}
        payload.update(data)
        return self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, step]), payload
        )

    def test_step_2_save_next_advances_without_dynamic_field_answers(self):
        """The old bug: the seeded required 'title' mirror expected its own
        ``dynamic_field_<id>`` value, so Save & Next bounced back to the same
        step and asked for the title again — every time."""
        response = self._post(2, {"title": "Community Literacy Caravan"})
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 3]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.title, "Community Literacy Caravan")
        self.assertIn(2, self.proposal.completed_steps)

    def test_step_4_save_next_advances_without_dynamic_field_answers(self):
        response = self._post(4, {"implementing_agency": "ISPSC Extension Unit"})
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 5]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertIn(4, self.proposal.completed_steps)

    def test_step_1_save_next_advances_for_non_research_type(self):
        response = self._post(
            1, {"extension_type": "COMMUNITY_BASED", "scope_type": "ACTIVITY"}
        )
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 2]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertIn(1, self.proposal.completed_steps)

    def test_mirror_fields_do_not_store_shadow_answers(self):
        """Values already live on the Proposal record — no duplicate rows."""
        self._post(2, {"title": "Shadow-free"})
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        title_field = form.fields.get(field_key="title")
        self.assertFalse(
            DynamicFormAnswer.objects.filter(field=title_field).exists()
        )

    def test_missing_native_value_still_blocks(self):
        """Emptying a required built-in input is still caught."""
        response = self._post(4, {"implementing_agency": ""})
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 4]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertNotIn(4, self.proposal.completed_steps)

    def test_stale_empty_shadow_answer_does_not_block_completion(self):
        """Answers saved by the old code must not shadow the real value."""
        self.proposal.title = "Already saved title"
        self.proposal.save(update_fields=["title"])

        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        title_field = form.fields.get(field_key="title")
        response_obj = form.responses.create(proposal=self.proposal, submitted_by=self.owner)
        DynamicFormAnswer.objects.create(response=response_obj, field=title_field, value="")

        self.assertTrue(_is_dynamic_step_complete(self.proposal, 2))
        missing = _proposal_dynamic_requirements_missing(self.proposal)
        self.assertFalse(any("Step 2" in item for item in missing))


class StepOneProposalFormatChipTests(TestCase):
    """Step 1 picks the Proposal format with chips, the way Extension Type does.

    The format used to be a ``<select>``, which looked nothing like the
    Extension Type / Scope chips right above it. It now uses the same
    chips-plus-hidden-input pattern, so the value still posts as
    ``proposal_format`` and the server-side rules are untouched.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("format_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def _get_html(self):
        response = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 1])
        )
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _format_block(self, html):
        """The Proposal format markup, without the fields around it."""
        start = html.index('id="proposalFormatWrap"')
        end = html.index('id="researchTitleWrap"')
        return html[start:end]

    @staticmethod
    def _chip_classes(html, value):
        """The class list on the format chip carrying ``data-value``."""
        match = re.search(
            r'<div\s+class="(format-chip[^"]*)"\s+data-value="%s"' % re.escape(value),
            html,
        )
        return match.group(1) if match else ""

    def _set_extension_type(self, value):
        self.proposal.extension_type = value
        self.proposal.save(update_fields=["extension_type"])

    def test_format_renders_as_chips_instead_of_a_dropdown(self):
        self._set_extension_type(Proposal.ExtensionType.REQUEST_BASED)
        html = self._get_html()

        self.assertNotIn('<select name="proposal_format"', html)
        self.assertIn('class="format-chip', html)
        # A multi-line ``{# ... #}`` is not a comment to Django (it prints
        # verbatim), so keep the block's own comments single-line.
        self.assertNotIn("{#", self._format_block(html))
        # Both formats are offered as clickable chips...
        self.assertIn('data-value="TRAINING_DESIGN"', html)
        self.assertIn('data-value="EXTENSION_PROPOSAL"', html)
        self.assertIn('data-label="Training Design"', html)
        self.assertIn('data-label="Extension Proposal"', html)
        # ...and the form still submits the chosen value under its old name.
        self.assertIn('name="proposal_format"', html)
        self.assertEqual(html.count('name="proposal_format"'), 1)

    def test_format_block_stays_hidden_for_other_extension_types(self):
        self._set_extension_type(Proposal.ExtensionType.COMMUNITY_BASED)
        html = self._get_html()

        # Only a request-based proposal gets to choose a format, so the chips
        # stay hidden — with a hidden input that still submits a valid value.
        self.assertIn('id="proposalFormatWrap" class="hidden"', html)
        self.assertIn('value="TRAINING_DESIGN"', html)
        self.assertNotIn('<select name="proposal_format"', html)

    def test_training_design_is_the_chip_active_by_default(self):
        self._set_extension_type(Proposal.ExtensionType.REQUEST_BASED)
        html = self._get_html()

        self.assertIn("bg-primary", self._chip_classes(html, "TRAINING_DESIGN"))
        self.assertIn("bg-white", self._chip_classes(html, "EXTENSION_PROPOSAL"))
        # The proponent never picked a format yet: the fallback is Training
        # Design, exactly what the view saves for a blank request-based pick.
        self.assertIn('value="TRAINING_DESIGN"', html)

    def test_saved_extension_proposal_highlights_its_own_chip(self):
        self.proposal.extension_type = Proposal.ExtensionType.REQUEST_BASED
        self.proposal.proposal_format = Proposal.ProposalFormat.EXTENSION_PROPOSAL
        self.proposal.save(update_fields=["extension_type", "proposal_format"])
        html = self._get_html()

        self.assertIn("bg-primary", self._chip_classes(html, "EXTENSION_PROPOSAL"))
        self.assertIn("bg-white", self._chip_classes(html, "TRAINING_DESIGN"))
        self.assertIn('value="EXTENSION_PROPOSAL"', html)

    def test_hidden_input_carries_the_chip_pick_on_save(self):
        response = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 1]),
            {
                "action": "next",
                "extension_type": "REQUEST_BASED",
                "scope_type": "PROJECT",
                "proposal_format": "EXTENSION_PROPOSAL",
            },
        )
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 2]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(
            self.proposal.proposal_format, Proposal.ProposalFormat.EXTENSION_PROPOSAL
        )


class StepEditorWithoutExplanationsTests(TestCase):
    """The step editor stays quiet about what each step's logic is.

    It used to spell out which inputs were "hardcoded", when the step counted
    as complete, which Keys edited those inputs, and how repeatable groups
    behaved. The office asked for the editor to simply work: renaming a field,
    changing its placeholder, and so on applies to the wizard step either way.
    """

    def setUp(self):
        self.admin_user, self.admin_client = factories.admin("quiet_editor_admin")

    def _editor(self, step_no):
        response = self.admin_client.get(reverse("wizard_step_edit", args=[step_no]))
        self.assertEqual(response.status_code, 200)
        return response

    def test_step_editor_shows_no_builtin_logic_panel(self):
        response = self._editor(2)
        self.assertNotContains(response, "Built-in step logic")
        self.assertNotContains(response, "What this step already asks for")
        self.assertNotContains(response, "When the step counts as complete")

    def test_step_editor_shows_no_mirror_field_badges(self):
        response = self._editor(2)
        self.assertNotContains(response, "Edits the built-in")
        self.assertNotContains(response, "not key-editable")
        self.assertNotContains(response, "A field whose Key matches")

    def test_step_editor_still_renders_the_field_rows_it_saves(self):
        """Dropping the explanations must not drop the inputs themselves."""
        response = self._editor(2)
        self.assertContains(response, 'name="field_label[]"')
        self.assertContains(response, 'name="field_key[]"')
        self.assertContains(response, 'name="field_type[]"')
        self.assertContains(response, "Fields (Inputs / Elements)")

    def test_editor_rename_still_applies_to_the_wizard_step(self):
        """What the editor *does* is what matters: the rename takes effect."""
        # Opening the editor is what creates and seeds the step's form.
        self._editor(2)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        field = form.fields.get(field_key="title")

        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[2]),
            {
                "title": "Title",
                "description": "",
                "instructions": "",
                "is_visible": "on",
                "is_required": "on",
                "field_id[]": [str(field.id)],
                "field_label[]": ["Official PPA Title"],
                "field_key[]": [field.field_key],
                "field_type[]": [field.field_type],
                "field_placeholder[]": [field.placeholder],
                "field_help_text[]": [field.help_text],
                "field_choices[]": [field.choices_text],
                "field_depends_on_key[]": [field.depends_on_key],
                "field_depends_on_value[]": [field.depends_on_value],
                "field_maps_to[]": [field.maps_to],
                "field_required[]": [str(field.id)],
            },
        )
        self.assertEqual(response.status_code, 302)

        owner = factories.make_user("renamed_label_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=owner)
        wizard = factories.make_client(owner).get(
            reverse("proposal_wizard", args=[proposal.id, 2])
        )
        html = wizard.content.decode()
        self.assertIn("Official PPA Title", html)
        # Still one Title input: the mirror edits the built-in one, no duplicate.
        self.assertEqual(html.count('name="title"'), 1)

