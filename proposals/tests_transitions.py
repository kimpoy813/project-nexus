"""
MOA and implementation state transition tests.

The ``mark_*`` methods on ``Proposal`` are what actually move a proposal
through its lifecycle, and every dashboard percentage and status badge is
derived from the fields they set. They had no direct coverage.

These tests focus on the invariants that would be expensive to discover in
production: that overall status is derived correctly from the three phases,
that recorded progress never regresses, and that a rejected or cancelled
proposal cannot be quietly resurrected by a later transition.
"""

from django.test import TestCase

from accounts.models import Profile
from accounts.tests import factories

from .models import Proposal


class MOATransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("moa_tr_owner", Profile.ROLE_FACULTY)

    def _proposal(self, **kwargs):
        defaults = {"created_by": self.owner, "title": "MOA lifecycle"}
        defaults.update(kwargs)
        return Proposal.objects.create(**defaults)

    def test_marking_moa_not_required_clears_the_requirement(self):
        proposal = self._proposal(requires_moa=True)
        proposal.mark_moa_not_required()
        proposal.refresh_from_db()

        self.assertFalse(proposal.requires_moa)
        self.assertEqual(proposal.moa_status, Proposal.MOAStatus.NOT_REQUIRED)

    def test_a_not_required_moa_counts_as_fully_complete(self):
        """Otherwise a proposal without a MOA could never reach 100%."""
        proposal = self._proposal(requires_moa=False)
        proposal.mark_moa_not_required()

        self.assertEqual(proposal.moa_progress, 100)

    def test_starting_a_draft_sets_the_requirement_and_timestamp(self):
        proposal = self._proposal(requires_moa=False)
        proposal.mark_moa_draft()
        proposal.refresh_from_db()

        self.assertTrue(proposal.requires_moa)
        self.assertEqual(proposal.moa_status, Proposal.MOAStatus.DRAFT)
        self.assertIsNotNone(proposal.moa_started_at)

    def test_the_start_timestamp_is_not_overwritten_on_a_later_draft(self):
        proposal = self._proposal()
        proposal.mark_moa_draft()
        first_started = proposal.moa_started_at

        proposal.mark_moa_for_revision()
        proposal.mark_moa_draft()
        proposal.refresh_from_db()

        self.assertEqual(proposal.moa_started_at, first_started)

    def test_the_full_moa_sequence_reaches_completion(self):
        proposal = self._proposal()

        for method, expected in [
            ("mark_moa_draft", Proposal.MOAStatus.DRAFT),
            ("mark_moa_legal_review", Proposal.MOAStatus.LEGAL_REVIEW),
            ("mark_moa_for_revision", Proposal.MOAStatus.FOR_REVISION),
            ("mark_moa_certification_ready", Proposal.MOAStatus.CERTIFICATION_READY),
            ("mark_moa_agenda_and_presentation", Proposal.MOAStatus.AGENDA_AND_PRESENTATION),
            ("mark_moa_completed", Proposal.MOAStatus.COMPLETED),
        ]:
            with self.subTest(step=method):
                getattr(proposal, method)()
                proposal.refresh_from_db()
                self.assertEqual(proposal.moa_status, expected)

        self.assertEqual(proposal.moa_progress, 100)

    def test_progress_increases_monotonically_through_the_happy_path(self):
        proposal = self._proposal()
        seen = []

        for method in [
            "mark_moa_draft",
            "mark_moa_legal_review",
            "mark_moa_certification_ready",
            "mark_moa_agenda_and_presentation",
            "mark_moa_completed",
        ]:
            getattr(proposal, method)()
            seen.append(proposal.moa_progress)

        self.assertEqual(seen, sorted(seen), f"progress went backwards: {seen}")


class ImplementationTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("impl_tr_owner", Profile.ROLE_FACULTY)

    def _proposal(self, **kwargs):
        defaults = {"created_by": self.owner, "title": "Implementation lifecycle"}
        defaults.update(kwargs)
        return Proposal.objects.create(**defaults)

    def test_a_new_proposal_has_not_started_implementation(self):
        proposal = self._proposal()

        self.assertEqual(
            proposal.implementation_status, Proposal.ImplementationStatus.NOT_STARTED
        )
        self.assertEqual(proposal.implementation_progress, 0)

    def test_each_implementation_stage_sets_its_status(self):
        proposal = self._proposal()

        for method, expected in [
            ("mark_implementation_ongoing", Proposal.ImplementationStatus.IMPLEMENTATION),
            ("mark_post_activity_report", Proposal.ImplementationStatus.POST_ACTIVITY_REPORT),
            ("mark_terminal_report", Proposal.ImplementationStatus.TERMINAL_REPORT),
            ("mark_implementation_monitoring", Proposal.ImplementationStatus.MONITORING),
            ("mark_implementation_revision", Proposal.ImplementationStatus.REVISION),
            ("mark_implementation_completed", Proposal.ImplementationStatus.COMPLETED),
        ]:
            with self.subTest(step=method):
                getattr(proposal, method)()
                proposal.refresh_from_db()
                self.assertEqual(proposal.implementation_status, expected)

    def test_completing_implementation_reaches_full_progress(self):
        proposal = self._proposal()
        proposal.mark_implementation_completed()

        self.assertEqual(proposal.implementation_progress, 100)


