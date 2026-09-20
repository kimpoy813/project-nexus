"""Tests for the free-text Gender Issues / Mandates repeater on step 10.

The step used to be a predefined multi-select checklist. Proponents now type
each gender issue or mandate themselves and can add as many entries as they
need - the same repeater shape as the Methodology step - so these tests pin the
rendering, the saved order, and the mapping back to the canonical mandates the
DOCX templates still print as fixed rows.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from proposals.models import Proposal, ProposalGenderIssue
from proposals.views.constants import GENDER_ISSUE_LIST
from proposals.views.wizard import canonical_gender_issue_key, is_step_complete


class GenderIssuesRepeaterTests(TestCase):
    #: One marker per server-rendered row. The add-row script carries the input
    #: name too, so counting ``name="gender_issues[]"`` would over-count by one.
    ROW_MARKUP = '<div class="flex gap-2 items-start gender-issue-row">'

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("gender_repeater_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)
        self.url = reverse("proposal_wizard", args=[self.proposal.id, 10])

    def _post(self, entries):
        return self.client_owner.post(
            self.url, {"action": "next", "gender_issues[]": entries}
        )

    def _saved_labels(self):
        return list(
            ProposalGenderIssue.objects.filter(proposal=self.proposal).values_list(
                "issue_label", flat=True
            )
        )

    def test_the_step_offers_a_typed_row_instead_of_predefined_options(self):
        response = self.client_owner.get(self.url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertEqual(content.count(self.ROW_MARKUP), 1)
        self.assertIn("Add Gender Issue / Mandate", content)
        self.assertNotIn('name="gender_issue_keys"', content)
        self.assertNotIn("you may select more than one", content)
        for _key, label in GENDER_ISSUE_LIST:
            self.assertNotIn(label, content)

    def test_every_typed_entry_is_saved_in_the_order_it_was_typed(self):
        entries = [
            "Women in the barangay help plan the activity.",
            GENDER_ISSUE_LIST[2][1],
            "Men and women share the tasks the training covers.",
        ]

        response = self._post(entries)

        self.assertRedirects(
            response,
            reverse("proposal_wizard", args=[self.proposal.id, 11]),
            fetch_redirect_response=False,
        )
        self.assertEqual(self._saved_labels(), entries)
        self.assertTrue(is_step_complete(self.proposal, 10))

    def test_saved_entries_come_back_as_their_own_rows(self):
        ProposalGenderIssue.objects.create(
            proposal=self.proposal, issue_label="First typed entry"
        )
        ProposalGenderIssue.objects.create(
            proposal=self.proposal, issue_label="Second typed entry"
        )

        response = self.client_owner.get(self.url)

        content = response.content.decode()
        self.assertEqual(content.count(self.ROW_MARKUP), 2)
        self.assertContains(response, "First typed entry")
        self.assertContains(response, "Second typed entry")
        self.assertLess(
            content.index("First typed entry"), content.index("Second typed entry")
        )

    def test_blank_rows_are_ignored(self):
        self._post(["   ", "The only real entry", ""])
        self.assertEqual(self._saved_labels(), ["The only real entry"])

    def test_saving_again_replaces_the_previous_entries(self):
        self._post(["First round", "Second round"])
        self._post(["Only one left"])
        self.assertEqual(self._saved_labels(), ["Only one left"])

    def test_clearing_every_row_makes_the_step_incomplete_again(self):
        ProposalGenderIssue.objects.create(
            proposal=self.proposal, issue_label="An entry that is removed later"
        )
        self.assertTrue(is_step_complete(self.proposal, 10))

        self._post([])

        self.assertEqual(self._saved_labels(), [])
        self.assertFalse(is_step_complete(self.proposal, 10))

    def test_the_retired_checklist_post_is_ignored_if_an_old_client_sends_it(self):
        self.client_owner.post(
            self.url,
            {
                "action": "next",
                "gender_issue_keys": [GENDER_ISSUE_LIST[0][0]],
                "gender_issues[]": ["A typed entry"],
            },
        )
        self.assertEqual(self._saved_labels(), ["A typed entry"])

    def test_read_only_view_shows_the_typed_entries_without_edit_controls(self):
        ProposalGenderIssue.objects.create(
            proposal=self.proposal, issue_label="Locked gender issue"
        )
        self.proposal.proposal_status = Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW
        self.proposal.is_locked = True
        self.proposal.save()

        response = self.client_owner.get(self.url + "?readonly=1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Locked gender issue")
        self.assertContains(response, "readonly")
        self.assertNotContains(response, "Add Gender Issue / Mandate")


class CanonicalMandateKeyTests(TestCase):
    """Typed text that rewords a template mandate still ticks its own row."""

    def test_the_canonical_wording_maps_to_its_key(self):
        for key, label in GENDER_ISSUE_LIST:
            self.assertEqual(canonical_gender_issue_key(label), key)

    def test_case_whitespace_and_a_missing_final_period_are_tolerated(self):
        label = GENDER_ISSUE_LIST[3][1]
        self.assertEqual(
            canonical_gender_issue_key(f"  {label.upper().rstrip('.')}\n"),
            "gad_awareness_safe_spaces",
        )

    def test_free_text_has_no_canonical_key(self):
        self.assertEqual(canonical_gender_issue_key("A mandate of their own"), "")
        self.assertEqual(canonical_gender_issue_key("   "), "")
        self.assertEqual(canonical_gender_issue_key(None), "")

    def test_the_key_is_stored_alongside_the_typed_text(self):
        owner = factories.make_user("gender_key_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=owner)
        client = factories.make_client(owner)

        client.post(
            reverse("proposal_wizard", args=[proposal.id, 10]),
            {
                "action": "next",
                "gender_issues[]": [
                    GENDER_ISSUE_LIST[1][1],
                    "Fisherwomen get their own livelihood training.",
                ],
            },
        )

        self.assertEqual(
            list(
                ProposalGenderIssue.objects.filter(proposal=proposal).values_list(
                    "issue_key", flat=True
                )
            ),
            [GENDER_ISSUE_LIST[1][0], ""],
        )


class GenderIssuesInGeneratedFormTests(TestCase):
    """The typed entries must reach the downloadable extension form."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("gender_docx_owner", Profile.ROLE_FACULTY)

    def _form_text(self, entries):
        import io
        import re
        import zipfile

        from proposals.docx_forms import build_extension_form_docx

        proposal = Proposal.objects.create(
            created_by=self.owner,
            title="Gender Form Check",
            extension_type="REQUEST_BASED",
            scope_type="PROJECT",
        )
        for entry in entries:
            ProposalGenderIssue.objects.create(
                proposal=proposal,
                issue_key=canonical_gender_issue_key(entry),
                issue_label=entry,
            )

        data = build_extension_form_docx(proposal)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", "", xml)

    def test_a_typed_entry_is_listed_under_others(self):
        text = self._form_text(["Fisherwomen get their own livelihood training."])
        self.assertIn("Others", text)
        self.assertIn("Fisherwomen get their own livelihood training.", text)
        self.assertNotIn("[Mandates placed in Others]", text)

    def test_a_canonical_entry_ticks_its_own_row_and_not_others(self):
        mandate = GENDER_ISSUE_LIST[0][1]
        text = self._form_text([mandate])
        self.assertIn("The activity strengthens the advocacy", text)
        self.assertNotIn("[Mandates placed in Others]", text)

    def test_a_form_with_no_entries_still_generates(self):
        text = self._form_text([])
        self.assertNotIn("[Mandates placed in Others]", text)
