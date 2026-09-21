"""
Step 3 (Proponents) as an admin-built repeatable group.

Step 3 used to be a hardcoded roster of six inputs. It is now a repeatable
group: the admin decides which fields each proponent row shows, whether they
are required, and how many rows are allowed, and every row is still a real
``ProposalProponent`` record so the generated documents keep working.

These tests cover the contract from both ends:

* the admin edits the group (fields, mapping, limits) and
* the proponent fills it in (add rows by hand, add rows from an account,
  remove, reorder, and hit the required-field gate).
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import DynamicFormField, DynamicFormResponse, DynamicFormRow, DynamicFormTemplate

from .models import Proposal, ProposalProponent


def mapped_fields(form):
    return list(form.fields.order_by("order").values_list("field_key", "label", "maps_to"))


class ProponentRepeaterSeedTests(TestCase):
    """The step must work before an admin ever opens the builder."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("pr_seed_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 3])

    def test_opening_step_three_seeds_the_default_proponent_group(self):
        self.assertEqual(DynamicFormTemplate.objects.filter(proposal_wizard_step=3).count(), 0)

        self.assertEqual(self.client_owner.get(self.url).status_code, 200)

        form = DynamicFormTemplate.objects.get(proposal_wizard_step=3)
        self.assertTrue(form.is_repeater)
        self.assertEqual(form.row_store, DynamicFormTemplate.RowStore.PROPONENT)
        self.assertEqual(form.repeater_label, "Proponent")
        self.assertEqual(
            [key for key, _label, _maps in mapped_fields(form)],
            ["full_name", "designation", "specialization", "role", "cp_number", "email"],
        )

    def test_the_default_name_field_is_required_and_writes_to_the_proponent(self):
        self.client_owner.get(self.url)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=3)
        name_field = form.fields.get(field_key="full_name")
        self.assertTrue(name_field.required)
        self.assertEqual(name_field.maps_to, DynamicFormField.MapsTo.FULL_NAME)

    def test_seeding_never_overwrites_an_admins_own_layout(self):
        self.client_owner.get(self.url)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=3)
        form.fields.all().delete()
        DynamicFormField.objects.create(
            form=form, label="Only Field", field_key="only_field", order=1
        )

        self.client_owner.get(self.url)

        self.assertEqual(form.fields.count(), 1)
        self.assertEqual(form.fields.get().label, "Only Field")

    def test_opening_step_three_twice_does_not_duplicate_fields(self):
        self.client_owner.get(self.url)
        self.client_owner.get(self.url)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=3)
        self.assertEqual(form.fields.count(), 6)


