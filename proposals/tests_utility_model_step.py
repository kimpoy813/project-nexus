"""
The Utility Model step and the "ISPSC Extension Agenda" rename.

Step 6 used to label its second checklist "ISPSC Extension Thrust"; the office
renamed it to "ISPSC Extension Agenda". Right after it, step 7 is the new
Utility Model step, which asks for the Title of Technology, the Utility Model
Registration Number and the Utility Model Description. Every one of the three
is answered - a proponent writes "N/A" when the proposal has no technology or
utility model behind it - so the step only counts as complete once all three
hold text.

Inserting a step at 7 moved every later built-in step up by one, so these
tests also pin the parts of the wizard that key off a step number: the seeded
step list, the per-step templates, the save handlers and the data migration
that renumbers a deployed database.
"""

import importlib

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from details.models import DynamicFormTemplate, ProposalWizardStepConfig
from proposals.models import Proposal, ProposalReviewRound, ProposalSectionComment
from proposals.views.constants import (
    INITIAL_STEP_LABELS,
    LAST_BUILTIN_STEP_NO,
    UTILITY_MODEL_STEP_NO,
)
from proposals.views.wizard import _wizard_step_config_map, is_step_complete


utility_migration = importlib.import_module("details.migrations.0027_utility_model_step")


def seed_default_steps(*, keep_default_forms=False):
    """The built-in step list, the way the first wizard visit seeds it.

    The same first visit seeds a "Fields for Step N" form on the steps that
    have built-in fields (including the new step 7). Those forms add required
    ``dynamic_field_<id>`` inputs that mirror the native ones, so tests that
    post native fields drop them unless they want that behaviour.
    """
    ProposalWizardStepConfig.objects.all().delete()
    DynamicFormTemplate.objects.all().delete()
    _wizard_step_config_map()
    if not keep_default_forms:
        DynamicFormTemplate.objects.all().delete()


class StepListTests(TestCase):
    def test_utility_model_follows_the_extension_agenda_step(self):
        titles = {item["no"]: item["title"] for item in INITIAL_STEP_LABELS}
        self.assertEqual(titles[6], "SDGs / Extension Agenda")
        self.assertEqual(titles[UTILITY_MODEL_STEP_NO], "Utility Model")
        self.assertEqual(UTILITY_MODEL_STEP_NO, 7)
        # Budgetary Requirement, which used to be step 7, follows it.
        self.assertEqual(titles[8], "Budgetary Requirement")
        self.assertEqual(titles[LAST_BUILTIN_STEP_NO], "Certificate of Completion Upload")
        self.assertEqual(LAST_BUILTIN_STEP_NO, 20)

    def test_the_step_six_description_no_longer_says_thrust(self):
        desc = next(item["desc"] for item in INITIAL_STEP_LABELS if item["no"] == 6)
        self.assertNotIn("thrust", desc.lower())
        self.assertIn("agenda", desc.lower())

    def test_step_numbers_are_contiguous(self):
        self.assertEqual(
            [item["no"] for item in INITIAL_STEP_LABELS],
            list(range(1, LAST_BUILTIN_STEP_NO + 1)),
        )

    def test_every_built_in_step_has_its_own_template(self):
        """Each built-in step renders its own page, not the generic fallback.

        Inserting a step renamed ``step_7.html`` .. ``step_19.html`` up by
        one; a missing file would silently drop a step back to the
        admin-fields-only page.
        """
        from django.template.loader import get_template

        for item in INITIAL_STEP_LABELS:
            with self.subTest(step=item["no"]):
                get_template(f"services/wizard/step_{item['no']}.html")


class ExtensionAgendaRenameTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("agenda_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def test_step_six_labels_the_checklist_extension_agenda(self):
        response = self.client_owner.get(reverse("proposal_wizard", args=[self.proposal.id, 6]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ISPSC Extension Agenda")
        self.assertNotContains(response, "ISPSC Extension Thrust")

    def test_the_sidebar_shows_utility_model_right_after_extension_agenda(self):
        response = self.client_owner.get(reverse("proposal_wizard", args=[self.proposal.id, 6]))
        html = response.content.decode()
        self.assertLess(html.index("SDGs / Extension Agenda"), html.index("Utility Model"))
        self.assertLess(html.index("Utility Model"), html.index("Budgetary Requirement"))


class UtilityModelStepTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("um_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, UTILITY_MODEL_STEP_NO])

    def test_the_step_asks_for_the_three_utility_model_fields(self):
        response = self.client_owner.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Title of Technology")
        self.assertContains(response, "Utility Model Registration Number")
        self.assertContains(response, "Utility Model Description")
        for name in (
            "technology_title",
            "utility_model_registration_number",
            "utility_model_description",
        ):
            with self.subTest(field=name):
                self.assertContains(response, f'name="{name}"')
        # The page tells the proponent how to answer when it does not apply.
        self.assertContains(response, "N/A")

    def test_the_seeded_admin_form_mirrors_the_native_fields(self):
        """The first wizard visit seeds a "Fields for Step 7" form.

        Its three fields carry the same keys as the native inputs, the same
        way "Fields for Step 8" mirrors Budgetary Requirement, so an admin
        can relabel them from the step editor (``step_fields``).
        """
        seed_default_steps(keep_default_forms=True)
        form = DynamicFormTemplate.objects.get(proposal_wizard_step=UTILITY_MODEL_STEP_NO)
        self.assertEqual(form.name, "Fields for Step 7")
        self.assertEqual(
            list(form.fields.order_by("order").values_list("field_key", "label", "field_type")),
            [
                ("technology_title", "Title of Technology", "TEXT"),
                ("utility_model_registration_number", "Utility Model Registration Number", "TEXT"),
                ("utility_model_description", "Utility Model Description", "TEXTAREA"),
            ],
        )
        for field in form.fields.all():
            field.label = f"Office {field.label}"
            field.save(update_fields=["label"])

        response = self.client_owner.get(self.url)
        self.assertContains(response, "Office Title of Technology")
        self.assertContains(response, "Office Utility Model Description")
        # The native inputs are rendered once each.
        html = response.content.decode()
        self.assertEqual(html.count('name="technology_title"'), 1)
        self.assertEqual(html.count('name="utility_model_registration_number"'), 1)
        self.assertEqual(html.count('name="utility_model_description"'), 1)

    def test_save_and_next_stores_the_answers_and_moves_on(self):
        response = self.client_owner.post(
            self.url,
            {
                "action": "next",
                "technology_title": "Solar-Powered Rice Dryer",
                "utility_model_registration_number": "2-2024-050123",
                "utility_model_description": "A low-cost dryer for smallholder farms.",
            },
        )
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, UTILITY_MODEL_STEP_NO + 1]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.technology_title, "Solar-Powered Rice Dryer")
        self.assertEqual(self.proposal.utility_model_registration_number, "2-2024-050123")
        self.assertEqual(
            self.proposal.utility_model_description, "A low-cost dryer for smallholder farms."
        )
        self.assertIn(UTILITY_MODEL_STEP_NO, self.proposal.completed_steps)

    def test_not_applicable_answers_complete_the_step(self):
        self.client_owner.post(
            self.url,
            {
                "action": "next",
                "technology_title": "N/A",
                "utility_model_registration_number": "N/A",
                "utility_model_description": "N/A",
            },
        )
        self.proposal.refresh_from_db()
        self.assertIn(UTILITY_MODEL_STEP_NO, self.proposal.completed_steps)
        self.assertEqual(self.proposal.technology_title, "N/A")

    def test_a_blank_field_leaves_the_step_incomplete(self):
        """Every field is answered; "N/A" is the way to say it does not apply."""
        response = self.client_owner.post(
            self.url,
            {
                "action": "next",
                "technology_title": "Solar-Powered Rice Dryer",
                "utility_model_registration_number": "",
                "utility_model_description": "N/A",
            },
        )
        self.proposal.refresh_from_db()
        # The partial answer is kept so the proponent can draft gradually...
        self.assertEqual(self.proposal.technology_title, "Solar-Powered Rice Dryer")
        # ...but the step is not ticked off, so submission stays blocked.
        self.assertNotIn(UTILITY_MODEL_STEP_NO, self.proposal.completed_steps)
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, UTILITY_MODEL_STEP_NO + 1]),
            fetch_redirect_response=False,
        )

    def test_skip_marks_the_step_skipped(self):
        response = self.client_owner.post(self.url, {"action": "skip"})
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, UTILITY_MODEL_STEP_NO + 1]),
            fetch_redirect_response=False,
        )
        self.proposal.refresh_from_db()
        self.assertIn(UTILITY_MODEL_STEP_NO, self.proposal.skipped_steps)

    def test_completion_rule_needs_all_three_answers(self):
        proposal = self.proposal
        self.assertFalse(is_step_complete(proposal, UTILITY_MODEL_STEP_NO))
        proposal.technology_title = "N/A"
        proposal.utility_model_registration_number = "N/A"
        self.assertFalse(is_step_complete(proposal, UTILITY_MODEL_STEP_NO))
        proposal.utility_model_description = "  "
        self.assertFalse(is_step_complete(proposal, UTILITY_MODEL_STEP_NO))
        proposal.utility_model_description = "N/A"
        self.assertTrue(is_step_complete(proposal, UTILITY_MODEL_STEP_NO))

    def test_read_only_view_shows_the_saved_answers(self):
        self.proposal.technology_title = "Solar-Powered Rice Dryer"
        self.proposal.utility_model_registration_number = "N/A"
        self.proposal.utility_model_description = "N/A"
        self.proposal.proposal_status = Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW
        self.proposal.is_locked = True
        self.proposal.save()

        response = self.client_owner.get(self.url + "?readonly=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solar-Powered Rice Dryer")
        self.assertContains(response, "readonly")
        self.assertNotContains(response, "Save &amp; Next")


