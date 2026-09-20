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

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import DynamicFormAnswer, DynamicFormTemplate, ProposalWizardStepConfig
from proposals.models import Proposal
from proposals.views.constants import BUILTIN_STEP_LOGIC, INITIAL_STEP_LABELS
from proposals.views.dynamic_fields import NATIVE_STEP_FIELDS, native_keys_for_step
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


class BuiltinStepLogicReferenceTests(TestCase):
    """The admin step editor documents each built-in step's logic."""

    def setUp(self):
        self.admin_user, self.admin_client = factories.admin("logic_admin")

    def test_every_builtin_step_has_a_logic_entry(self):
        for item in INITIAL_STEP_LABELS:
            with self.subTest(step=item["no"]):
                self.assertIn(item["no"], BUILTIN_STEP_LOGIC)
                entry = BUILTIN_STEP_LOGIC[item["no"]]
                self.assertTrue(entry["inputs"])
                self.assertTrue(entry["completion"])

    def test_editable_keys_stay_in_sync_with_native_step_fields(self):
        """The editor's advertised keys must match what the wizard honours."""
        for step_no, entry in BUILTIN_STEP_LOGIC.items():
            with self.subTest(step=step_no):
                for key in entry["editable_keys"]:
                    self.assertIn(
                        key,
                        native_keys_for_step(step_no),
                        f"step {step_no}: '{key}' advertised but not honoured",
                    )

    def test_step_editor_shows_the_builtin_logic_panel(self):
        response = self.admin_client.get(reverse("wizard_step_edit", args=[2]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Built-in step logic")
        self.assertContains(response, "What this step already asks for")
        # Advertises the key that edits the hardcoded Title input.
        self.assertContains(response, "<code", html=False)
        self.assertContains(response, "title")

    def test_step_editor_marks_mirror_fields(self):
        # Seed the default forms first (the manager does this on first visit).
        self.admin_client.get(reverse("wizard_steps_manager"))
        response = self.admin_client.get(reverse("wizard_step_edit", args=[2]))
        self.assertContains(response, "Edits the built-in")

    def test_file_upload_steps_explain_no_editable_keys(self):
        response = self.admin_client.get(reverse("wizard_step_edit", args=[17]))
        self.assertContains(response, "not key-editable")
