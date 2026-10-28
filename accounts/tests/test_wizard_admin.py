import json

from django.test import TestCase
from django.urls import reverse
from details.models import DynamicFormField, DynamicFormTemplate, ProposalWizardStepConfig
from . import factories


class WizardAdminTests(TestCase):
    def setUp(self):
        self.admin_user, self.admin_client = factories.admin()

    def _step_editor_payload(self, step_no, **overrides):
        self.admin_client.get(reverse("wizard_step_edit", args=[step_no]))
        step_config = ProposalWizardStepConfig.objects.get(step_no=step_no)
        form_obj = DynamicFormTemplate.objects.get(
            proposal_wizard_step=step_no,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        )
        payload = {
            "title": step_config.title,
            "description": step_config.description,
            "instructions": step_config.instructions,
            "template_download_heading": step_config.template_download_heading,
            "template_download_instructions": step_config.template_download_instructions,
            "work_plan_download_label": step_config.work_plan_download_label,
            "gantt_chart_download_label": step_config.gantt_chart_download_label,
            "funding_download_label": step_config.funding_download_label,
            "is_visible": "on" if step_config.is_visible else "",
            "is_required": "on" if step_config.is_required else "",
        }
        fields = list(form_obj.fields.order_by("order", "id"))
        for name in (
            "field_id[]",
            "field_label[]",
            "field_key[]",
            "field_type[]",
            "field_placeholder[]",
            "field_help_text[]",
            "field_choices[]",
            "field_depends_on_key[]",
            "field_depends_on_value[]",
            "field_maps_to[]",
        ):
            payload[name] = []
        payload["field_required[]"] = []
        for field in fields:
            payload["field_id[]"].append(str(field.pk))
            payload["field_label[]"].append(field.label)
            payload["field_key[]"].append(field.field_key)
            payload["field_type[]"].append(field.field_type)
            payload["field_placeholder[]"].append(field.placeholder)
            payload["field_help_text[]"].append(field.help_text)
            payload["field_choices[]"].append(field.choices_text)
            payload["field_depends_on_key[]"].append(field.depends_on_key)
            payload["field_depends_on_value[]"].append(field.depends_on_value)
            payload["field_maps_to[]"].append(field.maps_to)
            if field.required:
                payload["field_required[]"].append(str(field.pk))
        payload.update(overrides)
        return payload, fields

    def test_activity_upload_mirrors_are_added_to_an_existing_custom_step_form(self):
        ProposalWizardStepConfig.objects.get_or_create(
            step_no=17,
            defaults={
                "title": "Details of Activities",
                "display_order": 17,
            },
        )
        DynamicFormTemplate.objects.filter(
            proposal_wizard_step=17,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        ).delete()
        form_obj = DynamicFormTemplate.objects.create(
            name="Custom activity fields",
            slug="custom-activity-fields",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=17,
        )
        DynamicFormField.objects.create(
            form=form_obj,
            field_key="office_note",
            label="Office Note",
            order=1,
        )

        response = self.admin_client.get(reverse("wizard_step_edit", args=[17]))
        self.assertEqual(response.status_code, 200)
        keys = set(form_obj.fields.values_list("field_key", flat=True))
        self.assertEqual(
            keys,
            {"office_note", "work_plan_file", "gantt_chart_file"},
        )
        self.assertContains(response, "Office Note")
        self.assertContains(response, "Work Plan File")
        self.assertContains(response, "Gantt Chart File")

    def test_activity_step_editor_links_to_its_proposal_template_slots(self):
        response = self.admin_client.get(reverse("wizard_step_edit", args=[17]))
        self.assertEqual(response.status_code, 200)
        for key in (
            "program_work_plan_template.xlsx",
            "project_work_plan_template.xlsx",
            "program_gantt_chart_template.xlsx",
            "project_gantt_chart_template.xlsx",
        ):
            self.assertContains(
                response,
                reverse("proposal_template_edit", args=[key]),
            )
        self.assertContains(response, 'name="template_download_heading"')
        self.assertContains(response, 'name="work_plan_download_label"')
        self.assertContains(response, 'name="gantt_chart_download_label"')

    def test_activity_step_download_copy_and_native_upload_labels_are_editable(self):
        from accounts.models import Profile
        from proposals.models import Proposal

        payload, fields = self._step_editor_payload(17)
        payload.update(
            {
                "template_download_heading": "Activity Workbook Files",
                "template_download_instructions": "Download, complete, and re-upload each workbook.",
                "work_plan_download_label": "Get the Activity Plan",
                "gantt_chart_download_label": "Get the Timeline",
            }
        )
        for index, field in enumerate(fields):
            if field.field_key == "work_plan_file":
                payload["field_label[]"][index] = "Completed Activity Plan"
                payload["field_help_text[]"][index] = "Attach the revised activity plan workbook."
            elif field.field_key == "gantt_chart_file":
                payload["field_label[]"][index] = "Completed Timeline"
                payload["field_help_text[]"][index] = "Attach the revised Gantt workbook."
        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[17]), payload
        )
        self.assertEqual(response.status_code, 302)

        owner = factories.make_user("admin_edit_activity_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=owner, scope_type="PROJECT")
        wizard = factories.make_client(owner).get(
            reverse("proposal_wizard", args=[proposal.pk, 17])
        )
        self.assertEqual(wizard.status_code, 200)
        for text in (
            "Activity Workbook Files",
            "Download, complete, and re-upload each workbook.",
            "Get the Activity Plan",
            "Get the Timeline",
            "Completed Activity Plan",
            "Attach the revised activity plan workbook.",
            "Completed Timeline",
            "Attach the revised Gantt workbook.",
        ):
            self.assertContains(wizard, text)
        self.assertContains(wizard, 'name="work_plan_file"', count=1)
        self.assertContains(wizard, 'name="gantt_chart_file"', count=1)

    def test_funding_step_download_copy_and_upload_labels_are_editable(self):
        from accounts.models import Profile
        from proposals.models import Proposal

        payload, fields = self._step_editor_payload(18)
        payload.update(
            {
                "template_download_heading": "Funding Workbook",
                "template_download_instructions": "Fill out the workbook and attach it here.",
                "funding_download_label": "Get Funding Workbook",
            }
        )
        for index, field in enumerate(fields):
            if field.field_key == "funding_file":
                payload["field_label[]"][index] = "Completed Funding Plan"
                payload["field_help_text[]"][index] = "Use the approved funding workbook."
        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[18]), payload
        )
        self.assertEqual(response.status_code, 302)

        owner = factories.make_user("admin_edit_funding_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=owner, scope_type="PROJECT")
        wizard = factories.make_client(owner).get(
            reverse("proposal_wizard", args=[proposal.pk, 18])
        )
        self.assertEqual(wizard.status_code, 200)
        for text in (
            "Funding Workbook",
            "Fill out the workbook and attach it here.",
            "Get Funding Workbook",
            "Completed Funding Plan",
            "Use the approved funding workbook.",
        ):
            self.assertContains(wizard, text)
        self.assertContains(wizard, 'name="funding_file"', count=1)

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
        self.assertContains(response, "vendor/sortable.min.js")
        self.assertContains(response, reverse("wizard_steps_reorder"))
        self.assertContains(response, "fetch(reorderUrl")
        self.assertContains(response, "goey-toast-root")
        self.assertContains(response, "goey/toaster.js")
        self.assertContains(response, 'showToast("success"')
        self.assertNotContains(response, "window.location.reload")

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

    def test_step_19_and_20_editor_mirrors_match_wizard_requirements(self):
        from accounts.models import Profile
        from proposals.models import Proposal
        from proposals.views.wizard import is_step_complete

        payload_19, fields_19 = self._step_editor_payload(19)
        self.assertEqual(
            [f.field_key for f in fields_19],
            ["research_abstract_file", "complete_research_file"],
        )
        # Admin marks Complete Research optional (unchecks Req. on second row).
        payload_19["field_required[]"] = [str(fields_19[0].id)]
        resp_19 = self.admin_client.post(
            reverse("wizard_step_edit", args=[19]), payload_19
        )
        self.assertEqual(resp_19.status_code, 302)

        owner = factories.make_user("admin_step19_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(
            created_by=owner,
            extension_type=Proposal.ExtensionType.RESEARCH_STUDENT,
        )
        # Without research_abstract_file, Step 19 is still incomplete; once
        # abstract is present, optional complete_research_file does not block.
        self.assertFalse(is_step_complete(proposal, 19))
        from django.core.files.uploadedfile import SimpleUploadedFile

        proposal.research_abstract_file = SimpleUploadedFile("abs.pdf", b"%PDF-1.4")
        proposal.save(update_fields=["research_abstract_file"])
        self.assertTrue(is_step_complete(proposal, 19))

        wizard_19 = factories.make_client(owner).get(
            reverse("proposal_wizard", args=[proposal.pk, 19])
        )
        self.assertContains(wizard_19, "(Optional)")

        # Step 20 editor seeds certificate_of_completion_file for RESEARCH_FACULTY only.
        _payload_20, fields_20 = self._step_editor_payload(20)
        self.assertEqual(
            [f.field_key for f in fields_20],
            ["certificate_of_completion_file"],
        )
        self.assertEqual(fields_20[0].depends_on_value, "RESEARCH_FACULTY")

    def test_wizard_step_editor_uses_multi_row_aligned_field_cards(self):
        # Step 1 contains both SELECT (extension_type) and TEXTfields, while
        # Step 17 renders the Template Download Section and Step 19 renders FILE mirrors.
        resp_1 = self.admin_client.get(reverse("wizard_step_edit", args=[1]))
        self.assertEqual(resp_1.status_code, 200)
        html_1 = resp_1.content.decode()

        # Field rows are never crammed 6-across into md:col-span-2 cells.
        self.assertNotIn("md:col-span-2 flex items-end justify-end", html_1)
        self.assertNotIn("md:grid-cols-2 xl:grid-cols-3", html_1)
        self.assertIn("data-field-badge", html_1)
        self.assertIn("data-field-conditions-grid", html_1)
        self.assertIn("nx-btn--icon nx-btn--compact", html_1)
        self.assertNotIn("Repeatable group", html_1)
        # SELECT fields display their dropdown choices box; non-SELECT fields hide it.
        self.assertIn('class="choices-cell "', html_1)
        self.assertIn('class="choices-cell hidden"', html_1)
        # Dynamic builder script stays synchronized with server-rendered field rows.
        self.assertIn("function renumberFieldRows()", html_1)
        self.assertIn("function syncFieldChoices(", html_1)

        resp_17 = self.admin_client.get(reverse("wizard_step_edit", args=[17]))
        self.assertEqual(resp_17.status_code, 200)
        html_17 = resp_17.content.decode()
        self.assertIn("lg:grid-cols-3", html_17)
        self.assertIn('name="template_download_instructions"', html_17)

        resp_create = self.admin_client.get(reverse("wizard_step_create"))
        self.assertEqual(resp_create.status_code, 200)
        html_create = resp_create.content.decode()
        self.assertNotIn("md:grid-cols-3 xl:grid-cols-4", html_create)
        self.assertIn("nx-page-header", html_create)

    def test_multiple_new_fields_preserve_independent_required_flags(self):
        payload, _fields = self._step_editor_payload(2)
        payload["field_id[]"] = ["", ""]
        payload["field_label[]"] = ["Optional Subtitle", "Mandatory Tagline"]
        payload["field_key[]"] = ["optional_subtitle", "mandatory_tagline"]
        payload["field_type[]"] = ["TEXT", "TEXT"]
        payload["field_placeholder[]"] = ["", ""]
        payload["field_help_text[]"] = ["", ""]
        payload["field_choices[]"] = ["", ""]
        payload["field_depends_on_key[]"] = ["", ""]
        payload["field_depends_on_value[]"] = ["", ""]
        payload["field_maps_to[]"] = ["", ""]
        payload["field_required[]"] = ["new_1"]

        resp = self.admin_client.post(reverse("wizard_step_edit", args=[2]), payload)
        self.assertEqual(resp.status_code, 302)

        form = DynamicFormTemplate.objects.get(proposal_wizard_step=2)
        created = list(form.fields.order_by("order"))
        self.assertEqual(
            [(f.field_key, f.required) for f in created],
            [("optional_subtitle", False), ("mandatory_tagline", True)],
        )
