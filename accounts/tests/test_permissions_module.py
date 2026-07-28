"""
Unit tests for ``accounts.permissions``.

The view-level tests in ``test_permissions.py`` prove the right people reach
the right pages. These prove the predicates themselves behave correctly,
including the edge cases that are awkward to reach through a URL.
"""

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts import permissions
from accounts.models import Profile
from details.models import RoleCapability

from . import factories


class GetRoleTests(TestCase):
    def test_returns_the_profile_role(self):
        user = factories.make_user("gr_director", Profile.ROLE_DIRECTOR)
        self.assertEqual(permissions.get_role(user), Profile.ROLE_DIRECTOR)

    def test_anonymous_users_have_no_role(self):
        self.assertEqual(permissions.get_role(AnonymousUser()), "")

    def test_the_legacy_coordinator_role_maps_to_campus_coordinator(self):
        user = factories.make_user("gr_legacy", Profile.ROLE_FACULTY)
        Profile.objects.filter(user=user).update(role="COORDINATOR")
        user.refresh_from_db()
        user = type(user).objects.get(pk=user.pk)

        self.assertEqual(permissions.get_role(user), Profile.ROLE_CAMPUS_COORDINATOR)

    def test_roles_are_normalised_to_upper_case(self):
        user = factories.make_user("gr_lower", Profile.ROLE_FACULTY)
        Profile.objects.filter(user=user).update(role="director")
        user = type(user).objects.get(pk=user.pk)

        self.assertEqual(permissions.get_role(user), Profile.ROLE_DIRECTOR)


class HasRoleTests(TestCase):
    def test_accepts_individual_roles_and_collections(self):
        user = factories.make_user("hr_staff", Profile.ROLE_STAFF)

        self.assertTrue(permissions.has_role(user, Profile.ROLE_STAFF))
        self.assertTrue(
            permissions.has_role(user, Profile.ROLE_DIRECTOR, Profile.ROLE_STAFF)
        )
        self.assertTrue(permissions.has_role(user, permissions.PHASE_MANAGER_ROLES))
        self.assertFalse(permissions.has_role(user, Profile.ROLE_FACULTY))

    def test_anonymous_users_match_nothing(self):
        self.assertFalse(permissions.has_role(AnonymousUser(), Profile.ROLE_FACULTY))


class RolePredicateTests(TestCase):
    def test_each_predicate_matches_only_its_own_role(self):
        cases = [
            (Profile.ROLE_ADMIN, permissions.is_admin),
            (Profile.ROLE_DIRECTOR, permissions.is_director),
            (Profile.ROLE_STAFF, permissions.is_staff_role),
            (Profile.ROLE_DEPARTMENT_COORDINATOR, permissions.is_department_coordinator),
            (Profile.ROLE_CAMPUS_COORDINATOR, permissions.is_campus_coordinator),
        ]

        for role, predicate in cases:
            with self.subTest(role=role):
                matching = factories.make_user(f"rp_{role.lower()}", role)
                other = factories.make_user(f"rp_other_{role.lower()}", Profile.ROLE_FACULTY)

                self.assertTrue(predicate(matching))
                self.assertFalse(predicate(other))

    def test_a_django_superuser_counts_as_admin(self):
        user = factories.make_user("rp_super", Profile.ROLE_FACULTY)
        user.is_superuser = True
        user.save()

        self.assertTrue(permissions.is_admin(user))

    def test_is_staff_role_ignores_the_django_is_staff_flag(self):
        """``user.is_staff`` is Django admin access, not the STAFF profile role."""
        user = factories.make_user("rp_djstaff", Profile.ROLE_FACULTY)
        user.is_staff = True
        user.save()

        self.assertFalse(permissions.is_staff_role(user))


