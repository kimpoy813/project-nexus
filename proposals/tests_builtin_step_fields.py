"""
Admin edits to wizard steps must change the fields proponents see on the step
itself, not add a separate "Admin-managed requirements" form beneath it.

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

from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_step_17_upload_mirrors_render_the_native_inputs_once(self):
        response = self._get(17)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('name="work_plan_file"'), 1)
        self.assertEqual(html.count('name="gantt_chart_file"'), 1)
        self.assertContains(response, "Work Plan File")
        self.assertContains(response, "Gantt Chart File")

    def test_step_18_upload_mirror_renders_the_native_input_once(self):
        response = self._get(18)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('name="funding_file"'), 1)
        self.assertContains(response, "Funding Strategy")

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

    def test_wizard_step_editor_form_owns_builtin_customisations(self):
        """A second attached form cannot override what Wizard Steps saved."""
        primary = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        title = primary.fields.get(field_key="title")
        title.label = "Official PPA Title"
        title.save(update_fields=["label"])

        other = DynamicFormTemplate.objects.create(
            name="ZZZ Supplement",
            slug="zzz-supplement",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=2,
        )
        other.fields.create(
            label="Wrong title override",
            field_key="title",
            field_type="TEXT",
            order=1,
        )

        response = self._get(2)
        self.assertContains(response, "Official PPA Title")
        self.assertNotContains(response, "Wrong title override")

    def test_new_step_field_renders_as_part_of_the_step(self):
        """A new field is part of the step, not a separate admin form."""
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        form.fields.create(
            label="Acronym of the PPA",
            field_key="ppa_acronym",
            field_type="TEXT",
            required=False,
            order=99,
        )
        response = self._get(2)
        self.assertContains(response, "Acronym of the PPA")
        self.assertNotContains(response, "Admin-managed requirements")
        self.assertNotContains(response, "Additional Extension Office fields")
        self.assertNotContains(response, "controlled by the Admin/Form Builder")
        # The generated template name is admin plumbing, not user-facing copy.
        self.assertNotContains(response, form.name)
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

    def test_step_5_records_the_participant_split(self):
        """The terminal report needs students and faculty counted separately."""
        response = self._post(
            5,
            {
                "beneficiaries_count": "50",
                "beneficiaries_who": "Barangay Sabangan farmers",
                "student_participants": "5",
                "faculty_participants": "13",
                "research_staff_participants": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.beneficiaries_count, 50)
        self.assertEqual(self.proposal.student_participants, 5)
        self.assertEqual(self.proposal.faculty_participants, 13)
        # Left blank, not guessed: nobody from that group took part.
        self.assertIsNone(self.proposal.research_staff_participants)

    def test_step_17_file_mirrors_save_native_uploads_without_shadow_answers(self):
        response = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 17]),
            {
                "action": "next",
                "work_plan_file": SimpleUploadedFile("work-plan.xlsx", b"plan"),
                "gantt_chart_file": SimpleUploadedFile("gantt.xlsx", b"gantt"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertTrue(self.proposal.work_plan_file)
        self.assertTrue(self.proposal.gantt_chart_file)
        self.assertIn(17, self.proposal.completed_steps)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=17)
        self.assertFalse(
            DynamicFormAnswer.objects.filter(
                field__form=form,
                field__field_key__in=("work_plan_file", "gantt_chart_file"),
            ).exists()
        )

    def test_step_18_file_mirror_saves_native_upload_without_shadow_answer(self):
        response = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 18]),
            {
                "action": "next",
                "funding_file": SimpleUploadedFile("funding.xlsx", b"funding"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertTrue(self.proposal.funding_file)
        self.assertIn(18, self.proposal.completed_steps)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=18)
        self.assertFalse(
            DynamicFormAnswer.objects.filter(
                field__form=form,
                field__field_key="funding_file",
            ).exists()
        )

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

    def test_missing_configured_field_uses_normal_step_validation_copy(self):
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        form.fields.create(
            label="PPA Acronym",
            field_key="ppa_acronym",
            field_type="TEXT",
            required=True,
            order=99,
        )

        response = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 2]),
            {"action": "next", "title": "Community Literacy Caravan"},
            follow=True,
        )

        self.assertContains(response, "Please complete the required field(s): PPA Acronym")
        self.assertNotContains(response, "admin-managed")
        self.assertNotContains(response, form.name)

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
            r'<button[^>]*class="(format-chip[^"]*)"[^>]*data-value="%s"' % re.escape(value),
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


class ResearchAbstractStepRedundantFieldTests(TestCase):
    """Step 19 (Research Abstract Upload) must never show redundant step fields."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("abstract_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(
            created_by=self.owner,
            extension_type=Proposal.ExtensionType.RESEARCH_FACULTY,
            scope_type=Proposal.ScopeType.PROJECT,
            research_title="Rice Straw Biocomposite",
        )
        self.client_owner = factories.make_client(self.owner)

    def _pile_displaced_forms_onto_step_19(self):
        """Reproduce the production pile left by 0023's ascending renumber."""
        displaced = [
            (7, "step-7-fields", "Fields for Step 7", [("budgetary_requirement", "Budgetary Requirement", "TEXTAREA")]),
            (
                10,
                "step-10-fields",
                "Fields for Step 10",
                [
                    ("extension_venue", "Extension Venue / Site", "TEXT"),
                    ("estimated_month", "Estimated Month", "SELECT"),
                    ("estimated_year", "Estimated Year", "NUMBER"),
                ],
            ),
            (11, "step-11-fields", "Fields for Step 11", [("rationale_background", "Rationale / Background", "TEXTAREA")]),
            (12, "step-12-fields", "Fields for Step 12", [("significance", "Significance", "TEXTAREA")]),
            (13, "step-13-fields", "Fields for Step 13", [("general_objective", "General Objective", "TEXTAREA")]),
        ]
        # Remove the cleanly seeded 8/11/12/13/14/19/20 forms first and give
        # Step 7 the "-2" slug 0027 assigned when step-7-fields sat on 19.
        DynamicFormTemplate.objects.filter(
            proposal_wizard_step__in=[8, 11, 12, 13, 14, 19, 20]
        ).delete()
        DynamicFormTemplate.objects.filter(
            proposal_wizard_step=7, slug="step-7-fields"
        ).update(slug="step-7-fields-2")

        created_forms = []
        for _old_no, slug, name, fields in displaced:
            form = DynamicFormTemplate.objects.create(
                name=name,
                slug=slug,
                applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
                proposal_wizard_step=19,
                is_active=True,
                blocks_proposal_submission=True,
            )
            resp = form.responses.create(proposal=self.proposal, submitted_by=self.owner)
            for order, (key, label, ftype) in enumerate(fields, start=1):
                field = form.fields.create(
                    field_key=key,
                    label=label,
                    field_type=ftype,
                    required=True,
                    order=order,
                )
                DynamicFormAnswer.objects.create(response=resp, field=field, value="")
            created_forms.append(form)
        return created_forms

    def test_step_19_renders_abstract_and_complete_research_uploads_once(self):
        for ext_type in (
            Proposal.ExtensionType.RESEARCH_FACULTY,
            Proposal.ExtensionType.RESEARCH_STUDENT,
        ):
            self.proposal.extension_type = ext_type
            self.proposal.save(update_fields=["extension_type"])
            response = self.client_owner.get(
                reverse("proposal_wizard", args=[self.proposal.id, 19])
            )
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertEqual(html.count('name="research_abstract_file"'), 1)
            self.assertEqual(html.count('name="complete_research_file"'), 1)
            self.assertNotIn("dynamic_field_", html)

    def test_step_19_requires_both_abstract_and_complete_research_and_previews_both(self):
        self.proposal.extension_type = Proposal.ExtensionType.RESEARCH_STUDENT
        self.proposal.save(update_fields=["extension_type"])

        # Uploading only the abstract must block Save & Next until Complete Research is uploaded.
        partial = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 19]),
            {
                "action": "next",
                "research_abstract_file": SimpleUploadedFile("abstract.pdf", b"%PDF-abstract"),
            },
            follow=True,
        )
        self.assertContains(
            partial, "Please complete the required field(s): Complete Research File"
        )
        self.proposal.refresh_from_db()
        self.assertTrue(self.proposal.research_abstract_file)
        self.assertNotIn(19, self.proposal.completed_steps)

        # Uploading Complete Research completes Step 19 and exposes preview.
        complete_resp = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 19]),
            {
                "action": "next",
                "complete_research_file": SimpleUploadedFile("thesis.pdf", b"%PDF-full"),
            },
        )
        self.assertRedirects(
            complete_resp,
            reverse("proposal_wizard", args=[self.proposal.id, 20]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertIn(19, self.proposal.completed_steps)
        preview = self.client_owner.get(
            reverse("proposal_file_preview", args=[self.proposal.id, "complete_research"])
        )
        self.assertEqual(preview.status_code, 200)

    def test_certificate_of_completion_is_required_only_for_faculty_not_student(self):
        # Faculty research requires Certificate of Completion on Step 20.
        self.proposal.extension_type = Proposal.ExtensionType.RESEARCH_FACULTY
        self.proposal.save(update_fields=["extension_type"])

        step_20_faculty = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 20])
        )
        self.assertContains(step_20_faculty, 'name="certificate_of_completion_file"', count=1)

        blocked = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 20]),
            {"action": "next"},
            follow=True,
        )
        self.assertContains(
            blocked,
            "Please complete the required field(s): Certificate of Completion File",
        )
        self.proposal.refresh_from_db()
        self.assertNotIn(20, self.proposal.completed_steps)
        self.assertFalse(is_step_complete(self.proposal, 20))

        # Student research does NOT require Certificate of Completion on Step 20.
        self.proposal.extension_type = Proposal.ExtensionType.RESEARCH_STUDENT
        self.proposal.save(update_fields=["extension_type"])

        step_20_student = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 20])
        )
        self.assertNotContains(step_20_student, 'name="certificate_of_completion_file"')
        self.assertContains(step_20_student, "Not required for your proposal type")
        self.assertContains(step_20_student, "Research-based (Faculty)")
        self.assertTrue(is_step_complete(self.proposal, 20))
        self.assertTrue(_is_dynamic_step_complete(self.proposal, 20))
        missing = _proposal_dynamic_requirements_missing(self.proposal)
        self.assertFalse(any("Step 20" in item for item in missing), missing)

        saved = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 20]),
            {"action": "next"},
        )
        self.assertRedirects(
            saved,
            reverse("proposal_submit", args=[self.proposal.id]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertIn(20, self.proposal.completed_steps)

    def test_foreign_builtin_mirrors_stranded_on_step_19_do_not_render_or_block(self):
        self._pile_displaced_forms_onto_step_19()

        response = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 19])
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        main_start = html.index('<section class="nx-wizard-main')
        main_html = html[main_start:html.index("</section>", main_start)]
        for redundant_label in (
            "Budgetary Requirement",
            "Extension Venue / Site",
            "Estimated Month",
            "Estimated Year",
            "Rationale / Background",
            "Significance",
            "General Objective",
        ):
            self.assertNotIn(redundant_label, main_html)
        self.assertNotIn("dynamic_field_", main_html)

        post_resp = self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, 19]),
            {
                "action": "next",
                "research_abstract_file": SimpleUploadedFile("abstract.pdf", b"%PDF-1.4"),
                "complete_research_file": SimpleUploadedFile("complete.pdf", b"%PDF-1.4"),
            },
        )
        self.assertRedirects(
            post_resp,
            reverse("proposal_wizard", args=[self.proposal.id, 20]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertIn(19, self.proposal.completed_steps)
        self.assertTrue(_is_dynamic_step_complete(self.proposal, 19))
        missing = _proposal_dynamic_requirements_missing(self.proposal)
        self.assertFalse(any("Step 19" in item for item in missing), missing)

    def test_admin_step_19_and_20_edits_sync_labels_required_and_depends_on(self):
        _admin_user, admin_client = factories.admin("step19_20_sync_admin")

        # Step 19 editor shows both built-in upload mirrors.
        editor_19 = admin_client.get(reverse("wizard_step_edit", args=[19]))
        self.assertEqual(editor_19.status_code, 200)
        form_19 = DynamicFormTemplate.objects.get(proposal_wizard_step=19)
        fields_19 = list(form_19.fields.order_by("order", "id"))
        self.assertEqual(
            [f.field_key for f in fields_19],
            ["research_abstract_file", "complete_research_file"],
        )

        # Admin customises Complete Research label & restricts it to RESEARCH_STUDENT.
        post_19 = admin_client.post(
            reverse("wizard_step_edit", args=[19]),
            {
                "title": "Research Abstract Upload",
                "description": "Abstract and manuscript",
                "instructions": "",
                "is_visible": "on",
                "is_required": "on",
                "field_id[]": [str(f.id) for f in fields_19],
                "field_label[]": ["Approved Abstract PDF", "Full Thesis / Manuscript"],
                "field_key[]": [f.field_key for f in fields_19],
                "field_type[]": [f.field_type for f in fields_19],
                "field_placeholder[]": [f.placeholder for f in fields_19],
                "field_help_text[]": ["Upload signed abstract.", "Upload full student research."],
                "field_choices[]": [f.choices_text for f in fields_19],
                "field_depends_on_key[]": ["extension_type", "extension_type"],
                "field_depends_on_value[]": [
                    "RESEARCH_FACULTY,RESEARCH_STUDENT",
                    "RESEARCH_STUDENT",
                ],
                "field_maps_to[]": ["", ""],
                "field_required[]": [str(f.id) for f in fields_19],
            },
        )
        self.assertEqual(post_19.status_code, 302)

        # Faculty proposal now sees only Approved Abstract PDF on Step 19; Student sees both.
        faculty_view = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 19])
        )
        self.assertContains(faculty_view, "Approved Abstract PDF")
        self.assertContains(faculty_view, 'name="research_abstract_file"', count=1)
        self.assertNotContains(faculty_view, 'name="complete_research_file"')

        self.proposal.extension_type = Proposal.ExtensionType.RESEARCH_STUDENT
        self.proposal.save(update_fields=["extension_type"])
        student_view = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 19])
        )
        self.assertContains(student_view, "Approved Abstract PDF")
        self.assertContains(student_view, "Full Thesis / Manuscript")
        self.assertContains(student_view, 'name="complete_research_file"', count=1)

        # Step 20 editor defaults Certificate of Completion to RESEARCH_FACULTY only.
        editor_20 = admin_client.get(reverse("wizard_step_edit", args=[20]))
        self.assertEqual(editor_20.status_code, 200)
        form_20 = DynamicFormTemplate.objects.get(proposal_wizard_step=20)
        cert_field = form_20.fields.get(field_key="certificate_of_completion_file")
        self.assertEqual(cert_field.depends_on_key, "extension_type")
        self.assertEqual(cert_field.depends_on_value, "RESEARCH_FACULTY")

        # Community-based proposals do not require either step's uploads.
        self.proposal.extension_type = Proposal.ExtensionType.COMMUNITY_BASED
        self.proposal.save(update_fields=["extension_type"])
        self.assertTrue(_is_dynamic_step_complete(self.proposal, 19))
        self.assertTrue(_is_dynamic_step_complete(self.proposal, 20))
        missing = _proposal_dynamic_requirements_missing(self.proposal)
        self.assertFalse(any("Step 19" in item or "Step 20" in item for item in missing), missing)

    def test_migration_0054_unpiles_displaced_forms_from_step_19(self):
        import importlib
        from django.apps import apps

        migration = importlib.import_module(
            "details.migrations.0054_clean_research_abstract_step_fields"
        )
        self._pile_displaced_forms_onto_step_19()

        migration.clean_research_abstract_step(apps, None)
        # Running a second time must be a clean no-op.
        migration.clean_research_abstract_step(apps, None)

        step_19_form = DynamicFormTemplate.objects.get(proposal_wizard_step=19)
        self.assertEqual(
            list(step_19_form.fields.order_by("order").values_list("field_key", flat=True)),
            ["research_abstract_file", "complete_research_file"],
        )
        step_20_form = DynamicFormTemplate.objects.get(proposal_wizard_step=20)
        cert_field = step_20_form.fields.get(field_key="certificate_of_completion_file")
        self.assertEqual(cert_field.depends_on_value, "RESEARCH_FACULTY")

        restored = dict(
            DynamicFormTemplate.objects.filter(
                slug__in=[
                    "step-7-fields",
                    "step-10-fields",
                    "step-11-fields",
                    "step-12-fields",
                    "step-13-fields",
                ]
            ).values_list("slug", "proposal_wizard_step")
        )
        self.assertEqual(
            restored,
            {
                "step-7-fields": 8,
                "step-10-fields": 11,
                "step-11-fields": 12,
                "step-12-fields": 13,
                "step-13-fields": 14,
            },
        )
        # Bogus Step-19 shadow answers on native mirror fields are gone.
        self.assertFalse(
            DynamicFormAnswer.objects.filter(
                field__form__slug__in=list(restored.keys())
            ).exists()
        )

    def test_migration_0054_cleans_admin_emptied_pile_and_preserves_custom_step_19_fields(self):
        import importlib
        from django.apps import apps

        migration = importlib.import_module(
            "details.migrations.0054_clean_research_abstract_step_fields"
        )
        forms = self._pile_displaced_forms_onto_step_19()
        # Simulate an admin who edited Step 19, which renamed the first piled
        # form and added a genuine Step-19 custom field alongside the foreign mirror.
        first_form = forms[0]
        first_form.name = "Fields for Step 19: Research Abstract Upload"
        first_form.save(update_fields=["name"])
        first_form.fields.create(
            field_key="abstract_keywords",
            label="Abstract Keywords",
            field_type="TEXT",
            required=False,
            order=99,
        )

        migration.clean_research_abstract_step(apps, None)

        step_19_forms = list(
            DynamicFormTemplate.objects.filter(proposal_wizard_step=19)
        )
        self.assertEqual(len(step_19_forms), 1)
        self.assertEqual(
            list(step_19_forms[0].fields.order_by("order").values_list("field_key", flat=True)),
            ["abstract_keywords", "research_abstract_file", "complete_research_file"],
        )
        # Step 8 still receives its default budgetary_requirement mirror.
        step_8_form = DynamicFormTemplate.objects.get(proposal_wizard_step=8)
        self.assertEqual(
            list(step_8_form.fields.values_list("field_key", flat=True)),
            ["budgetary_requirement"],
        )

    def test_step_editor_consolidates_extra_forms_and_drops_foreign_mirrors(self):
        _admin_user, admin_client = factories.admin("step19_editor_admin")
        self._pile_displaced_forms_onto_step_19()
        extra = DynamicFormTemplate.objects.create(
            name="Extra Step 19 Note",
            slug="extra-step-19-note",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=19,
        )
        extra.fields.create(
            field_key="ethics_clearance_no",
            label="Ethics Clearance Number",
            field_type="TEXT",
            required=False,
            order=1,
        )

        response = admin_client.get(reverse("wizard_step_edit", args=[19]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ethics Clearance Number")
        self.assertContains(response, "Research Abstract File")
        self.assertContains(response, "Complete Research File")
        self.assertNotContains(response, "Budgetary Requirement")
        self.assertNotContains(response, "Rationale / Background")
        self.assertEqual(
            DynamicFormTemplate.objects.filter(proposal_wizard_step=19).count(),
            1,
        )

