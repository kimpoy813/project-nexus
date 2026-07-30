"""
Central permission predicates for NExUS.

Previously permission logic was spread across ``accounts/views.py``,
``proposals/views.py``, ``accounts/decorators.py``, and
``accounts/context_processors.py``, in at least four different styles. There
was no single place to answer "who can do X?", which is how Admin silently
acquired the ability to submit accomplishment reports.

Everything here is a plain predicate taking a ``user`` (and sometimes an
object) and returning a bool. Views, templates, and decorators should call
these rather than comparing roles inline.

Design notes
------------
* ``ADMIN`` implies most capabilities, but **not** all — see
  ``ROLE_RESTRICTED_CAPABILITIES``. Admin manages the system; it does not
  stand in for every operational role.
* Predicates never raise for anonymous users; they return ``False``.
* Object-level predicates take the object explicitly so they can be unit
  tested without a request.
"""

from accounts.models import Profile


# ---------------------------------------------------------------------------
# Role groups
# ---------------------------------------------------------------------------

#: Roles that may create and own proposals.
PROPOSAL_AUTHOR_ROLES = frozenset({
    Profile.ROLE_FACULTY,
    Profile.ROLE_EVALUATOR,
    Profile.ROLE_DEPARTMENT_COORDINATOR,
    Profile.ROLE_CAMPUS_COORDINATOR,
    Profile.ROLE_DIRECTOR,
})

#: Roles that review proposals as part of the approval chain.
PROPOSAL_REVIEWER_ROLES = frozenset({
    Profile.ROLE_EVALUATOR,
    Profile.ROLE_DEPARTMENT_COORDINATOR,
    Profile.ROLE_CAMPUS_COORDINATOR,
    Profile.ROLE_DIRECTOR,
})

#: Roles that drive the MOA and implementation trackers.
PHASE_MANAGER_ROLES = frozenset({
    Profile.ROLE_STAFF,
    Profile.ROLE_DIRECTOR,
})

#: Coordinators file quarterly accomplishment reports.
ACCOMPLISHMENT_SUBMIT_ROLES = frozenset({
    Profile.ROLE_DEPARTMENT_COORDINATOR,
    Profile.ROLE_CAMPUS_COORDINATOR,
})

#: Staff and Director read those reports but never submit them.
ACCOMPLISHMENT_VIEW_ONLY_ROLES = frozenset({
    Profile.ROLE_STAFF,
    Profile.ROLE_DIRECTOR,
})

#: Anyone who may open the accomplishment reports list.
ACCOMPLISHMENT_REPORT_ROLES = ACCOMPLISHMENT_SUBMIT_ROLES | ACCOMPLISHMENT_VIEW_ONLY_ROLES


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

def get_role(user):
    """Return ``user``'s normalised role, or ``""`` when there isn't one."""
    if not getattr(user, "is_authenticated", False):
        return ""

    profile = getattr(user, "profile", None)
    role = (getattr(profile, "role", "") or "").strip().upper()

    # Legacy records used a single "COORDINATOR" role.
    if role == "COORDINATOR":
        return Profile.ROLE_CAMPUS_COORDINATOR

    return role


def has_role(user, *roles):
    """True when ``user``'s role is any of ``roles``."""
    role = get_role(user)
    if not role:
        return False

    allowed = set()
    for item in roles:
        if isinstance(item, (set, frozenset, list, tuple)):
            allowed.update(item)
        else:
            allowed.add(item)
    return role in allowed


def is_admin(user):
    return get_role(user) == Profile.ROLE_ADMIN or bool(getattr(user, "is_superuser", False))


def is_director(user):
    return get_role(user) == Profile.ROLE_DIRECTOR


def is_staff_role(user):
    """The STAFF *profile role*, not Django's ``user.is_staff`` flag."""
    return get_role(user) == Profile.ROLE_STAFF


def is_department_coordinator(user):
    return get_role(user) == Profile.ROLE_DEPARTMENT_COORDINATOR


def is_campus_coordinator(user):
    return get_role(user) == Profile.ROLE_CAMPUS_COORDINATOR


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------

def _capability_defaults():
    """Fallback capability grants used before the admin matrix is saved."""
    from details.models import RoleCapability

    return {
        RoleCapability.Capability.CREATE_PROPOSAL: PROPOSAL_AUTHOR_ROLES,
        RoleCapability.Capability.REVIEW_PROPOSAL: PROPOSAL_REVIEWER_ROLES,
        RoleCapability.Capability.MANAGE_MOA: PHASE_MANAGER_ROLES,
        RoleCapability.Capability.MANAGE_IMPLEMENTATION: PHASE_MANAGER_ROLES,
        RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT: ACCOMPLISHMENT_SUBMIT_ROLES,
        RoleCapability.Capability.VIEW_ANALYTICS: frozenset({
            Profile.ROLE_DIRECTOR,
            Profile.ROLE_STAFF,
            Profile.ROLE_CAMPUS_COORDINATOR,
            Profile.ROLE_DEPARTMENT_COORDINATOR,
        }),
    }