class OverallStatusDerivationTests(TestCase):
    """``sync_overall_status`` runs on every save and drives the status badge."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("status_owner", Profile.ROLE_FACULTY)

    def _proposal(self, **kwargs):
        defaults = {"created_by": self.owner, "title": "Status derivation"}
        defaults.update(kwargs)
        return Proposal.objects.create(**defaults)

    def test_an_untouched_draft_is_not_active(self):
        proposal = self._proposal()
        self.assertNotEqual(proposal.status, Proposal.OverallStatus.COMPLETED)

    def test_any_progress_marks_the_proposal_active(self):
        proposal = self._proposal()
        proposal.mark_moa_draft()
        proposal.refresh_from_db()

        self.assertEqual(proposal.status, Proposal.OverallStatus.ACTIVE)

    def test_a_proposal_without_an_moa_completes_on_the_other_two_phases(self):
        proposal = self._proposal(requires_moa=False)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED
        proposal.save()
        proposal.refresh_from_db()

        self.assertEqual(proposal.status, Proposal.OverallStatus.COMPLETED)
        self.assertIsNotNone(proposal.closed_at)

    def test_a_proposal_requiring_an_moa_does_not_complete_until_the_moa_does(self):
        proposal = self._proposal(requires_moa=True)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED
        proposal.moa_status = Proposal.MOAStatus.LEGAL_REVIEW
        proposal.save()
        proposal.refresh_from_db()

        self.assertNotEqual(proposal.status, Proposal.OverallStatus.COMPLETED)

    def test_all_three_phases_complete_closes_the_proposal(self):
        proposal = self._proposal(requires_moa=True)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.moa_status = Proposal.MOAStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED
        proposal.save()
        proposal.refresh_from_db()

        self.assertEqual(proposal.status, Proposal.OverallStatus.COMPLETED)
        self.assertEqual(proposal.overall_progress, 100)

    def test_closed_at_is_not_overwritten_by_a_later_save(self):
        proposal = self._proposal(requires_moa=False)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED
        proposal.save()
        first_closed = proposal.closed_at

        proposal.save()
        proposal.refresh_from_db()

        self.assertEqual(proposal.closed_at, first_closed)


class TerminalStatusTests(TestCase):
    """Rejected and cancelled proposals must stay terminal."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("terminal_owner", Profile.ROLE_FACULTY)

    def _proposal(self):
        return Proposal.objects.create(created_by=self.owner, title="Terminal")

    def test_a_rejected_proposal_reports_zero_progress(self):
        proposal = self._proposal()
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.mark_rejected()

        self.assertEqual(proposal.status, Proposal.OverallStatus.REJECTED)
        self.assertEqual(proposal.overall_progress, 0)

    def test_a_cancelled_proposal_reports_zero_progress(self):
        proposal = self._proposal()
        proposal.mark_cancelled()

        self.assertEqual(proposal.status, Proposal.OverallStatus.CANCELLED)
        self.assertEqual(proposal.overall_progress, 0)

    def test_a_rejected_proposal_is_not_flipped_back_to_active_by_a_save(self):
        """``sync_overall_status`` returns early for terminal states."""
        proposal = self._proposal()
        proposal.mark_rejected()

        proposal.mark_moa_draft()  # triggers another save
        proposal.refresh_from_db()

        self.assertEqual(proposal.status, Proposal.OverallStatus.REJECTED)

    def test_a_cancelled_proposal_is_not_flipped_back_to_active_by_a_save(self):
        proposal = self._proposal()
        proposal.mark_cancelled()

        proposal.mark_implementation_ongoing()
        proposal.refresh_from_db()

        self.assertEqual(proposal.status, Proposal.OverallStatus.CANCELLED)