class ProponentRepeaterFillTests(TestCase):
    """What a proponent sees and saves on step 3."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("pr_fill_owner", Profile.ROLE_FACULTY)
        cls.colleague = factories.make_user(
            "pr_fill_colleague", Profile.ROLE_FACULTY, full_name="Maria Santos"
        )

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 3])
        self.client_owner.get(self.url)
        self.form = DynamicFormTemplate.objects.get(proposal_wizard_step=3)
        self.fields_by_key = {field.field_key: field for field in self.form.fields.all()}

    def _row_payload(self, index, **values):
        payload = {
            f"repeater_{self.form.id}_rows": index + 1,
            f"repeater_{self.form.id}_row_id_{index}": "",
            f"repeater_{self.form.id}_row_id_{index + 1}": "",
        }
        for key, value in values.items():
            field = self.fields_by_key[key]
            payload[f"repeater_{self.form.id}_row_{index}_field_{field.id}"] = value
        return payload

    def test_the_admin_defined_labels_are_rendered(self):
        response = self.client_owner.get(self.url)
        self.assertContains(response, "Position / Designation")
        self.assertContains(response, "Specialization")
        self.assertContains(response, "CP Number")

    def test_a_proponent_can_type_in_a_row_by_hand(self):
        payload = self._row_payload(
            0,
            full_name="Juan Dela Cruz",
            designation="Assistant Professor I",
            specialization="Agronomy",
            cp_number="09171234567",
            email="juan@example.com",
        )
        payload["action"] = "next"

        response = self.client_owner.post(self.url, payload)
        self.assertEqual(response.status_code, 302)

        row = ProposalProponent.objects.get(proposal=self.proposal)
        self.assertIsNone(row.user)
        self.assertEqual(row.full_name, "Juan Dela Cruz")
        self.assertEqual(row.designation, "Assistant Professor I")
        self.assertEqual(row.specialization, "Agronomy")
        self.assertEqual(row.cp_number, "09171234567")
        self.assertEqual(row.email, "juan@example.com")

    def test_an_extra_admin_field_is_kept_on_the_proponent(self):
        extra = DynamicFormField.objects.create(
            form=self.form,
            label="Faculty Rank",
            field_key="faculty_rank",
            field_type=DynamicFormField.FieldType.TEXT,
            order=10,
        )
        payload = self._row_payload(0, full_name="Ana Reyes")
        payload[f"repeater_{self.form.id}_row_0_field_{extra.id}"] = "Instructor III"
        payload["action"] = "next"

        self.client_owner.post(self.url, payload)

        row = ProposalProponent.objects.get(proposal=self.proposal)
        self.assertEqual(row.extra_fields, {"faculty_rank": "Instructor III"})

    def test_blank_rows_are_not_saved(self):
        payload = self._row_payload(0, full_name="Juan Dela Cruz")
        payload[f"repeater_{self.form.id}_rows"] = 3
        payload[f"repeater_{self.form.id}_row_id_1"] = ""
        payload[f"repeater_{self.form.id}_row_id_2"] = ""
        payload["action"] = "next"

        self.client_owner.post(self.url, payload)

        self.assertEqual(self.proposal.proponents.count(), 1)

    def test_a_missing_required_field_blocks_save_and_next(self):
        payload = self._row_payload(0, designation="Instructor")  # no Name
        payload["action"] = "next"

        response = self.client_owner.post(self.url, payload, follow=True)

        self.assertContains(response, "Please complete the required field(s)")
        self.assertNotContains(response, "admin-managed")
        self.assertNotIn(3, self.proposal.completed_steps or [])

    def test_the_step_is_not_complete_until_required_details_exist(self):
        self.client_owner.post(self.url, self._row_payload(0, full_name="Juan Dela Cruz"))

        self.proposal.refresh_from_db()
        self.assertIn(3, self.proposal.completed_steps or [])

    def test_more_than_one_proponent_can_be_entered(self):
        payload = self._row_payload(0, full_name="Juan Dela Cruz")
        payload.update(self._row_payload(1, full_name="Ana Reyes"))
        payload[f"repeater_{self.form.id}_rows"] = 2
        payload["action"] = "next"

        self.client_owner.post(self.url, payload)

        names = list(
            self.proposal.proponents.order_by("sort_order").values_list("full_name", flat=True)
        )
        self.assertEqual(names, ["Juan Dela Cruz", "Ana Reyes"])

    def test_picking_an_existing_account_still_adds_a_row(self):
        payload = {
            "action": "add_member",
            "add_user_id": str(self.colleague.id),
        }

        self.client_owner.post(self.url, payload)

        row = ProposalProponent.objects.get(proposal=self.proposal)
        self.assertEqual(row.user, self.colleague)
        self.assertEqual(row.full_name, "Maria Santos")

    def test_saved_rows_can_be_edited_and_removed(self):
        self.client_owner.post(self.url, self._row_payload(0, full_name="Juan Dela Cruz"))
        self.client_owner.post(self.url, self._row_payload(1, full_name="Ana Reyes"))
        first, second = self.proposal.proponents.order_by("sort_order")

        payload = self._row_payload(0, full_name="Juan D. Cruz")
        payload[f"repeater_{self.form.id}_row_id_0"] = str(first.id)
        payload[f"repeater_{self.form.id}_row_id_1"] = str(second.id)
        payload[f"repeater_{self.form.id}_remove"] = str(second.id)
        payload["action"] = "save_members"

        self.client_owner.post(self.url, payload)

        self.assertEqual(self.proposal.proponents.count(), 1)
        self.assertEqual(self.proposal.proponents.get().full_name, "Juan D. Cruz")

    def test_the_creator_row_cannot_be_removed(self):
        ProposalProponent.objects.create(
            proposal=self.proposal,
            user=self.owner,
            full_name="Owner Name",
            role="Project Leader",
        )
        creator_row = self.proposal.proponents.get(user=self.owner)

        payload = {
            "action": "save_members",
            f"repeater_{self.form.id}_rows": 1,
            f"repeater_{self.form.id}_row_id_0": str(creator_row.id),
            f"repeater_{self.form.id}_remove": str(creator_row.id),
        }
        self.client_owner.post(self.url, payload)

        self.assertTrue(self.proposal.proponents.filter(id=creator_row.id).exists())

    def test_rows_can_be_reordered(self):
        self.client_owner.post(self.url, self._row_payload(0, full_name="Juan Dela Cruz"))
        self.client_owner.post(self.url, self._row_payload(1, full_name="Ana Reyes"))
        first, second = self.proposal.proponents.order_by("sort_order")

        # A move button submits the whole step, exactly like the browser does.
        payload = self._row_payload(0, full_name="Juan Dela Cruz")
        payload.update(self._row_payload(1, full_name="Ana Reyes"))
        payload.update(
            {
                "action": "save_members",
                f"repeater_{self.form.id}_rows": 2,
                f"repeater_{self.form.id}_row_id_0": str(first.id),
                f"repeater_{self.form.id}_row_id_1": str(second.id),
                f"repeater_{self.form.id}_move": f"{second.id}:up",
            }
        )
        self.client_owner.post(self.url, payload)

        names = list(self.proposal.proponents.values_list("full_name", flat=True))
        self.assertEqual(names, ["Ana Reyes", "Juan Dela Cruz"])

    def test_the_maximum_row_count_is_enforced(self):
        self.form.repeater_max_rows = 1
        self.form.save(update_fields=["repeater_max_rows"])

        payload = self._row_payload(0, full_name="Juan Dela Cruz")
        payload.update(self._row_payload(1, full_name="Ana Reyes"))
        payload[f"repeater_{self.form.id}_rows"] = 2
        payload["action"] = "next"

        response = self.client_owner.post(self.url, payload, follow=True)

        self.assertContains(response, "maximum of 1")
        self.assertEqual(self.proposal.proponents.count(), 1)

    def test_a_read_only_proposal_shows_the_rows_without_edit_controls(self):
        ProposalProponent.objects.create(
            proposal=self.proposal, full_name="Juan Dela Cruz", cp_number="0917"
        )
        self.proposal.proposal_status = Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW
        self.proposal.save(update_fields=["proposal_status"])

        response = self.client_owner.get(self.url)

        self.assertContains(response, "Juan Dela Cruz")
        self.assertNotContains(response, "+ Add Proponent")


class ProponentRepeaterFallbackTests(TestCase):
    """Turning the repeatable group off must not break Step 3."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("pr_fallback_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 3])
        self.client_owner.get(self.url)
        self.form = DynamicFormTemplate.objects.get(proposal_wizard_step=3)

    def test_without_a_repeater_the_built_in_roster_is_used(self):
        self.form.is_repeater = False
        self.form.save(update_fields=["is_repeater"])
        row = ProposalProponent.objects.create(proposal=self.proposal, full_name="Juan Dela Cruz")

        response = self.client_owner.get(self.url)

        self.assertContains(response, "Current Proponents")
        self.assertContains(response, f"p_{row.id}_designation")

    def test_the_built_in_roster_still_saves_its_own_fields(self):
        self.form.is_repeater = False
        self.form.save(update_fields=["is_repeater"])
        row = ProposalProponent.objects.create(proposal=self.proposal, full_name="Juan Dela Cruz")

        payload = {
            "action": "save_members",
            f"p_{row.id}_designation": "Professor V",
            f"p_{row.id}_specialization": "Soil Science",
            f"p_{row.id}_cp_number": "09998887777",
            f"p_{row.id}_email": "juan@example.com",
        }
        self.client_owner.post(self.url, payload)

        row.refresh_from_db()
        self.assertEqual(row.designation, "Professor V")
        self.assertEqual(row.specialization, "Soil Science")
        self.assertEqual(row.cp_number, "09998887777")
        self.assertEqual(row.email, "juan@example.com")