def _role_restricted_capabilities():
    """Capabilities that Admin does *not* inherit automatically.

    Admin manages the system rather than performing every operational duty, so
    these stay tied to the roles that actually do the work.
    """
    from details.models import RoleCapability

    return {
        RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT: ACCOMPLISHMENT_SUBMIT_ROLES,
    }


def has_capability(user, capability):
    """Resolve ``capability`` for ``user``.

    Order of precedence:

    1. Role-restricted capabilities consult their fixed role set only.
    2. Admin and superusers get everything else.
    3. An explicit ``RoleCapability`` row wins if one exists.
    4. Otherwise fall back to the built-in defaults.
    """
    from details.models import RoleCapability

    if not getattr(user, "is_authenticated", False):
        return False

    role = get_role(user)

    restricted = _role_restricted_capabilities()
    if capability in restricted:
        return role in restricted[capability]

    if is_admin(user):
        return True

    institution = getattr(getattr(user, "profile", None), "institution", None)
    existing = RoleCapability.objects.filter(
        institution=institution,
        role=role,
        capability=capability,
    ).first()
    if existing is not None:
        return existing.enabled

    return role in _capability_defaults().get(capability, frozenset())


# ---------------------------------------------------------------------------
# Accomplishment reports
# ---------------------------------------------------------------------------

def can_submit_accomplishment_reports(user):
    """Only Department and Campus Coordinators file reports."""
    return has_role(user, ACCOMPLISHMENT_SUBMIT_ROLES)


def can_view_accomplishment_reports(user):
    """Coordinators (their own scope) plus Staff and Director (everything)."""
    return has_role(user, ACCOMPLISHMENT_REPORT_ROLES)


def sees_all_accomplishment_reports(user):
    """Staff and Director are not scoped to a campus or department."""
    return has_role(user, ACCOMPLISHMENT_VIEW_ONLY_ROLES)


# ---------------------------------------------------------------------------
# Proposals (object-level)
# ---------------------------------------------------------------------------

def can_edit_proposal(user, proposal):
    """Editing is ownership-based: owner, edit-collaborator, or proponent.

    Deliberately not role-based — an Admin cannot silently rewrite someone's
    proposal.
    """
    from proposals.models import ProposalCollaborator, ProposalProponent

    if not getattr(user, "is_authenticated", False):
        return False

    if proposal.created_by_id == user.id:
        return True

    if ProposalCollaborator.objects.filter(
        proposal=proposal, user=user, can_edit=True
    ).exists():
        return True

    return ProposalProponent.objects.filter(proposal=proposal, user=user).exists()


def has_active_evaluator_assignment(user, proposal=None, review_round=None):
    from proposals.models import ProposalEvaluatorAssignment

    if not getattr(user, "is_authenticated", False):
        return False

    qs = ProposalEvaluatorAssignment.objects.filter(evaluator=user, is_active=True)
    if proposal is not None:
        qs = qs.filter(proposal=proposal)
    if review_round is not None:
        qs = qs.filter(review_round=review_round)
    return qs.exists()


def can_review_proposal(user, proposal):
    """Reviewers are scoped by role; everyone else needs an assignment."""
    from details.models import RoleCapability

    if not getattr(user, "is_authenticated", False):
        return False

    profile = getattr(user, "profile", None)
    role = get_role(user)

    if not has_capability(user, RoleCapability.Capability.REVIEW_PROPOSAL):
        return has_active_evaluator_assignment(user, proposal=proposal)

    if role == Profile.ROLE_DIRECTOR:
        return True

    if role == Profile.ROLE_DEPARTMENT_COORDINATOR:
        return _matches(proposal.department, getattr(profile, "department", ""))

    if role == Profile.ROLE_CAMPUS_COORDINATOR:
        return _matches(proposal.campus, getattr(profile, "campus", ""))

    current_round = (
        proposal.get_active_review_round() or proposal.get_current_review_round()
    )
    return has_active_evaluator_assignment(
        user, proposal=proposal, review_round=current_round
    )


def can_view_proposal(user, proposal):
    return (
        can_edit_proposal(user, proposal)
        or can_review_proposal(user, proposal)
        or is_staff_role(user)
    )


def can_manage_proposal_phase(user, proposal=None):
    """Who may advance the MOA and implementation trackers."""
    from details.models import RoleCapability

    if not getattr(user, "is_authenticated", False):
        return False

    return (
        has_capability(user, RoleCapability.Capability.MANAGE_MOA)
        or has_capability(user, RoleCapability.Capability.MANAGE_IMPLEMENTATION)
        or has_role(user, PHASE_MANAGER_ROLES)
    )


def can_view_proposal_summary(user, proposal):
    if not getattr(user, "is_authenticated", False):
        return False

    if is_staff_role(user):
        return True

    if proposal.created_by_id == user.id:
        return True

    return proposal.proponents.filter(user=user).exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches(left, right):
    """Case- and whitespace-insensitive comparison of two scope strings."""
    return (left or "").strip().casefold() == (right or "").strip().casefold()