class HighestProgressRatchetTests(TestCase):
    """``sync_highest_progress`` records a high-water mark that never drops."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("ratchet_owner", Profile.ROLE_FACULTY)

    def _proposal(self):
        return Proposal.objects.create(created_by=self.owner, title="Ratchet")

    def test_the_high_water_mark_follows_progress_upward(self):
        proposal = self._proposal()
        proposal.mark_moa_draft()
        proposal.mark_moa_legal_review()
        proposal.refresh_from_db()

        self.assertGreaterEqual(proposal.highest_moa_progress, proposal.moa_progress)

    def test_sending_a_moa_back_does_not_lower_the_recorded_maximum(self):
        proposal = self._proposal()
        proposal.mark_moa_draft()
        proposal.mark_moa_certification_ready()
        peak = proposal.highest_moa_progress

        proposal.mark_moa_for_revision()  # a lower progress value
        proposal.refresh_from_db()

        self.assertEqual(proposal.highest_moa_progress, peak)
        self.assertLess(proposal.moa_progress, peak)

    def test_the_implementation_ratchet_behaves_the_same_way(self):
        proposal = self._proposal()
        proposal.mark_terminal_report()
        peak = proposal.highest_implementation_progress

        proposal.mark_implementation_ongoing()  # earlier stage
        proposal.refresh_from_db()

        self.assertEqual(proposal.highest_implementation_progress, peak)

    def test_the_proposal_phase_ratchet_behaves_the_same_way(self):
        proposal = self._proposal()
        proposal.proposal_status = Proposal.ProposalStatus.APPROVED
        proposal.save()
        peak = proposal.highest_proposal_progress

        proposal.proposal_status = Proposal.ProposalStatus.FOR_REVISION
        proposal.save()
        proposal.refresh_from_db()

        self.assertEqual(proposal.highest_proposal_progress, peak)


class PhaseLabelTests(TestCase):
    """``current_phase_label`` drives the dashboard's phase column."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("label_owner", Profile.ROLE_FACULTY)

    def _proposal(self, **kwargs):
        defaults = {"created_by": self.owner, "title": "Labels"}
        defaults.update(kwargs)
        return Proposal.objects.create(**defaults)

    def test_a_new_proposal_is_labelled_proposal(self):
        self.assertEqual(self._proposal().current_phase_label, "Proposal")

    def test_starting_the_moa_moves_the_label(self):
        proposal = self._proposal(requires_moa=True)
        proposal.mark_moa_draft()

        self.assertEqual(proposal.current_phase_label, "MOA")

    def test_implementation_takes_precedence_over_the_moa_label(self):
        proposal = self._proposal(requires_moa=True)
        proposal.mark_moa_completed()
        proposal.mark_implementation_ongoing()

        self.assertEqual(proposal.current_phase_label, "Implementation")

    def test_a_finished_proposal_is_labelled_accordingly(self):
        proposal = self._proposal(requires_moa=False)
        proposal.proposal_status = Proposal.ProposalStatus.COMPLETED
        proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED
        proposal.save()

        self.assertEqual(proposal.current_phase_label, "Extension Finished")


