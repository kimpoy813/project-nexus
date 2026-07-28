"""
Characterisation tests for proposal permission helpers.

Written *before* the permissions refactor to pin down existing behaviour, so
that moving the logic into ``accounts/permissions.py`` can be proven not to
change who can do what.

Where current behaviour looks wrong, the test documents it as-is and the
reason is called out in a comment rather than silently "fixed" — changing
access rules is a product decision, not a refactor.
"""

from django.test import TestCase

from accounts.models import Profile
from accounts.tests import factories
from details.models import RoleCapability

from .models import (
    Proposal,
    ProposalCollaborator,
    ProposalEvaluatorAssignment,
    ProposalReviewRound,
)


def assign_evaluator(proposal, evaluator, assigned_by, *, is_active=True):
    """Create an evaluator assignment, satisfying the model's invariants.

    ``ProposalEvaluatorAssignment.clean`` requires a review round belonging to
    the same proposal and an assigner with the DIRECTOR role.
    """
    review_round, _ = ProposalReviewRound.objects.get_or_create(
        proposal=proposal, round_no=1
    )
    return ProposalEvaluatorAssignment.objects.create(
        proposal=proposal,
        review_round=review_round,
        evaluator=evaluator,
        assigned_by=assigned_by,
        is_active=is_active,
    )


