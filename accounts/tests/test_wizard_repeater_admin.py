"""
Automatic proponent repeatable-group behavior in the wizard step editor.

Step 3 (Proponents) is automatically configured as a proponent-storing
repeatable group without exposing a manual "Repeatable group" panel in the
step editor UI. Admins can still rename, reorder, add, or map fields on Step 3
while every other step keeps a clean non-repeater editor.
"""

from django.test import TestCase
from django.urls import reverse

from details.models import DynamicFormField, DynamicFormTemplate

from . import factories


def field_row(field=None, **overrides):
    """One row of the builder's parallel ``field_*[]`` arrays."""
    row = {
        "field_id": str(field.id) if field else "",
        "label": field.label if field else "Field",
        "key": field.field_key if field else "field_key",
        "type": field.field_type if field else DynamicFormField.FieldType.TEXT,
        "placeholder": field.placeholder if field else "",
        "help_text": field.help_text if field else "",
        "choices": field.choices_text if field else "",
        "depends_on_key": field.depends_on_key if field else "",
        "depends_on_value": field.depends_on_value if field else "",
        "maps_to": field.maps_to if field else "",
        "required": field.required if field else False,
    }
    row.update(overrides)
    return row


def payload_from_rows(rows, **extra):
    payload = {
        "field_id[]": [row["field_id"] for row in rows],
        "field_label[]": [row["label"] for row in rows],
        "field_key[]": [row["key"] for row in rows],
        "field_type[]": [row["type"] for row in rows],
        "field_placeholder[]": [row["placeholder"] for row in rows],
        "field_help_text[]": [row["help_text"] for row in rows],
        "field_choices[]": [row["choices"] for row in rows],
        "field_depends_on_key[]": [row["depends_on_key"] for row in rows],
        "field_depends_on_value[]": [row["depends_on_value"] for row in rows],
        "field_maps_to[]": [row["maps_to"] for row in rows],
        "field_required[]": [
            row["field_id"] or f"new_{idx}"
            for idx, row in enumerate(rows)
            if row["required"]
        ],
    }
    payload.update(extra)
    return payload


class StepEditorRepeaterTests(TestCase):
    def setUp(self):
        self.admin_user, self.admin_client = factories.admin()
        # Opening the editor creates/seeds the step's form.
        self._open_step(3)

    def _open_step(self, step_no):
        return self.admin_client.get(reverse("wizard_step_edit", args=[step_no]))

    def _form(self, step_no=3):
        return DynamicFormTemplate.objects.filter(proposal_wizard_step=step_no).first()

    def test_step_editor_removes_repeatable_group_panel_everywhere(self):
        for url in (
            reverse("wizard_step_edit", args=[1]),
            reverse("wizard_step_edit", args=[3]),
            reverse("wizard_step_edit", args=[19]),
            reverse("wizard_step_create"),
        ):
            with self.subTest(url=url):
                response = self.admin_client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Repeatable group")
                self.assertNotContains(response, "Repeat these fields")
                self.assertNotContains(response, 'name="is_repeater"')
                self.assertNotContains(response, 'name="repeater_label"')
                self.assertNotContains(response, 'name="repeater_min_rows"')
                self.assertNotContains(response, 'name="repeater_max_rows"')
                self.assertNotContains(response, 'name="row_store"')

    def test_the_step_three_editor_shows_the_default_proponent_fields(self):
        form = self._form()
        self.assertIsNotNone(form)
        self.assertTrue(form.is_repeater)
        self.assertEqual(form.row_store, DynamicFormTemplate.RowStore.PROPONENT)

        response = self._open_step(3)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Position / Designation")
        self.assertContains(response, 'name="field_maps_to[]"')
        self.assertContains(response, 'data-proponent-step="true"')

    def test_saving_step_three_preserves_automatic_proponent_repeater_and_mappings(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]
        rows[1]["label"] = "Academic Rank / Designation"

        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(
                rows,
                title="Proponents",
                description="People behind the proposal",
                instructions="",
                is_visible="on",
                is_required="on",
            ),
        )
        self.assertEqual(response.status_code, 302)

        form.refresh_from_db()
        self.assertTrue(form.is_repeater)
        self.assertEqual(form.row_store, DynamicFormTemplate.RowStore.PROPONENT)
        self.assertEqual(form.repeater_label, "Proponent")
        self.assertEqual(
            form.fields.get(field_key="designation").label,
            "Academic Rank / Designation",
        )
        self.assertEqual(form.fields.exclude(maps_to="").count(), 6)

    def test_non_proponent_steps_cannot_claim_proponent_columns(self):
        self._open_step(2)
        form = self._form(2)
        rows = [field_row(field, maps_to="full_name") for field in form.fields.order_by("order")]

        self.admin_client.post(
            reverse("wizard_step_edit", args=[2]),
            payload_from_rows(rows, title="Title", is_visible="on", is_required="on"),
        )

        form.refresh_from_db()
        self.assertFalse(form.is_repeater)
        self.assertEqual(form.fields.exclude(maps_to="").count(), 0)

    def test_two_fields_cannot_map_to_the_same_column(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]
        rows.append(field_row(None, label="Nickname", key="nickname", maps_to="full_name"))

        self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(rows, title="Proponents", is_visible="on", is_required="on"),
        )

        self.assertEqual(
            form.fields.filter(maps_to="full_name").count(),
            1,
        )
        self.assertEqual(form.fields.get(field_key="nickname").maps_to, "")

    def test_the_step_editor_does_not_seed_a_step_that_is_not_proponents(self):
        self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows([], title="Something Else", is_visible="on", is_required="on"),
        )

        response = self._open_step(3)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._form().is_repeater)
        self.assertEqual(self._form().fields.exclude(maps_to="").count(), 0)


class DefaultFieldSeederTests(TestCase):
    """The wizard's built-in defaults must not edit an admin's form."""

    def test_an_edited_form_is_left_alone_by_the_seeder(self):
        from accounts.views.builders import _seed_default_fields
        from details.models import ProposalWizardStepConfig
        from proposals.views.constants import INITIAL_STEP_LABELS

        # The migrations seed the built-in steps; rebuild them from the same
        # list so the test does not depend on what a migration happened to
        # write (step_no is unique).
        ProposalWizardStepConfig.objects.all().delete()
        ProposalWizardStepConfig.objects.bulk_create(
            [
                ProposalWizardStepConfig(
                    step_no=item["no"],
                    title=item["title"],
                    description=item["desc"],
                    is_visible=True,
                    is_required=True,
                )
                for item in INITIAL_STEP_LABELS
            ]
        )

        form = DynamicFormTemplate.objects.create(
            name="Office fields for step 1",
            slug="office-fields-step-1",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=1,
            is_active=True,
        )
        DynamicFormField.objects.create(
            form=form, label="Only field", field_key="only_field", order=1
        )

        _seed_default_fields()

        self.assertEqual(list(form.fields.values_list("field_key", flat=True)), ["only_field"])