class ShiftedStepsStillSaveTests(TestCase):
    """The steps that moved up by one still save to their own fields."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("shift_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        seed_default_steps()
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def _post(self, step, data):
        return self.client_owner.post(
            reverse("proposal_wizard", args=[self.proposal.id, step]), {"action": "next", **data}
        )

    def test_budgetary_requirement_is_step_eight(self):
        self._post(8, {"budgetary_requirement": "CTE Fund 30,000"})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.budgetary_requirement, "CTE Fund 30,000")
        self.assertIn(8, self.proposal.completed_steps)

    def test_participants_is_step_nine(self):
        self._post(9, {"sex_male": 3, "sex_female": 2, "g_straight": 5})
        self.proposal.refresh_from_db()
        self.assertEqual((self.proposal.sex_male, self.proposal.sex_female), (3, 2))
        self.assertIn(9, self.proposal.completed_steps)

    def test_a_participants_mismatch_bounces_back_to_step_nine(self):
        response = self._post(9, {"sex_male": 3, "sex_female": 2, "g_straight": 1})
        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 9]),
            fetch_redirect_response=False,
        )

    def test_date_and_venue_is_step_eleven(self):
        self._post(11, {"extension_venue": "Barangay Hall", "estimated_month": "May", "estimated_year": "2026"})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.extension_venue, "Barangay Hall")
        self.assertIn(11, self.proposal.completed_steps)

    def test_significance_is_step_thirteen(self):
        self._post(13, {"significance": "It matters."})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.significance, "It matters.")
        self.assertIn(13, self.proposal.completed_steps)

    def test_the_last_step_leads_to_submission(self):
        response = self._post(LAST_BUILTIN_STEP_NO, {})
        self.assertRedirects(
            response,
            reverse("proposal_submit", args=[self.proposal.id]),
            fetch_redirect_response=False,
        )

    def test_legacy_proposals_sit_on_the_last_step(self):
        _admin, admin_client = factories.admin("shift_admin")
        admin_client.post(
            reverse("admin_legacy_proposal_create"),
            {
                "title": "Old proposal",
                "extension_type": "REQUEST_BASED",
                "scope_type": "PROJECT",
                "proposal_status": "APPROVED",
            },
        )
        self.assertEqual(
            Proposal.objects.get(title="Old proposal").current_step, LAST_BUILTIN_STEP_NO
        )


class UtilityModelMigrationTests(TestCase):
    """``details/0027`` against a database that already has the 19-step list.

    The migration is replayed by hand against the live models (the schema is
    the same on either side of it), on a database rebuilt to look like a
    deployment that pre-dates the step.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("mig_um_owner", Profile.ROLE_FACULTY)
        cls.reviewer = factories.make_user("mig_um_reviewer", Profile.ROLE_EVALUATOR)

    def _build_pre_utility_database(self):
        from django.apps import apps

        ProposalWizardStepConfig.objects.all().delete()
        DynamicFormTemplate.objects.all().delete()
        rows = []
        for item in INITIAL_STEP_LABELS:
            if item["no"] == UTILITY_MODEL_STEP_NO:
                continue
            no = item["no"] if item["no"] < UTILITY_MODEL_STEP_NO else item["no"] - 1
            desc = "SDGs covered and extension thrust" if no == 6 else item["desc"]
            rows.append(
                ProposalWizardStepConfig(
                    step_no=no, title=item["title"], description=desc, is_visible=True, is_required=True
                )
            )
        # An extra step the admin added past the built-in list.
        rows.append(ProposalWizardStepConfig(step_no=20, title="Office extra", is_required=False))
        ProposalWizardStepConfig.objects.bulk_create(rows)

        # The seeded per-step forms, in the old numbering (budget on 7). The
        # step editor renames a form after its step title once an admin opens
        # it, and the office may add forms of its own.
        for step_no in (1, 2, 4, 5, 7, 10, 11, 12, 13):
            name = f"Fields for Step {step_no}"
            if step_no == 13:
                name += ": Significance"
            DynamicFormTemplate.objects.create(
                name=name,
                slug=f"step-{step_no}-fields",
                applies_to="PROPOSAL",
                proposal_wizard_step=step_no,
            )
        DynamicFormTemplate.objects.create(
            name="Budget notes (office)",
            slug="office-budget-notes",
            applies_to="PROPOSAL",
            proposal_wizard_step=7,
        )

        self.draft = Proposal.objects.create(
            created_by=self.owner,
            completed_steps=[1, 2, 3, 6, 7, 12, 19],
            skipped_steps=[8],
            current_step=12,
        )
        self.fresh = Proposal.objects.create(created_by=self.owner, current_step=6, completed_steps=[1, 2, 3, 4, 5, 6])
        self.review_round = ProposalReviewRound.objects.create(proposal=self.draft, round_no=1)
        for step_no in (6, 7, 8, 19):
            ProposalSectionComment.objects.create(
                proposal=self.draft,
                review_round=self.review_round,
                reviewer=self.reviewer,
                reviewer_role="EVALUATOR",
                step_no=step_no,
                comment=f"note on step {step_no}",
            )
        return apps

    def test_the_step_is_inserted_and_everything_after_it_moves_up(self):
        apps = self._build_pre_utility_database()

        utility_migration.apply(apps, None)

        with self.subTest("step table"):
            table = [
                (c.step_no, c.title) for c in ProposalWizardStepConfig.objects.order_by("step_no")
            ]
            expected = [(item["no"], item["title"]) for item in INITIAL_STEP_LABELS]
            self.assertEqual(table[:LAST_BUILTIN_STEP_NO], expected)
            self.assertEqual(table[LAST_BUILTIN_STEP_NO:], [(21, "Office extra")])
            six = ProposalWizardStepConfig.objects.get(step_no=6)
            self.assertEqual(six.description, "SDGs covered and extension agenda")
            new = ProposalWizardStepConfig.objects.get(step_no=UTILITY_MODEL_STEP_NO)
            self.assertTrue(new.is_visible)
            self.assertTrue(new.is_required)

        with self.subTest("draft progress"):
            draft = Proposal.objects.get(pk=self.draft.pk)
            self.assertEqual(draft.completed_steps, [1, 2, 3, 6, 8, 13, 20])
            self.assertEqual(draft.skipped_steps, [9])
            self.assertEqual(draft.current_step, 13)
            # A draft that had just finished step 6 meets the new step next.
            fresh = Proposal.objects.get(pk=self.fresh.pk)
            self.assertEqual(fresh.completed_steps, [1, 2, 3, 4, 5, 6])
            self.assertEqual(fresh.current_step, 6)

        with self.subTest("reviewer comments"):
            comments = {
                c.step_no: c.comment
                for c in ProposalSectionComment.objects.filter(proposal=self.draft)
            }
            self.assertEqual(
                comments,
                {
                    6: "note on step 6",
                    8: "note on step 7",
                    9: "note on step 8",
                    20: "note on step 19",
                },
            )

        with self.subTest("admin-built step forms"):
            forms = dict(
                DynamicFormTemplate.objects.filter(applies_to="PROPOSAL").values_list(
                    "slug", "proposal_wizard_step"
                )
            )
            self.assertEqual(forms["step-7-fields"], 8)
            self.assertEqual(forms["step-13-fields"], 14)
            self.assertEqual(forms["step-5-fields"], 5)
            # The seeded names follow their step; the office's own names do not.
            names = dict(DynamicFormTemplate.objects.values_list("slug", "name"))
            self.assertEqual(names["step-7-fields"], "Fields for Step 8")
            self.assertEqual(names["step-13-fields"], "Fields for Step 14: Significance")
            self.assertEqual(names["step-5-fields"], "Fields for Step 5")
            self.assertEqual(names["office-budget-notes"], "Budget notes (office)")
            self.assertEqual(forms["office-budget-notes"], 8)
            # The new step got the built-in field set.
            new_form = DynamicFormTemplate.objects.get(proposal_wizard_step=UTILITY_MODEL_STEP_NO)
            self.assertEqual(
                list(new_form.fields.order_by("order").values_list("field_key", flat=True)),
                ["technology_title", "utility_model_registration_number", "utility_model_description"],
            )

    def test_the_migration_is_idempotent(self):
        apps = self._build_pre_utility_database()
        utility_migration.apply(apps, None)
        before = list(ProposalWizardStepConfig.objects.values_list("step_no", "title"))

        utility_migration.apply(apps, None)

        self.assertEqual(list(ProposalWizardStepConfig.objects.values_list("step_no", "title")), before)
        self.assertEqual(Proposal.objects.get(pk=self.draft.pk).current_step, 13)

    def test_an_empty_step_table_is_left_for_the_wizard_to_seed(self):
        from django.apps import apps

        ProposalWizardStepConfig.objects.all().delete()
        utility_migration.apply(apps, None)
        self.assertFalse(ProposalWizardStepConfig.objects.exists())
        # ...and the wizard's seed is the 20-step list.
        _wizard_step_config_map()
        self.assertEqual(
            ProposalWizardStepConfig.objects.get(step_no=UTILITY_MODEL_STEP_NO).title,
            "Utility Model",
        )

    def test_reversing_puts_the_numbers_back(self):
        apps = self._build_pre_utility_database()
        utility_migration.apply(apps, None)

        utility_migration.reverse(apps, None)

        table = [(c.step_no, c.title) for c in ProposalWizardStepConfig.objects.order_by("step_no")]
        self.assertNotIn("Utility Model", [title for _, title in table])
        self.assertEqual(table[6], (7, "Budgetary Requirement"))
        self.assertEqual(table[-1], (20, "Office extra"))
        draft = Proposal.objects.get(pk=self.draft.pk)
        self.assertEqual(draft.completed_steps, [1, 2, 3, 6, 7, 12, 19])
        self.assertEqual(draft.skipped_steps, [8])
        self.assertEqual(draft.current_step, 12)
        self.assertEqual(
            sorted(ProposalSectionComment.objects.filter(proposal=self.draft).values_list("step_no", flat=True)),
            [6, 7, 8, 19],
        )
        budget_form = DynamicFormTemplate.objects.get(slug="step-7-fields")
        self.assertEqual(budget_form.proposal_wizard_step, 7)
        self.assertEqual(budget_form.name, "Fields for Step 7")
        self.assertEqual(
            DynamicFormTemplate.objects.get(slug="step-13-fields").name, "Fields for Step 13: Significance"
        )
        # Only the built-in field set leaves with the step; the office form on
        # the old step 7 is back on Budgetary Requirement, not on the removed step.
        self.assertFalse(DynamicFormTemplate.objects.filter(slug__startswith="step-7-fields-").exists())
        self.assertEqual(
            set(
                DynamicFormTemplate.objects.filter(proposal_wizard_step=UTILITY_MODEL_STEP_NO).values_list(
                    "slug", flat=True
                )
            ),
            {"step-7-fields", "office-budget-notes"},
        )
