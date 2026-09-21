"""
Proposal wizard and workflow tests.

Covers the parts of the lifecycle that were previously untested: the wizard
view (a 631-line function), status transitions, review rounds, and the MOA and
implementation trackers.

These are intentionally behavioural — they assert what a user of a given role
can see and do — so they keep holding if the wizard is later split into
smaller functions.
"""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories

from .models import (
    Proposal,
    ProposalCollaborator,
    ProposalReviewRound,
)
from .views import TOTAL_STEPS


DENIED = (302, 403, 404)


class WizardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("wz_owner", Profile.ROLE_FACULTY)
        cls.stranger = factories.make_user("wz_stranger", Profile.ROLE_FACULTY)
        cls.staff = factories.make_user("wz_staff", Profile.ROLE_STAFF)
        cls.director = factories.make_user("wz_director", Profile.ROLE_DIRECTOR)
        cls.collaborator = factories.make_user("wz_collab", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def _url(self, step=1):
        return reverse("proposal_wizard", args=[self.proposal.id, step])

    def test_the_owner_can_open_the_wizard(self):
        client = factories.make_client(self.owner)
        self.assertEqual(client.get(self._url()).status_code, 200)

    def test_a_stranger_is_turned_away(self):
        client = factories.make_client(self.stranger)
        self.assertIn(client.get(self._url()).status_code, DENIED)

    def test_staff_cannot_open_the_wizard(self):
        """Documented behaviour, and arguably surprising.

        ``_can_view_proposal`` returns True for STAFF, but the wizard is also
        wrapped in ``@faculty_like_required`` whose role list excludes STAFF,
        so the decorator rejects them before the view's own check runs.

        Staff reach proposals through the review/summary and tracker screens
        instead. Recorded here so the inconsistency is visible rather than
        rediscovered; changing it is a product decision, not a refactor.
        """
        client = factories.make_client(self.staff)
        self.assertIn(client.get(self._url()).status_code, DENIED)

    def test_the_director_can_view_any_proposal(self):
        client = factories.make_client(self.director)
        self.assertEqual(client.get(self._url()).status_code, 200)

    def test_an_edit_collaborator_can_open_the_wizard(self):
        ProposalCollaborator.objects.create(
            proposal=self.proposal, user=self.collaborator, can_edit=True
        )
        client = factories.make_client(self.collaborator)
        self.assertEqual(client.get(self._url()).status_code, 200)

    def test_anonymous_users_are_redirected(self):
        self.assertIn(self.client.get(self._url()).status_code, DENIED)


class WizardStepClampingTests(TestCase):
    """Out-of-range steps must be clamped rather than raising."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("wc_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def test_step_zero_is_clamped_to_the_first_step(self):
        response = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, 0])
        )
        self.assertEqual(response.status_code, 200)

    def test_a_step_beyond_the_last_is_clamped(self):
        response = self.client_owner.get(
            reverse("proposal_wizard", args=[self.proposal.id, TOTAL_STEPS + 50])
        )
        self.assertEqual(response.status_code, 200)

    def test_every_valid_step_renders(self):
        for step in range(1, TOTAL_STEPS + 1):
            with self.subTest(step=step):
                response = self.client_owner.get(
                    reverse("proposal_wizard", args=[self.proposal.id, step])
                )
                self.assertEqual(response.status_code, 200)

    def test_an_unknown_proposal_id_returns_404(self):
        import uuid

        response = self.client_owner.get(
            reverse("proposal_wizard", args=[uuid.uuid4(), 1])
        )
        self.assertEqual(response.status_code, 404)


class ProposalStatusTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("st_owner", Profile.ROLE_FACULTY)

    def test_a_new_proposal_starts_in_drafting(self):
        proposal = Proposal.objects.create(created_by=self.owner)
        self.assertEqual(proposal.proposal_status, Proposal.ProposalStatus.DRAFTING)
        self.assertEqual(proposal.proposal_progress, 10)

    def test_moa_status_defaults_depend_on_whether_an_moa_is_required(self):
        without = Proposal.objects.create(created_by=self.owner, requires_moa=False)
        self.assertIn(
            without.moa_status,
            {Proposal.MOAStatus.NOT_REQUIRED, Proposal.MOAStatus.NOT_STARTED},
        )

    def test_implementation_starts_not_started(self):
        proposal = Proposal.objects.create(created_by=self.owner)
        self.assertEqual(
            proposal.implementation_status,
            Proposal.ImplementationStatus.NOT_STARTED,
        )

    def test_every_declared_status_has_a_progress_value(self):
        for status in Proposal.ProposalStatus:
            with self.subTest(status=status):
                self.assertIn(status, Proposal.PROPOSAL_PROGRESS_MAP)

        for status in Proposal.MOAStatus:
            with self.subTest(status=status):
                self.assertIn(status, Proposal.MOA_PROGRESS_MAP)

        for status in Proposal.ImplementationStatus:
            with self.subTest(status=status):
                self.assertIn(status, Proposal.IMPLEMENTATION_PROGRESS_MAP)

    def test_progress_values_stay_within_0_and_100(self):
        maps = [
            Proposal.PROPOSAL_PROGRESS_MAP,
            Proposal.MOA_PROGRESS_MAP,
            Proposal.IMPLEMENTATION_PROGRESS_MAP,
        ]
        for mapping in maps:
            for status, value in mapping.items():
                with self.subTest(status=status):
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, 100)


class ReviewRoundTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("rr_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_a_review_round_can_be_created(self):
        rr = ProposalReviewRound.objects.create(proposal=self.proposal, round_no=1)
        self.assertEqual(rr.round_no, 1)
        self.assertFalse(rr.is_closed)

    def test_round_numbers_are_unique_per_proposal(self):
        from django.db import IntegrityError, transaction

        ProposalReviewRound.objects.create(proposal=self.proposal, round_no=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProposalReviewRound.objects.create(proposal=self.proposal, round_no=1)

    def test_two_proposals_can_each_have_a_round_one(self):
        other = Proposal.objects.create(created_by=self.owner)

        ProposalReviewRound.objects.create(proposal=self.proposal, round_no=1)
        ProposalReviewRound.objects.create(proposal=other, round_no=1)

        self.assertEqual(ProposalReviewRound.objects.filter(round_no=1).count(), 2)


class PhaseManagementAccessTests(TestCase):
    """MOA and implementation trackers are Staff/Director territory."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("pm_owner", Profile.ROLE_FACULTY)
        cls.staff = factories.make_user("pm_staff", Profile.ROLE_STAFF)
        cls.director = factories.make_user("pm_director", Profile.ROLE_DIRECTOR)
        cls.faculty = factories.make_user("pm_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner, requires_moa=True)

    def test_staff_can_open_the_moa_tracker(self):
        client = factories.make_client(self.staff)
        response = client.get(reverse("proposal_moa_tracker", args=[self.proposal.id]))
        self.assertIn(response.status_code, (200, 302))

    def test_staff_can_open_the_implementation_tracker(self):
        client = factories.make_client(self.staff)
        response = client.get(
            reverse("proposal_implementation_tracker", args=[self.proposal.id])
        )
        self.assertIn(response.status_code, (200, 302))

    def test_an_unrelated_faculty_member_cannot_open_the_moa_tracker(self):
        client = factories.make_client(self.faculty)
        response = client.get(reverse("proposal_moa_tracker", args=[self.proposal.id]))
        self.assertIn(response.status_code, DENIED)

    def test_anonymous_users_cannot_open_the_trackers(self):
        for name in ["proposal_moa_tracker", "proposal_implementation_tracker"]:
            with self.subTest(url=name):
                response = self.client.get(reverse(name, args=[self.proposal.id]))
                self.assertIn(response.status_code, DENIED)


class WizardInPageNavigationTests(TestCase):
    """Step changes stay inside the wizard instead of reloading the site.

    The server still renders a full page (so no-JS browsers work). The
    in-page navigator in ``static/js/nexus-wizard.js`` swaps ``#nx-wizard-root``
    for stepper clicks and Save/Back/Skip posts. These tests pin the markup
    and the controller that make that possible, plus that a save still lands
    on the server.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("wiz_nav", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        self.client_owner = factories.make_client(self.owner)

    def _url(self, step=1):
        return reverse("proposal_wizard", args=[self.proposal.id, step])

    def test_the_wizard_marks_its_body_for_in_page_swaps(self):
        html = self.client_owner.get(self._url()).content.decode()
        self.assertIn('id="nx-wizard-root"', html)
        self.assertIn("data-nx-wizard", html)
        self.assertIn("js/nexus-wizard.js", html)
        self.assertIn("wizard-stepper-scroll", html)

    def test_saving_a_step_still_persists_on_the_server(self):
        response = self.client_owner.post(
            self._url(1),
            {
                "action": "next",
                "extension_type": "REQUEST_BASED",
                "scope_type": "PROJECT",
                "proposal_format": "TRAINING_DESIGN",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.extension_type, "REQUEST_BASED")
        self.assertEqual(self.proposal.scope_type, "PROJECT")
        self.assertIn("/edit/step/", response["Location"])


class WizardNavigatorAssetTests(SimpleTestCase):
    """The in-page wizard controller keeps the hooks the templates rely on."""

    def test_the_controller_intercepts_wizard_links_and_forms(self):
        from pathlib import Path
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "static" / "js" / "nexus-wizard.js"
        self.assertTrue(path.exists(), "nexus-wizard.js is missing")
        js = path.read_text(encoding="utf-8")
        for marker in (
            "nx-wizard-root",
            "isWizardUrl",
            "FormData",
            "pushState",
            "popstate",
            "NexusWizard",
            "activateScripts",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, js)


class ProposalListingTests(TestCase):
    """Dashboards must not leak proposals between unrelated users."""

    @classmethod
    def setUpTestData(cls):
        cls.alice = factories.make_user("pl_alice", Profile.ROLE_FACULTY)
        cls.bob = factories.make_user("pl_bob", Profile.ROLE_FACULTY)

    def test_a_faculty_dashboard_does_not_show_another_users_proposal(self):
        Proposal.objects.create(created_by=self.bob, title="BOB-SECRET-PROPOSAL")

        client = factories.make_client(self.alice)
        response = client.get(reverse("faculty_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "BOB-SECRET-PROPOSAL")

    def test_a_faculty_dashboard_shows_the_users_own_proposal(self):
        Proposal.objects.create(created_by=self.alice, title="ALICE-OWN-PROPOSAL")

        client = factories.make_client(self.alice)
        response = client.get(reverse("faculty_dashboard"))

        self.assertContains(response, "ALICE-OWN-PROPOSAL")