class CanEditTests(TestCase):
    """``_can_edit``: owner, edit-collaborators, and named proponents."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("edit_owner", Profile.ROLE_FACULTY)
        cls.collaborator = factories.make_user("edit_collab", Profile.ROLE_FACULTY)
        cls.stranger = factories.make_user("edit_stranger", Profile.ROLE_FACULTY)
        cls.admin = factories.make_user("edit_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        from proposals.views import _can_edit

        self._can_edit = _can_edit
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_the_owner_can_edit(self):
        self.assertTrue(self._can_edit(self.owner, self.proposal))

    def test_a_stranger_cannot_edit(self):
        self.assertFalse(self._can_edit(self.stranger, self.proposal))

    def test_a_collaborator_with_edit_rights_can_edit(self):
        ProposalCollaborator.objects.create(
            proposal=self.proposal, user=self.collaborator, can_edit=True
        )
        self.assertTrue(self._can_edit(self.collaborator, self.proposal))

    def test_a_collaborator_without_edit_rights_cannot_edit(self):
        ProposalCollaborator.objects.create(
            proposal=self.proposal, user=self.collaborator, can_edit=False
        )
        self.assertFalse(self._can_edit(self.collaborator, self.proposal))

    def test_admin_does_not_get_edit_rights_implicitly(self):
        """Documented behaviour: editing is ownership-based, not role-based."""
        self.assertFalse(self._can_edit(self.admin, self.proposal))


class CanReviewTests(TestCase):
    """``_can_review``: capability gate, then role-specific scoping."""

    @classmethod
    def setUpTestData(cls):
        cls.director = factories.make_user("rev_director", Profile.ROLE_DIRECTOR)
        cls.dept = factories.make_user(
            "rev_dept", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )
        cls.campus = factories.make_user(
            "rev_campus", Profile.ROLE_CAMPUS_COORDINATOR, campus="Main Campus"
        )
        cls.evaluator = factories.make_user("rev_evaluator", Profile.ROLE_EVALUATOR)
        cls.faculty = factories.make_user("rev_faculty", Profile.ROLE_FACULTY)
        cls.owner = factories.make_user("rev_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        from proposals.views import _can_review

        self._can_review = _can_review

    def _proposal(self, **kwargs):
        return Proposal.objects.create(created_by=self.owner, **kwargs)

    def test_the_director_can_review_anything(self):
        self.assertTrue(self._can_review(self.director, self._proposal()))

    def test_a_department_coordinator_can_review_their_own_department(self):
        proposal = self._proposal(department="Computer Science")
        self.assertTrue(self._can_review(self.dept, proposal))

    def test_a_department_coordinator_cannot_review_another_department(self):
        proposal = self._proposal(department="Nursing")
        self.assertFalse(self._can_review(self.dept, proposal))

    def test_department_scoping_ignores_surrounding_whitespace(self):
        proposal = self._proposal(department="  Computer Science  ")
        self.assertTrue(self._can_review(self.dept, proposal))

    def test_a_campus_coordinator_can_review_their_own_campus(self):
        proposal = self._proposal(campus="Main Campus")
        self.assertTrue(self._can_review(self.campus, proposal))

    def test_a_campus_coordinator_cannot_review_another_campus(self):
        proposal = self._proposal(campus="North Campus")
        self.assertFalse(self._can_review(self.campus, proposal))

    def test_an_evaluator_needs_an_active_assignment(self):
        proposal = self._proposal()
        self.assertFalse(self._can_review(self.evaluator, proposal))

        assign_evaluator(proposal, self.evaluator, self.director)
        self.assertTrue(self._can_review(self.evaluator, proposal))

    def test_an_inactive_assignment_does_not_grant_review_rights(self):
        proposal = self._proposal()
        assign_evaluator(proposal, self.evaluator, self.director, is_active=False)
        self.assertFalse(self._can_review(self.evaluator, proposal))

    def test_plain_faculty_cannot_review(self):
        self.assertFalse(self._can_review(self.faculty, self._proposal()))

    def test_anonymous_users_cannot_review(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(self._can_review(AnonymousUser(), self._proposal()))

    def test_disabling_the_capability_falls_back_to_evaluator_assignment(self):
        """Turning REVIEW_PROPOSAL off in the matrix demotes a coordinator."""
        proposal = self._proposal(department="Computer Science")
        RoleCapability.objects.update_or_create(
            role=Profile.ROLE_DEPARTMENT_COORDINATOR,
            capability=RoleCapability.Capability.REVIEW_PROPOSAL,
            defaults={"enabled": False},
        )

        self.assertFalse(self._can_review(self.dept, proposal))

        assign_evaluator(proposal, self.dept, self.director)
        self.assertTrue(self._can_review(self.dept, proposal))


class CanManagePhaseTests(TestCase):
    """``_can_manage_phase``: who may advance the MOA / implementation trackers."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = factories.make_user("mp_staff", Profile.ROLE_STAFF)
        cls.director = factories.make_user("mp_director", Profile.ROLE_DIRECTOR)
        cls.faculty = factories.make_user("mp_faculty", Profile.ROLE_FACULTY)
        cls.evaluator = factories.make_user("mp_evaluator", Profile.ROLE_EVALUATOR)
        cls.admin = factories.make_user("mp_admin", Profile.ROLE_ADMIN)
        cls.owner = factories.make_user("mp_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        from proposals.views import _can_manage_phase

        self._can_manage_phase = _can_manage_phase
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_staff_and_director_can_manage_phases(self):
        self.assertTrue(self._can_manage_phase(self.staff, self.proposal))
        self.assertTrue(self._can_manage_phase(self.director, self.proposal))

    def test_faculty_and_evaluators_cannot_manage_phases(self):
        self.assertFalse(self._can_manage_phase(self.faculty, self.proposal))
        self.assertFalse(self._can_manage_phase(self.evaluator, self.proposal))

    def test_admin_can_manage_phases(self):
        """Admin implies every capability, so it passes the capability gate."""
        self.assertTrue(self._can_manage_phase(self.admin, self.proposal))

    def test_anonymous_users_cannot_manage_phases(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(self._can_manage_phase(AnonymousUser(), self.proposal))


class CanViewProposalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("vp_owner", Profile.ROLE_FACULTY)
        cls.staff = factories.make_user("vp_staff", Profile.ROLE_STAFF)
        cls.director = factories.make_user("vp_director", Profile.ROLE_DIRECTOR)
        cls.stranger = factories.make_user("vp_stranger", Profile.ROLE_FACULTY)

    def setUp(self):
        from proposals.views import _can_view_proposal

        self._can_view = _can_view_proposal
        self.proposal = Proposal.objects.create(created_by=self.owner)

    def test_the_owner_can_view(self):
        self.assertTrue(self._can_view(self.owner, self.proposal))

    def test_staff_can_view_any_proposal(self):
        self.assertTrue(self._can_view(self.staff, self.proposal))

    def test_the_director_can_view_any_proposal(self):
        self.assertTrue(self._can_view(self.director, self.proposal))

    def test_an_unrelated_user_cannot_view(self):
        self.assertFalse(self._can_view(self.stranger, self.proposal))


class RoleCapabilityDefaultTests(TestCase):
    """``_role_has_capability`` before the admin matrix has been saved."""

    def setUp(self):
        from proposals.views import _role_has_capability

        self._has = _role_has_capability
        RoleCapability.objects.all().delete()

    def test_admin_is_granted_every_capability_except_the_restricted_one(self):
        """Admin implies every capability except submitting accomplishment reports.

        That one stays tied to coordinators: Admin manages the system rather
        than filing quarterly reports for a department or campus.
        """
        admin = factories.make_user("rc_admin", Profile.ROLE_ADMIN)
        restricted = RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT

        for capability in RoleCapability.Capability:
            with self.subTest(capability=capability):
                if capability == restricted:
                    self.assertFalse(self._has(admin, capability))
                else:
                    self.assertTrue(self._has(admin, capability))

    def test_faculty_may_create_but_not_review(self):
        faculty = factories.make_user("rc_faculty", Profile.ROLE_FACULTY)
        self.assertTrue(self._has(faculty, RoleCapability.Capability.CREATE_PROPOSAL))
        self.assertFalse(self._has(faculty, RoleCapability.Capability.REVIEW_PROPOSAL))

    def test_staff_may_manage_moa_and_implementation(self):
        staff = factories.make_user("rc_staff", Profile.ROLE_STAFF)
        self.assertTrue(self._has(staff, RoleCapability.Capability.MANAGE_MOA))
        self.assertTrue(self._has(staff, RoleCapability.Capability.MANAGE_IMPLEMENTATION))

    def test_staff_may_not_create_proposals_by_default(self):
        staff = factories.make_user("rc_staff2", Profile.ROLE_STAFF)
        self.assertFalse(self._has(staff, RoleCapability.Capability.CREATE_PROPOSAL))

    def test_an_explicit_matrix_row_overrides_the_default(self):
        faculty = factories.make_user("rc_faculty2", Profile.ROLE_FACULTY)
        RoleCapability.objects.create(
            role=Profile.ROLE_FACULTY,
            capability=RoleCapability.Capability.CREATE_PROPOSAL,
            enabled=False,
        )
        self.assertFalse(self._has(faculty, RoleCapability.Capability.CREATE_PROPOSAL))

    def test_anonymous_users_have_no_capabilities(self):
        from django.contrib.auth.models import AnonymousUser

        for capability in RoleCapability.Capability:
            with self.subTest(capability=capability):
                self.assertFalse(self._has(AnonymousUser(), capability))