class GenericRepeaterTests(TestCase):
    """The same repeatable-group feature on a non-proponent step."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("pr_generic_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 5])
        self.form = DynamicFormTemplate.objects.create(
            name="Partner organisations",
            slug="partner-organisations",
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=5,
            is_repeater=True,
            repeater_label="Partner",
            row_store=DynamicFormTemplate.RowStore.GENERIC,
            blocks_proposal_submission=False,
        )
        self.name_field = DynamicFormField.objects.create(
            form=self.form, label="Organisation", field_key="organisation", order=1
        )
        self.contact_field = DynamicFormField.objects.create(
            form=self.form, label="Contact person", field_key="contact", order=2
        )

    def test_rows_are_saved_as_form_rows(self):
        payload = {
            "action": "next",
            f"repeater_{self.form.id}_rows": 1,
            f"repeater_{self.form.id}_row_id_0": "",
            f"repeater_{self.form.id}_row_0_field_{self.name_field.id}": "ISPSC",
            f"repeater_{self.form.id}_row_0_field_{self.contact_field.id}": "Dr. Reyes",
        }

        self.client_owner.post(self.url, payload)

        response = DynamicFormResponse.objects.get(form=self.form, proposal=self.proposal)
        row = DynamicFormRow.objects.get(response=response)
        self.assertEqual(row.data, {"organisation": "ISPSC", "contact": "Dr. Reyes"})

    def test_a_saved_row_can_be_removed(self):
        self.client_owner.post(
            self.url,
            {
                "action": "next",
                f"repeater_{self.form.id}_rows": 1,
                f"repeater_{self.form.id}_row_id_0": "",
                f"repeater_{self.form.id}_row_0_field_{self.name_field.id}": "ISPSC",
            },
        )
        row = DynamicFormRow.objects.get()
        response = row.response

        self.client_owner.post(
            self.url,
            {
                "action": "save_members",
                f"repeater_{self.form.id}_rows": 1,
                f"repeater_{self.form.id}_row_id_0": str(row.id),
                f"repeater_{self.form.id}_remove": str(row.id),
            },
        )

        self.assertEqual(response.rows.count(), 0)
