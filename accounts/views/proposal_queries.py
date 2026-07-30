"""
Read-only query helpers that build proposal data for the dashboards.
"""
import logging

from django.db.models import Case
from django.db.models import IntegerField
from django.db.models import Q
from django.db.models import When
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from proposals.models import Proposal
from proposals.models import ProposalFinalDocument
from proposals.models import ProposalReviewRound
from proposals.models import ProposalSectionComment
from ..models import Profile
from .helpers import User, _safe_int

logger = logging.getLogger(__name__)


def _user_institution(user):
    try:
        return user.profile.institution
    except Exception:
        return None


def _proposal_scope_for_user(user):
    return Proposal.objects.filter(institution=_user_institution(user))


def _get_total_proposal_steps():
    return 19


def _get_current_step(proposal):
    return max(1, _safe_int(getattr(proposal, "current_step", 1), 1))


def _get_comment_count_for_current_round(proposal):
    try:
        current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    except (AttributeError, ObjectDoesNotExist):
        # Older proposals may predate review rounds entirely.
        current_round = None
    except Exception:
        logger.exception("Could not resolve review round for proposal %s.", proposal.pk)
        current_round = None

    if not current_round:
        return 0

    return ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=current_round,
    ).count()


def _get_review_level(proposal):
    return (getattr(proposal, "review_level", "") or "").upper().strip()


def _get_process_label(proposal):
    if proposal.status == Proposal.OverallStatus.COMPLETED:
        return "Completed"

    if proposal.implementation_status != Proposal.ImplementationStatus.NOT_STARTED:
        return "Implementation"

    if proposal.requires_moa and proposal.moa_status not in {
        Proposal.MOAStatus.NOT_STARTED,
        Proposal.MOAStatus.NOT_REQUIRED,
    }:
        return "MOA"

    return "Proposal"


def _get_lifecycle_milestone(proposal):
    process_label = _get_process_label(proposal)

    comment_count = _get_comment_count_for_current_round(proposal)

    if proposal.status == Proposal.OverallStatus.DRAFT:
        return f"Step {_get_current_step(proposal)} of {_get_total_proposal_steps()}"

    if process_label == "Proposal":
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION:
            return f"{_get_comment_count_for_current_round(proposal)} review comment(s) pending"
        if proposal.proposal_status == Proposal.ProposalStatus.IN_REVIEW:
            review_level = _get_review_level(proposal)
            if review_level == "DEPARTMENT":
                return "Department review ongoing"
            if review_level == "CAMPUS":
                return "Campus review ongoing"
            if review_level == "DIRECTOR":
                return "Director review ongoing"
            return "Review ongoing"
        if proposal.proposal_status == Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED:
            return "Summary sent to proponent"
        if proposal.proposal_status == Proposal.ProposalStatus.READY_FOR_PRINTING:
            return "Ready for printing"
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD:
            return "Awaiting submission and upload"
        if proposal.proposal_status == Proposal.ProposalStatus.APPROVED:
            return "Approved documents in progress"
        return proposal.get_proposal_status_display()

    if process_label == "MOA":
        return proposal.get_moa_status_display()

    if process_label == "Implementation":
        return proposal.get_implementation_status_display()

    return "Lifecycle finished"


def _get_lifecycle_description(proposal):
    process_label = _get_process_label(proposal)

    if proposal.status == Proposal.OverallStatus.DRAFT:
        return (
            f"The proposal is still being prepared and is currently on Step "
            f"{_get_current_step(proposal)} of {_get_total_proposal_steps()}."
        )

    if process_label == "Proposal":
        if proposal.proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW:
            return "The proposal has been submitted and is queued for review."
        if proposal.proposal_status == Proposal.ProposalStatus.IN_REVIEW:
            return "The proposal is currently undergoing institutional review."
        if proposal.proposal_status == Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED:
            return "The review summary has been prepared and issued to the proponent."
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION:
            return "The proposal has been returned to the proponent for revision."
        if proposal.proposal_status == Proposal.ProposalStatus.READY_FOR_PRINTING:
            return "The proposal is cleared and ready for printing."
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD:
            return "Signed and digital copies are being submitted and uploaded."
        if proposal.proposal_status == Proposal.ProposalStatus.APPROVED:
            return (
                "The proposal is approved. Post-approval documents such as the "
                "Letter of Award, Endorsement, and Extension Agreement may now be processed."
            )
        if proposal.proposal_status == Proposal.ProposalStatus.COMPLETED:
            return "The proposal phase has been completed."
        return "The proposal is currently active in the proposal phase."

    if process_label == "MOA":
        return "The extension is currently in the MOA processing phase."

    if process_label == "Implementation":
        return "The extension is currently in the implementation and reporting phase."

    return "The extension lifecycle has been completed and formally closed."


