"""
The no-code builder's "repeatable group" settings.

Step 3 (Proponents) is the first consumer: the office defines which fields each
proponent row shows and which proponent record column each field fills in. The
panel lives in the wizard step editor, which is exercised here.
"""

from django.urls import reverse
from django.test import TestCase

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
            row["field_id"] or "new" for row in rows if row["required"]
        ],
    }
    payload.update(extra)
    return payload


class StepEditorRepeaterTests(TestCase):
    def setUp(self):
        self.admin_user, self.admin_client = factories.admin()
        # Opening the editor is what creates/seeds the step's form.
        self._open_step(3)

    def _open_step(self, step_no):
        return self.admin_client.get(reverse("wizard_step_edit", args=[step_no]))

    def _form(self, step_no=3):
        return DynamicFormTemplate.objects.filter(proposal_wizard_step=step_no).first()

    def test_the_step_three_editor_shows_the_default_proponent_fields(self):
        form = self._form()
        self.assertIsNotNone(form)
        self.assertTrue(form.is_repeater)
        self.assertEqual(form.row_store, DynamicFormTemplate.RowStore.PROPONENT)

        response = self._open_step(3)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Position / Designation")
        self.assertContains(response, "Repeatable group")
        self.assertContains(response, 'name="field_maps_to[]"')
        self.assertContains(response, "Proponents of the proposal")

    def test_saving_the_step_persists_the_group_settings(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]

        response = self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(
                rows,
                title="Proponents",
                description="People behind the proposal",
                instructions="",
                is_visible="on",
                is_required="on",
                is_repeater="on",
                repeater_label="Project staff",
                repeater_min_rows="2",
                repeater_max_rows="5",
                row_store="PROPONENT",
            ),
        )
        self.assertEqual(response.status_code, 302)

        form.refresh_from_db()
        self.assertTrue(form.is_repeater)
        self.assertEqual(form.repeater_label, "Project staff")
        self.assertEqual(form.repeater_min_rows, 2)
        self.assertEqual(form.repeater_max_rows, 5)
        self.assertEqual(form.row_store, DynamicFormTemplate.RowStore.PROPONENT)

    def test_an_impossible_row_window_is_clamped(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]

        self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(
                rows,
                title="Proponents",
                is_repeater="on",
                repeater_min_rows="9",
                repeater_max_rows="3",
                row_store="PROPONENT",
            ),
        )

        form.refresh_from_db()
        self.assertEqual(form.repeater_max_rows, 3)
        self.assertEqual(form.repeater_min_rows, 3)

    def test_turning_the_group_off_clears_the_proponent_mapping(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]

        self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(rows, title="Proponents", row_store="PROPONENT"),
        )

        form.refresh_from_db()
        self.assertFalse(form.is_repeater)
        self.assertEqual(form.fields.exclude(maps_to="").count(), 0)

    def test_free_standing_rows_cannot_claim_proponent_columns(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]

        self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(
                rows, title="Proponents", is_repeater="on", row_store="GENERIC"
            ),
        )

        form.refresh_from_db()
        self.assertEqual(form.row_store, DynamicFormTemplate.RowStore.GENERIC)
        self.assertEqual(form.fields.exclude(maps_to="").count(), 0)

    def test_two_fields_cannot_map_to_the_same_column(self):
        form = self._form()
        rows = [field_row(field) for field in form.fields.order_by("order")]
        rows.append(field_row(None, label="Nickname", key="nickname", maps_to="full_name"))

        self.admin_client.post(
            reverse("wizard_step_edit", args=[3]),
            payload_from_rows(
                rows, title="Proponents", is_repeater="on", row_store="PROPONENT"
            ),
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