class CapabilityTests(TestCase):
    def setUp(self):
        RoleCapability.objects.all().delete()

    def test_admin_gets_unrestricted_capabilities(self):
        admin = factories.make_user("cap_admin", Profile.ROLE_ADMIN)

        self.assertTrue(
            permissions.has_capability(admin, RoleCapability.Capability.CREATE_PROPOSAL)
        )
        self.assertTrue(
            permissions.has_capability(admin, RoleCapability.Capability.VIEW_ANALYTICS)
        )

    def test_admin_does_not_get_the_restricted_capability(self):
        admin = factories.make_user("cap_admin2", Profile.ROLE_ADMIN)

        self.assertFalse(
            permissions.has_capability(
                admin, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT
            )
        )

    def test_a_restricted_capability_ignores_an_enabling_matrix_row(self):
        """A stray matrix row must not re-grant a role-restricted capability."""
        staff = factories.make_user("cap_staff", Profile.ROLE_STAFF)
        RoleCapability.objects.create(
            role=Profile.ROLE_STAFF,
            capability=RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT,
            enabled=True,
        )

        self.assertFalse(
            permissions.has_capability(
                staff, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT
            )
        )

    def test_coordinators_hold_the_restricted_capability(self):
        for role in [Profile.ROLE_DEPARTMENT_COORDINATOR, Profile.ROLE_CAMPUS_COORDINATOR]:
            with self.subTest(role=role):
                user = factories.make_user(f"cap_{role.lower()}", role)
                self.assertTrue(
                    permissions.has_capability(
                        user, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT
                    )
                )

    def test_an_explicit_matrix_row_overrides_the_default(self):
        faculty = factories.make_user("cap_faculty", Profile.ROLE_FACULTY)
        self.assertTrue(
            permissions.has_capability(faculty, RoleCapability.Capability.CREATE_PROPOSAL)
        )

        RoleCapability.objects.create(
            role=Profile.ROLE_FACULTY,
            capability=RoleCapability.Capability.CREATE_PROPOSAL,
            enabled=False,
        )
        self.assertFalse(
            permissions.has_capability(faculty, RoleCapability.Capability.CREATE_PROPOSAL)
        )

    def test_anonymous_users_hold_no_capabilities(self):
        for capability in RoleCapability.Capability:
            with self.subTest(capability=capability):
                self.assertFalse(permissions.has_capability(AnonymousUser(), capability))


class AccomplishmentPredicateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = factories.make_user("ap_dept", Profile.ROLE_DEPARTMENT_COORDINATOR)
        cls.campus = factories.make_user("ap_campus", Profile.ROLE_CAMPUS_COORDINATOR)
        cls.staff = factories.make_user("ap_staff", Profile.ROLE_STAFF)
        cls.director = factories.make_user("ap_director", Profile.ROLE_DIRECTOR)
        cls.admin = factories.make_user("ap_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("ap_faculty", Profile.ROLE_FACULTY)

    def test_submit_view_and_scope_predicates_agree(self):
        cases = [
            #  user,          submit, view,  sees_all
            (self.dept, True, True, False),
            (self.campus, True, True, False),
            (self.staff, False, True, True),
            (self.director, False, True, True),
            (self.admin, False, False, False),
            (self.faculty, False, False, False),
        ]

        for user, submit, view, sees_all in cases:
            with self.subTest(role=user.profile.role):
                self.assertIs(permissions.can_submit_accomplishment_reports(user), submit)
                self.assertIs(permissions.can_view_accomplishment_reports(user), view)
                self.assertIs(permissions.sees_all_accomplishment_reports(user), sees_all)

    def test_submitters_are_always_viewers(self):
        for user in [self.dept, self.campus]:
            with self.subTest(role=user.profile.role):
                self.assertTrue(permissions.can_view_accomplishment_reports(user))


class ScopeMatchingTests(TestCase):
    """``can_review_proposal`` compares scope strings leniently."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("sm_owner", Profile.ROLE_FACULTY)
        cls.dept = factories.make_user(
            "sm_dept", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )

    def _proposal(self, **kwargs):
        from proposals.models import Proposal

        return Proposal.objects.create(created_by=self.owner, **kwargs)

    def test_matching_ignores_whitespace(self):
        proposal = self._proposal(department="  Computer Science ")
        self.assertTrue(permissions.can_review_proposal(self.dept, proposal))

    def test_matching_ignores_case(self):
        """Previously case-sensitive: 'COMPUTER SCIENCE' silently failed."""
        proposal = self._proposal(department="COMPUTER SCIENCE")
        self.assertTrue(permissions.can_review_proposal(self.dept, proposal))

    def test_a_genuinely_different_department_still_fails(self):
        proposal = self._proposal(department="Nursing")
        self.assertFalse(permissions.can_review_proposal(self.dept, proposal))

    def test_an_empty_proposal_scope_does_not_match_a_set_profile_scope(self):
        proposal = self._proposal(department="")
        self.assertFalse(permissions.can_review_proposal(self.dept, proposal))