def _build_proposal_dashboard_item(proposal):
    submitted_at = getattr(proposal, "submitted_at", None)
    updated_at = getattr(proposal, "last_saved_at", None)
    comment_count = _get_comment_count_for_current_round(proposal)

    days_since_submission = None
    if submitted_at:
        try:
            days_since_submission = max((timezone.now() - submitted_at).days, 0)
        except (TypeError, ValueError):
            # submitted_at is not a comparable datetime.
            days_since_submission = None

    scope_label = proposal.get_scope_type_display() if getattr(proposal, "scope_type", None) else "—"
    process_label = _get_process_label(proposal)

    is_for_revision = (
        proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION
        or proposal.moa_status == Proposal.MOAStatus.FOR_REVISION
        or proposal.implementation_status == Proposal.ImplementationStatus.REVISION
    )

    is_draft = (
        proposal.status == Proposal.OverallStatus.DRAFT
        and proposal.proposal_status == Proposal.ProposalStatus.DRAFTING
    )

    needs_attention = bool(
        is_for_revision
        or proposal.proposal_status in {
            Proposal.ProposalStatus.READY_FOR_PRINTING,
            Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
        }
        or (comment_count > 0 and proposal.proposal_status in {
            Proposal.ProposalStatus.FOR_REVISION,
            Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
        })
    )

    return {
        "proposal": proposal,
        "current_step": _get_current_step(proposal),
        "total_steps": _get_total_proposal_steps(),
        "progress_percent": proposal.overall_progress,
        "status_label": proposal.current_status_label,
        "status_stage": proposal.current_phase_label,
        "status_milestone": _get_lifecycle_milestone(proposal),
        "status_description": _get_lifecycle_description(proposal),
        "process_label": process_label,
        "comment_count": comment_count,
        "submitted_at": submitted_at,
        "updated_at": updated_at,
        "days_since_submission": days_since_submission,
        "is_for_revision": is_for_revision,
        "needs_attention": needs_attention,
        "is_draft": is_draft,
        "scope_label": scope_label,
        "proposal_fill": min(proposal.proposal_progress, 100),
        "proposal_remaining": max(0, 100 - proposal.proposal_progress),
        "moa_fill": min(proposal.moa_progress, 100),
        "moa_remaining": max(0, 100 - proposal.moa_progress),
        "implementation_fill": min(proposal.implementation_progress, 100),
        "implementation_remaining": max(0, 100 - proposal.implementation_progress),
    }