class WizardHelperTests(TestCase):
    """Helpers extracted from ``proposal_wizard`` during the split.

    ``proposal_wizard`` was 629 lines; these were pulled out of it. They are
    tested directly because the extraction is only safe if their behaviour is
    pinned independently of the 470-line view that calls them.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("wh_owner", Profile.ROLE_FACULTY)
        cls.reviewer = factories.make_user("wh_reviewer", Profile.ROLE_DIRECTOR)

    def setUp(self):
        from .models import ProposalReviewRound

        self.proposal = Proposal.objects.create(
            created_by=self.owner, title="Wizard helpers"
        )
        self.round = ProposalReviewRound.objects.create(
            proposal=self.proposal, round_no=1
        )

    def _add_comment(self, step_no):
        from .models import ProposalSectionComment

        return ProposalSectionComment.objects.create(
            proposal=self.proposal,
            review_round=self.round,
            reviewer=self.reviewer,
            reviewer_role="DIRECTOR",
            step_no=step_no,
            comment=f"Comment on step {step_no}",
        )

    # ---- _sidebar_comment_counts ----------------------------------------

    def test_no_counts_without_a_review_round(self):
        from .views.wizard import _sidebar_comment_counts

        self.assertEqual(_sidebar_comment_counts(self.proposal, None), {})

    def test_badges_are_hidden_unless_the_proposal_is_for_revision(self):
        """Badges prompt the proponent to act, so they are noise otherwise."""
        from .views.wizard import _sidebar_comment_counts

        self._add_comment(3)
        self.proposal.proposal_status = Proposal.ProposalStatus.IN_REVIEW

        self.assertEqual(_sidebar_comment_counts(self.proposal, self.round), {})

    def test_badges_appear_once_the_proposal_is_for_revision(self):
        from .views.wizard import _sidebar_comment_counts

        self._add_comment(3)
        self._add_comment(5)
        self.proposal.proposal_status = Proposal.ProposalStatus.FOR_REVISION

        counts = _sidebar_comment_counts(self.proposal, self.round)
        self.assertEqual(counts, {3: 1, 5: 1})

    def test_multiple_comments_on_one_step_are_counted_together(self):
        from .models import ProposalSectionComment
        from .views.wizard import _sidebar_comment_counts

        self._add_comment(4)
        ProposalSectionComment.objects.create(
            proposal=self.proposal,
            review_round=self.round,
            reviewer=self.owner,
            reviewer_role="FACULTY",
            step_no=4,
            comment="Another",
        )
        self.proposal.proposal_status = Proposal.ProposalStatus.FOR_REVISION

        self.assertEqual(_sidebar_comment_counts(self.proposal, self.round), {4: 2})

    # ---- _proponent_review_panel ----------------------------------------

    def test_non_proponents_get_no_review_panel(self):
        from .views.wizard import _proponent_review_panel

        summary, comments = _proponent_review_panel(
            self.proposal, self.round, step=1, is_proponent=False
        )
        self.assertIsNone(summary)
        self.assertEqual(list(comments), [])

    def test_comments_stay_private_until_the_proposal_is_returned(self):
        """In-progress review notes must not leak to the proponent."""
        from .views.wizard import _proponent_review_panel

        self._add_comment(1)
        self.proposal.proposal_status = Proposal.ProposalStatus.IN_REVIEW

        _, comments = _proponent_review_panel(
            self.proposal, self.round, step=1, is_proponent=True
        )
        self.assertEqual(list(comments), [])

    def test_comments_become_visible_once_returned_for_revision(self):
        from .views.wizard import _proponent_review_panel

        self._add_comment(1)
        self.proposal.proposal_status = Proposal.ProposalStatus.FOR_REVISION

        _, comments = _proponent_review_panel(
            self.proposal, self.round, step=1, is_proponent=True
        )
        self.assertEqual(len(list(comments)), 1)

    def test_only_the_current_step_is_returned(self):
        from .views.wizard import _proponent_review_panel

        self._add_comment(1)
        self._add_comment(2)
        self.proposal.proposal_status = Proposal.ProposalStatus.FOR_REVISION

        _, comments = _proponent_review_panel(
            self.proposal, self.round, step=2, is_proponent=True
        )
        steps = {c.step_no for c in comments}
        self.assertEqual(steps, {2})

    # ---- _add_step_context_for_get --------------------------------------

    def test_step_context_adds_the_sdg_and_thrust_lists(self):
        """The two flows split SDGs (6) and thrusts (7) into their own steps."""
        from .views.wizard import _add_step_context_for_get

        ctx = _add_step_context_for_get({}, self.proposal, step=6)
        self.assertIn("sdgs", ctx)
        self.assertNotIn("thrusts", ctx)

        ctx = _add_step_context_for_get({}, self.proposal, step=7)
        self.assertIn("thrusts", ctx)
        self.assertNotIn("sdgs", ctx)

    def test_step_context_adds_gender_totals(self):
        """Participants moved to step 9 when the thrust got its own step."""
        from .views.wizard import _add_step_context_for_get

        self.proposal.sex_male = 3
        self.proposal.sex_female = 4

        ctx = _add_step_context_for_get({}, self.proposal, step=9)
        self.assertEqual(ctx["sex_total"], 7)

    def test_step_context_matches_the_training_flow_step_numbers(self):
        """The Training Design flow profiles participants on step 12."""
        from .views.wizard import _add_step_context_for_get

        self.proposal.extension_type = "COMMUNITY_BASED"
        self.proposal.sex_male = 3
        self.proposal.sex_female = 4

        ctx = _add_step_context_for_get({}, self.proposal, step=12)
        self.assertEqual(ctx["sex_total"], 7)

    def test_step_context_is_harmless_for_a_step_with_no_extras(self):
        from .views.wizard import _add_step_context_for_get

        self.assertEqual(_add_step_context_for_get({}, self.proposal, step=1), {})
