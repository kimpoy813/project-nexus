"""
Thin delegations to accounts.permissions, kept for backwards compatibility.
"""

from ..models import ProposalReviewRound
from accounts import permissions


def _is_director(user):
    return permissions.is_director(user)


def _is_staff(user):
    return permissions.is_staff_role(user)


def _is_department_coordinator(user):
    return permissions.is_department_coordinator(user)


def _is_campus_coordinator(user):
    return permissions.is_campus_coordinator(user)


def _user_role_value(user):
    return permissions.get_role(user)


def _role_has_capability(user, capability):
    return permissions.has_capability(user, capability)


def _has_active_evaluator_assignment(user, proposal=None, review_round=None):
    return permissions.has_active_evaluator_assignment(
        user, proposal=proposal, review_round=review_round
    )


def _can_edit(user, proposal):
    return permissions.can_edit_proposal(user, proposal)


def _can_review(user, proposal):
    return permissions.can_review_proposal(user, proposal)


def _can_view_proposal(user, proposal):
    return permissions.can_view_proposal(user, proposal)


def _can_manage_phase(user, proposal):
    """
    Only Staff and the Director can move a proposal through the MOA Tracker
    or the Implementation Tracker (i.e. advance/send back a stage, or
    upload the stage's official documents).
    """
    return permissions.can_manage_proposal_phase(user, proposal)


def _ensure_open_review_round(proposal, user):
    """Ensure an OPEN review round exists (is_closed=False), creating a new one if needed."""
    rr = ProposalReviewRound.objects.filter(proposal=proposal, is_closed=False).order_by("-round_no", "-id").first()
    if rr:
        return rr

    last_rr = ProposalReviewRound.objects.filter(proposal=proposal).order_by("-round_no", "-id").first()
    next_no = (getattr(last_rr, "round_no", 0) or 0) + 1

    field_names = {f.name for f in ProposalReviewRound._meta.get_fields() if hasattr(f, "name")}
    create_kwargs = {"proposal": proposal}

    if "round_no" in field_names:
        create_kwargs["round_no"] = next_no
    if "is_closed" in field_names:
        create_kwargs["is_closed"] = False
    if "ready_for_staff_summary" in field_names:
        create_kwargs["ready_for_staff_summary"] = False

    for k in ("started_by", "created_by", "opened_by"):
        if k in field_names:
            create_kwargs[k] = user

    return ProposalReviewRound.objects.create(**create_kwargs)


def _get_reviewer_role(user, proposal, review_round):
    if not user.is_authenticated or not review_round:
        return ""

    if _is_director(user):
        return "DIRECTOR"

    if _is_department_coordinator(user):
        profile = getattr(user, "profile", None)
        user_department = (getattr(profile, "department", "") or "").strip()
        proposal_department = (proposal.department or "").strip()
        if user_department == proposal_department:
            return "DEPARTMENT_COORDINATOR"
        return ""

    if _is_campus_coordinator(user):
        profile = getattr(user, "profile", None)
        user_campus = (getattr(profile, "campus", "") or "").strip()
        proposal_campus = (proposal.campus or "").strip()
        if user_campus == proposal_campus:
            return "CAMPUS_COORDINATOR"
        return ""

    if _has_active_evaluator_assignment(user, proposal=proposal, review_round=review_round):
        return "EVALUATOR"

    return ""


def _can_view_summary(user, proposal):
    return permissions.can_view_proposal_summary(user, proposal)