def _get_user_proposals_context(user):
    my_proposals = (
        _proposal_scope_for_user(user).filter(
            Q(created_by=user)
            | Q(proponents__user=user)
            | Q(collaborators__user=user)
        )
        .distinct()
        .order_by("-last_saved_at")
        .prefetch_related("proponents", "collaborators")
    )

    drafts = my_proposals.filter(
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).order_by("-last_saved_at")

    submitted_queryset = my_proposals.exclude(
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).annotate(
        _attention_rank=Case(
            When(proposal_status=Proposal.ProposalStatus.FOR_REVISION, then=0),
            When(proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING, then=1),
            When(proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD, then=1),
            When(proposal_status=Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED, then=2),
            default=3,
            output_field=IntegerField(),
        )
    ).order_by("_attention_rank", "-submitted_at", "-last_saved_at")

    all_proposals = [_build_proposal_dashboard_item(proposal) for proposal in my_proposals]

    # --- Signed proposal flag (for hiding Download/Upload buttons once signed is uploaded) ---
    proposal_ids = [item["proposal"].id for item in all_proposals]
    signed_ids = set(
        ProposalFinalDocument.objects.filter(
            proposal_id__in=proposal_ids,
            document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
        ).values_list("proposal_id", flat=True)
    )
    for item in all_proposals:
        item["signed_uploaded"] = item["proposal"].id in signed_ids

    # Attach released approval documents for Approved/Claiming cards (LOA/Endorsement/Agreement)
    from proposals.models import ProposalFinalDocument as _PFD
    doc_types = [
        _PFD.DocumentType.LETTER_OF_AWARD,
        _PFD.DocumentType.ENDORSEMENT_FOR_APPROVAL,
        _PFD.DocumentType.EXTENSION_AGREEMENT,
    ]
    docs = _PFD.objects.filter(
        proposal_id__in=proposal_ids,
        document_type__in=doc_types,
    ).select_related("proposal")

    docs_by_pid = {}
    for d in docs:
        docs_by_pid.setdefault(d.proposal_id, {})[d.document_type] = d

    for item in all_proposals:
        pid = item["proposal"].id
        by_type = docs_by_pid.get(pid, {})
        item["loa_doc"] = by_type.get(_PFD.DocumentType.LETTER_OF_AWARD)
        item["endorse_doc"] = by_type.get(_PFD.DocumentType.ENDORSEMENT_FOR_APPROVAL)
        item["agreement_doc"] = by_type.get(_PFD.DocumentType.EXTENSION_AGREEMENT)

        # Claim is enabled when proposal is Approved/Claiming and all 3 docs exist.
        item["can_claim"] = (
            item["proposal"].proposal_status == Proposal.ProposalStatus.APPROVED
            and item["loa_doc"] is not None
            and item["endorse_doc"] is not None
            and item["agreement_doc"] is not None
        )


    needs_attention_count = sum(1 for item in all_proposals if item.get("needs_attention"))
    # Sort proposals that need attention first (stable sort keeps existing ordering within groups)
    all_proposals.sort(key=lambda x: (not x.get("needs_attention", False)))

    proposal_phase_count = 0
    moa_phase_count = 0
    implementation_phase_count = 0
    completed_phase_count = 0

    for item in all_proposals:
        process_label = item["process_label"]
        if process_label == "Completed":
            completed_phase_count += 1
        elif process_label == "Implementation":
            implementation_phase_count += 1
        elif process_label == "MOA":
            moa_phase_count += 1
        else:
            proposal_phase_count += 1

    under_review_count = submitted_queryset.filter(
        proposal_status__in=[
            Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
            Proposal.ProposalStatus.IN_REVIEW,
            Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
            Proposal.ProposalStatus.FOR_REVISION,
        ]
    ).count()

    approved_count = submitted_queryset.filter(
        proposal_status__in=[
            Proposal.ProposalStatus.READY_FOR_PRINTING,
            Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
            Proposal.ProposalStatus.APPROVED,
            Proposal.ProposalStatus.COMPLETED,
        ]
    ).count()

    return {
        "drafts": drafts,
        "submitted_proposals": submitted_queryset,
        "all_proposals": all_proposals,
        "draft_count": drafts.count(),
        "submitted_count": submitted_queryset.count(),
        "under_review_count": under_review_count,
        "approved_count": approved_count,
        "needs_attention_count": needs_attention_count,
        "proposal_phase_count": proposal_phase_count,
        "moa_phase_count": moa_phase_count,
        "implementation_phase_count": implementation_phase_count,
        "completed_phase_count": completed_phase_count,
    }


def _get_reviewable_proposal_statuses():
    return [
        Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
        Proposal.ProposalStatus.IN_REVIEW,
    ]


def _get_department_review_queue(user):
    profile = getattr(user, "profile", None)
    department = (getattr(profile, "department", "") or "").strip()

    return (
        _proposal_scope_for_user(user).filter(
            department=department,
            proposal_status__in=_get_reviewable_proposal_statuses(),
        )
        .exclude(created_by=user)
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_campus_review_queue(user):
    profile = getattr(user, "profile", None)
    campus = (getattr(profile, "campus", "") or "").strip()

    return (
        _proposal_scope_for_user(user).filter(
            campus=campus,
            proposal_status__in=_get_reviewable_proposal_statuses(),
        )
        .exclude(created_by=user)
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_director_review_queue(user):
    return (
        _proposal_scope_for_user(user).filter(
            proposal_status__in=[
                Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
                Proposal.ProposalStatus.IN_REVIEW,
            ]
        )
        .exclude(created_by=user)
        .exclude(
            review_rounds__ready_for_staff_summary=True,
            review_rounds__is_closed=False,
        )
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_evaluator_review_queue(user):
    return (
        _proposal_scope_for_user(user).filter(
            evaluator_assignments__evaluator=user,
            evaluator_assignments__is_active=True,
            proposal_status__in=_get_reviewable_proposal_statuses(),
        )
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_staff_summary_queue():
    return (
        Proposal.objects.filter(
            review_rounds__ready_for_staff_summary=True,
            review_rounds__is_closed=False,
            proposal_status=Proposal.ProposalStatus.IN_REVIEW,
        )
        .exclude(review_rounds__summaries__isnull=False)
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_director_monitored_proposals(request):
    qs = (
        Proposal.objects.filter(institution=_user_institution(request.user))
        .select_related("created_by", "created_by__profile")
        .prefetch_related("proponents__user", "collaborators__user")
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )

    campus_filter = (request.GET.get("campus") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    scope_filter = (request.GET.get("scope") or "").strip()
    search = (request.GET.get("q") or "").strip()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()

    if campus_filter:
        qs = qs.filter(campus=campus_filter)

    if status_filter:
        qs = qs.filter(proposal_status=status_filter)

    if scope_filter:
        qs = qs.filter(scope_type=scope_filter)

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(research_title__icontains=search))

    if date_from:
        qs = qs.filter(last_saved_at__date__gte=date_from)

    if date_to:
        qs = qs.filter(last_saved_at__date__lte=date_to)

    return qs


def _get_proposal_prohibited_evaluator_ids(proposal):
    prohibited_ids = {proposal.created_by_id}

    proponent_user_ids = set(
        proposal.proponents.exclude(user__isnull=True).values_list("user_id", flat=True)
    )
    collaborator_user_ids = set(
        proposal.collaborators.exclude(user__isnull=True).values_list("user_id", flat=True)
    )

    prohibited_ids.update(proponent_user_ids)
    prohibited_ids.update(collaborator_user_ids)
    return prohibited_ids


def _get_assigned_evaluators_for_proposal(proposal):
    return [
        assignment.evaluator
        for assignment in proposal.evaluator_assignments.filter(is_active=True).select_related("evaluator__profile")
    ]


def _get_assignable_evaluators_for_proposal(proposal):
    prohibited_ids = _get_proposal_prohibited_evaluator_ids(proposal)

    already_assigned_ids = set(
        proposal.evaluator_assignments.filter(is_active=True).values_list("evaluator_id", flat=True)
    )

    return list(
        User.objects.filter(
            profile__institution=proposal.institution,
            is_active=True,
            profile__role__in=[
                Profile.ROLE_FACULTY,
                Profile.ROLE_EVALUATOR,
                Profile.ROLE_DEPARTMENT_COORDINATOR,
                Profile.ROLE_CAMPUS_COORDINATOR,
            ],
        )
        .exclude(id__in=prohibited_ids)
        .exclude(id__in=already_assigned_ids)
        .select_related("profile")
        .order_by("profile__full_name", "username")
    )


def _review_round_field_names():
    return {field.name for field in ProposalReviewRound._meta.get_fields() if hasattr(field, "name")}


def _get_open_review_round(proposal):
    # Both accessors are optional on older records, so a miss is normal here
    # and only unexpected failures are worth logging.
    try:
        current_round = proposal.get_active_review_round()
        if current_round:
            return current_round
    except (AttributeError, ObjectDoesNotExist):
        pass
    except Exception:
        logger.exception("get_active_review_round failed for proposal %s.", proposal.pk)

    try:
        current_round = proposal.get_current_review_round()
        if current_round and not getattr(current_round, "is_closed", False):
            return current_round
    except (AttributeError, ObjectDoesNotExist):
        pass
    except Exception:
        logger.exception("get_current_review_round failed for proposal %s.", proposal.pk)

    field_names = _review_round_field_names()
    qs = ProposalReviewRound.objects.filter(proposal=proposal)

    if "is_closed" in field_names:
        open_round = qs.filter(is_closed=False).order_by("-id").first()
        if open_round:
            return open_round

    return qs.order_by("-id").first()


def _create_review_round_for_proposal(proposal, user):
    field_names = _review_round_field_names()

    next_round_no = 1
    if "round_no" in field_names:
        last_round = (
            ProposalReviewRound.objects.filter(proposal=proposal)
            .order_by("-round_no")
            .values_list("round_no", flat=True)
            .first()
        )
        next_round_no = (last_round or 0) + 1

    create_kwargs = {"proposal": proposal}

    if "round_no" in field_names:
        create_kwargs["round_no"] = next_round_no
    if "started_by" in field_names:
        create_kwargs["started_by"] = user
    if "created_by" in field_names:
        create_kwargs["created_by"] = user
    if "opened_by" in field_names:
        create_kwargs["opened_by"] = user
    if "is_closed" in field_names:
        create_kwargs["is_closed"] = False
    if "ready_for_staff_summary" in field_names:
        create_kwargs.setdefault("ready_for_staff_summary", False)

    return ProposalReviewRound.objects.create(**create_kwargs)


def _get_or_create_open_review_round(proposal, user):
    review_round = _get_open_review_round(proposal)
    if review_round:
        return review_round
    return _create_review_round_for_proposal(proposal, user)
