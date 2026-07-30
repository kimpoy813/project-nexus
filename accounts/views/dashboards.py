"""
The seven role dashboards and the evaluator-assignment actions they expose.
"""
import logging
from collections import OrderedDict

from datetime import timedelta
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from details.models import Activity
from details.models import DocumentTemplate
from details.models import DynamicFormTemplate
from details.models import ExtensionProcess
from details.models import Personnel
from details.models import ProposalWizardStepConfig
from details.models import RoleCapability
from details.models import SitePage
from details.models import Target
from proposals.models import MOASubmission
from proposals.models import Proposal
from proposals.models import ProposalCommentSummary
from proposals.models import ProposalEvaluatorAssignment
from proposals.models import ProposalFinalDocument
from proposals.models import ProposalReviewRound
from proposals.models import ProposalSectionComment
from ..decorators import admin_required
from ..decorators import faculty_like_required
from ..decorators import role_required
from ..models import Profile
from ..models import Signatory
from ..models import SiteConfiguration
from ..models import SiteConfigurationLog
from ..tenancy import get_user_institution
from .helpers import User, _get_or_create_profile, _get_role_dashboard_name
from .proposal_queries import _build_proposal_dashboard_item, _get_assignable_evaluators_for_proposal, _get_assigned_evaluators_for_proposal, _get_campus_review_queue, _get_department_review_queue, _get_director_monitored_proposals, _get_evaluator_review_queue, _get_open_review_round, _get_or_create_open_review_round, _get_proposal_prohibited_evaluator_ids, _get_user_proposals_context

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    return redirect(_get_role_dashboard_name(profile.role))


@login_required
def dashboard_redirect(request):
    profile, _ = _get_or_create_profile(request.user)
    return redirect(_get_role_dashboard_name(profile.role))


@login_required
@faculty_like_required
def faculty_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    assigned_review_queue = _get_evaluator_review_queue(request.user)

    proposals_ctx = _get_user_proposals_context(request.user)

    # Proposals that require proponent action
    printing_ready_count = (
        Proposal.objects.filter(
            Q(created_by=request.user) | Q(proponents__user=request.user),
            institution=get_user_institution(request.user),
            proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING,
        )
        .distinct()
        .count()
    )
    approved_download_count = printing_ready_count  # alias used by templates


    upload_required_count = (
        Proposal.objects.filter(
            Q(created_by=request.user) | Q(proponents__user=request.user),
            institution=get_user_institution(request.user),
            proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
        )
        .distinct()
        .count()
    )

    # Show the banner for proposals that were returned for revision
    # and also those with an issued summary if your workflow still uses that state.
    revision_statuses = {
        Proposal.ProposalStatus.FOR_REVISION,
        Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
    }

    revision_proposals = (
        Proposal.objects.filter(
            Q(created_by=request.user)
            | Q(proponents__user=request.user)
            | Q(collaborators__user=request.user),
            institution=get_user_institution(request.user),
            proposal_status__in=revision_statuses,
        )
        .distinct()
        .select_related("created_by", "created_by__profile")
        .order_by("-last_saved_at", "-submitted_at", "-id")
    )

    context = {
        "profile": profile,
        "nav_notif_count": (proposals_ctx.get("needs_attention_count", 0) + assigned_review_queue.count() + printing_ready_count + upload_required_count),
        "printing_ready_count": printing_ready_count,
        "upload_required_count": upload_required_count,
        "approved_download_count": approved_download_count,
        **proposals_ctx,
        "assigned_review_queue": assigned_review_queue,
        "assigned_review_count": assigned_review_queue.count(),
        "has_evaluator_assignments": assigned_review_queue.exists(),
        "revision_proposals": revision_proposals,
        "revision_count": revision_proposals.count(),
    }

    return render(request, "dashboard/faculty_dashboard.html", context)


@login_required
@role_required(["EVALUATOR"])
def evaluator_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    assigned_review_queue = _get_evaluator_review_queue(request.user)
    proposals_ctx = _get_user_proposals_context(request.user)

    context = {
        "profile": profile,
        "nav_notif_count": proposals_ctx.get("needs_attention_count", 0) + assigned_review_queue.count(),
        **proposals_ctx,
        "assigned_review_queue": assigned_review_queue,
        "assigned_review_count": assigned_review_queue.count(),
        "has_evaluator_assignments": assigned_review_queue.exists(),
    }
    return render(request, "dashboard/evaluator_dashboard.html", context)


@login_required
@role_required(["DIRECTOR"])
def director_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)

    from django.db.models import Q

    review_queue = Proposal.objects.filter(
        Q(proposal_status=Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW)
        | Q(proposal_status=Proposal.ProposalStatus.IN_REVIEW)
        | Q(proposal_status=Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED)
        | Q(proposal_status=Proposal.ProposalStatus.FOR_REVISION)
        | Q(proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING)
        | Q(proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD)
        | Q(proposal_status=Proposal.ProposalStatus.APPROVED)
        | Q(proposal_status=Proposal.ProposalStatus.COMPLETED)
    ).filter(institution=get_user_institution(request.user)).order_by("-submitted_at")

    # Count only items that still require director-side workflow attention (exclude Approved/Completed)
    action_queue_count = review_queue.exclude(
        proposal_status__in=[
            Proposal.ProposalStatus.READY_FOR_PRINTING,
            Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
            Proposal.ProposalStatus.APPROVED,
            Proposal.ProposalStatus.COMPLETED,
        ]
    ).count()

    for proposal in review_queue:
        proposal.assigned_evaluators = _get_assigned_evaluators_for_proposal(proposal)
        proposal.available_evaluators = _get_assignable_evaluators_for_proposal(proposal)

    monitored_queryset = _get_director_monitored_proposals(request)
    monitored_items = [_build_proposal_dashboard_item(proposal) for proposal in monitored_queryset]

    selected_process = (request.GET.get("process") or "").strip()
    selected_campus = (request.GET.get("campus") or "").strip()
    selected_status = (request.GET.get("status") or "").strip()
    selected_scope = (request.GET.get("scope") or "").strip()
    selected_date_from = (request.GET.get("date_from") or "").strip()
    selected_date_to = (request.GET.get("date_to") or "").strip()
    search_query = (request.GET.get("q") or "").strip()

    if selected_process:
        process_map = {
            "PROPOSAL": "Proposal",
            "MOA": "MOA",
            "IMPLEMENTATION": "Implementation",
            "COMPLETED": "Completed",
        }
        wanted_label = process_map.get(selected_process)
        if wanted_label:
            monitored_items = [
                item for item in monitored_items
                if item.get("process_label") == wanted_label
            ]

    def build_campus_stats_from_items(items):
        grouped = {}

        for item in items:
            proposal = item["proposal"]
            campus = (proposal.campus or "").strip() or "Unassigned Campus"

            if campus not in grouped:
                grouped[campus] = {
                    "campus": campus,
                    "total": 0,
                    "proposal_count": 0,
                    "moa_count": 0,
                    "implementation_count": 0,
                    "completed_count": 0,
                    "pending_count": 0,
                    "under_review_count": 0,
                    "approved_count": 0,
                    "revision_count": 0,
                    "active_pipeline_count": 0,
                    "review_backlog_count": 0,
                    "completion_rate": 0,
                }

            row = grouped[campus]
            row["total"] += 1

            process_label = item.get("process_label", "Proposal")
            if process_label == "Proposal":
                row["proposal_count"] += 1
            elif process_label == "MOA":
                row["moa_count"] += 1
            elif process_label == "Implementation":
                row["implementation_count"] += 1
            elif process_label == "Completed":
                row["completed_count"] += 1

            p = item["proposal"]

            if p.proposal_status in [
                Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
                Proposal.ProposalStatus.IN_REVIEW,
                Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
                Proposal.ProposalStatus.FOR_REVISION,
            ]:
                row["pending_count"] += 1

            if p.proposal_status == Proposal.ProposalStatus.IN_REVIEW:
                row["under_review_count"] += 1

            if p.proposal_status in [
                Proposal.ProposalStatus.APPROVED,
                Proposal.ProposalStatus.COMPLETED,
            ]:
                row["approved_count"] += 1

            if (
                p.proposal_status == Proposal.ProposalStatus.FOR_REVISION
                or p.moa_status == Proposal.MOAStatus.FOR_REVISION
                or p.implementation_status == Proposal.ImplementationStatus.REVISION
            ):
                row["revision_count"] += 1

        for row in grouped.values():
            row["active_pipeline_count"] = (
                row["proposal_count"] + row["moa_count"] + row["implementation_count"]
            )
            row["review_backlog_count"] = (
                row["pending_count"] + row["under_review_count"] + row["revision_count"]
            )
            row["completion_rate"] = round(
                (row["completed_count"] / row["total"]) * 100, 1
            ) if row["total"] else 0

        return sorted(grouped.values(), key=lambda x: x["campus"].lower())

    campus_stats = build_campus_stats_from_items(monitored_items)

    institution_total = len(monitored_items)

    submitted_total = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW
    )
    under_review_total = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status == Proposal.ProposalStatus.IN_REVIEW
    )
    institution_revision = sum(1 for item in monitored_items if item["is_for_revision"])
    institution_approved = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status in [
            Proposal.ProposalStatus.APPROVED,
            Proposal.ProposalStatus.COMPLETED,
        ]
    )
    institution_completed = sum(
        1 for item in monitored_items
        if item["proposal"].status == Proposal.OverallStatus.COMPLETED
        or item.get("process_label") == "Completed"
    )

    institution_pending = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status in [
            Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
            Proposal.ProposalStatus.IN_REVIEW,
            Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
            Proposal.ProposalStatus.FOR_REVISION,
        ]
    )

    proposal_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "Proposal"
    )
    moa_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "MOA"
    )
    implementation_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "Implementation"
    )
    completed_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "Completed"
    )

    active_pipeline_total = (
        proposal_process_total + moa_process_total + implementation_process_total
    )

    overall_completion_rate = round(
        (institution_completed / institution_total) * 100, 1
    ) if institution_total else 0

    review_backlog_total = submitted_total + under_review_total + institution_revision

    top_completed_campus = None
    top_completion_rate_campus = None
    top_backlog_campus = None

    if campus_stats:
        top_completed_campus = max(campus_stats, key=lambda x: x["completed_count"])
        top_completion_rate_campus = max(campus_stats, key=lambda x: x["completion_rate"])
        top_backlog_campus = max(campus_stats, key=lambda x: x["review_backlog_count"])

    paginator = Paginator(monitored_items, 10)
    page_number = request.GET.get("page")
    monitored_page = paginator.get_page(page_number)

    campuses = (
        Proposal.objects.filter(institution=get_user_institution(request.user)).exclude(campus__isnull=True)
        .exclude(campus__exact="")
        .values_list("campus", flat=True)
        .distinct()
        .order_by("campus")
    )

    process_chart_labels = ["Proposal", "MOA", "Implementation", "Completed"]
    process_chart_data = [
        proposal_process_total,
        moa_process_total,
        implementation_process_total,
        completed_process_total,
    ]

    status_chart_labels = ["Submitted", "In Review", "Revision", "Approved", "Completed"]
    status_chart_data = [
        submitted_total,
        under_review_total,
        institution_revision,
        institution_approved,
        institution_completed,
    ]

    campus_chart_labels = [item["campus"] for item in campus_stats]
    campus_chart_total = [item["total"] for item in campus_stats]
    campus_chart_completed = [item["completed_count"] for item in campus_stats]
    campus_chart_backlog = [item["review_backlog_count"] for item in campus_stats]
    campus_chart_completion_rate = [item["completion_rate"] for item in campus_stats]
    campus_chart_proposal = [item["proposal_count"] for item in campus_stats]
    campus_chart_moa = [item["moa_count"] for item in campus_stats]
    campus_chart_implementation = [item["implementation_count"] for item in campus_stats]
    campus_chart_pending = [item["pending_count"] for item in campus_stats]
    campus_chart_under_review = [item["under_review_count"] for item in campus_stats]
    campus_chart_revision = [item["revision_count"] for item in campus_stats]

    proposals_ctx = _get_user_proposals_context(request.user)

    context = {
        "profile": profile,
        "nav_notif_count": action_queue_count,
        **proposals_ctx,
        "review_queue": review_queue,
        "review_queue_count": action_queue_count,
        "monitored_page": monitored_page,
        "campus_stats": campus_stats,
        "institution_total": institution_total,
        "institution_pending": institution_pending,
        "institution_revision": institution_revision,
        "institution_approved": institution_approved,
        "institution_completed": institution_completed,
        "submitted_total": submitted_total,
        "under_review_total": under_review_total,
        "proposal_process_total": proposal_process_total,
        "moa_process_total": moa_process_total,
        "implementation_process_total": implementation_process_total,
        "completed_process_total": completed_process_total,
        "active_pipeline_total": active_pipeline_total,
        "review_backlog_total": review_backlog_total,
        "overall_completion_rate": overall_completion_rate,
        "top_completed_campus": top_completed_campus,
        "top_completion_rate_campus": top_completion_rate_campus,
        "top_backlog_campus": top_backlog_campus,
        "campus_choices": campuses,
        "selected_campus": selected_campus,
        "selected_process": selected_process,
        "selected_status": selected_status,
        "selected_scope": selected_scope,
        "selected_date_from": selected_date_from,
        "selected_date_to": selected_date_to,
        "search_query": search_query,
        "process_chart_labels": json.dumps(process_chart_labels),
        "process_chart_data": json.dumps(process_chart_data),
        "status_chart_labels": json.dumps(status_chart_labels),
        "status_chart_data": json.dumps(status_chart_data),
        "campus_chart_labels": json.dumps(campus_chart_labels),
        "campus_chart_total": json.dumps(campus_chart_total),
        "campus_chart_completed": json.dumps(campus_chart_completed),
        "campus_chart_backlog": json.dumps(campus_chart_backlog),
        "campus_chart_completion_rate": json.dumps(campus_chart_completion_rate),
        "campus_chart_proposal": json.dumps(campus_chart_proposal),
        "campus_chart_moa": json.dumps(campus_chart_moa),
        "campus_chart_implementation": json.dumps(campus_chart_implementation),
        "campus_chart_pending": json.dumps(campus_chart_pending),
        "campus_chart_under_review": json.dumps(campus_chart_under_review),
        "campus_chart_revision": json.dumps(campus_chart_revision),
        "review_year_choices": (
            Proposal.objects.exclude(submitted_at__isnull=True)
            .dates("submitted_at", "year", order="DESC")
        ),
    }

    return render(request, "dashboard/director_dashboard.html", context)


@login_required
@role_required(["DIRECTOR", "STAFF"])
@require_POST
def proposal_mark_ready_for_summary(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    review_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not review_round:
        messages.error(request, "No active review round found.")
        return redirect("director_dashboard")

    # Block re-queue if summary already sent for this round
    if ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=review_round,
        sent_to_proponent=True,
    ).exists():
        messages.warning(request, "A summary has already been issued for the current review round.")
        return redirect("director_dashboard")

    # Require at least one director comment in this round
    has_director_comment = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=review_round,
        reviewer=request.user,
        reviewer_role="DIRECTOR",
    ).exists()
    if not has_director_comment:
        messages.error(request, "Please add at least one director comment before marking ready for summary.")
        return redirect("director_dashboard")

    if not getattr(review_round, "ready_for_staff_summary", False):
        review_round.ready_for_staff_summary = True
        review_round.save(update_fields=["ready_for_staff_summary"])

    proposal.proposal_status = Proposal.ProposalStatus.IN_REVIEW
    proposal.save(update_fields=["proposal_status"])

    messages.success(request, "Proposal marked ready for staff summary.")
    return redirect("director_dashboard")


@login_required
@role_required(["DIRECTOR"])
@require_POST
def proposal_assign_evaluator(request, proposal_id, evaluator_id):
    try:
        proposal = get_object_or_404(
            Proposal.objects.prefetch_related(
                "proponents__user",
                "collaborators__user",
                "review_rounds",
                "evaluator_assignments__evaluator__profile",
            ),
            id=proposal_id,
        )

        evaluator = get_object_or_404(
            User.objects.select_related("profile"),
            id=evaluator_id,
            is_active=True,
        )

        allowed_roles = {
            Profile.ROLE_FACULTY,
            Profile.ROLE_EVALUATOR,
            Profile.ROLE_DEPARTMENT_COORDINATOR,
            Profile.ROLE_CAMPUS_COORDINATOR,
        }

        evaluator_role = getattr(getattr(evaluator, "profile", None), "role", "")
        if evaluator_role not in allowed_roles:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "Selected user cannot be assigned as evaluator."},
                    status=400,
                )
            messages.error(request, "Selected user cannot be assigned as evaluator.")
            return redirect("director_dashboard")

        prohibited_ids = _get_proposal_prohibited_evaluator_ids(proposal)
        if evaluator.id in prohibited_ids:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "This faculty member cannot be assigned as evaluator for this proposal."},
                    status=400,
                )
            messages.error(request, "This faculty member cannot be assigned as evaluator for this proposal.")
            return redirect("director_dashboard")

        review_round = _get_or_create_open_review_round(proposal, request.user)

        assignment, created = ProposalEvaluatorAssignment.objects.get_or_create(
            proposal=proposal,
            review_round=review_round,
            evaluator=evaluator,
            defaults={
                "assigned_by": request.user,
                "is_active": True,
                "is_completed": False,
            },
        )

        if not created:
            changed = False

            if not assignment.is_active:
                assignment.is_active = True
                changed = True

            if assignment.is_completed:
                assignment.is_completed = False
                changed = True

            if assignment.assigned_by_id != request.user.id:
                assignment.assigned_by = request.user
                changed = True

            if changed:
                assignment.save()

        if proposal.proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW:
            proposal.transition_proposal_status(
                Proposal.ProposalStatus.IN_REVIEW
            )
            proposal.save(update_fields=["proposal_status"])

        assigned_evaluators = _get_assigned_evaluators_for_proposal(proposal)
        available_evaluators = _get_assignable_evaluators_for_proposal(proposal)

        evaluator_name = getattr(getattr(evaluator, "profile", None), "full_name", "") or evaluator.username

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "ok": True,
                "message": f'"{evaluator_name}" has been added as evaluator.',
                "proposal_id": str(proposal.id),
                "assigned_evaluators": [
                    {
                        "id": ev.id,
                        "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                        "remove_url": reverse("proposal_remove_evaluator", args=[proposal.id, ev.id]),
                    }
                    for ev in assigned_evaluators
                ],
                "available_evaluators": [
                    {
                        "id": ev.id,
                        "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                    }
                    for ev in available_evaluators
                ],
                "status_label": proposal.current_status_label,
            })

        messages.success(request, f'"{evaluator_name}" has been added as evaluator.')
        return redirect("director_dashboard")

    except Exception:
        logger.exception("Failed to assign evaluator on proposal %s.", proposal_id)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "Server error. The problem has been logged."},
                status=500,
            )
        raise


@login_required
@role_required(["DIRECTOR"])
@require_POST
def proposal_remove_evaluator(request, proposal_id, evaluator_id):
    proposal = get_object_or_404(
        Proposal.objects.prefetch_related(
            "evaluator_assignments__evaluator__profile",
            "proponents__user",
            "collaborators__user",
            "review_rounds",
        ),
        id=proposal_id,
    )

    review_round = _get_open_review_round(proposal)

    qs = ProposalEvaluatorAssignment.objects.filter(
        proposal=proposal,
        evaluator_id=evaluator_id,
        is_active=True,
    )

    if review_round is not None:
        qs = qs.filter(review_round=review_round)

    assignment = qs.first()

    if not assignment:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Evaluator assignment not found."}, status=404)
        messages.error(request, "Evaluator assignment not found.")
        return redirect("director_dashboard")

    assignment.is_active = False
    assignment.save(update_fields=["is_active"])

    assigned_evaluators = _get_assigned_evaluators_for_proposal(proposal)
    available_evaluators = _get_assignable_evaluators_for_proposal(proposal)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "message": "Evaluator removed successfully.",
            "proposal_id": str(proposal.id),
            "assigned_evaluators": [
                {
                    "id": ev.id,
                    "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                    "remove_url": reverse("proposal_remove_evaluator", args=[proposal.id, ev.id]),
                }
                for ev in assigned_evaluators
            ],
            "available_evaluators": [
                {
                    "id": ev.id,
                    "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                }
                for ev in available_evaluators
            ],
        })

    messages.success(request, "Evaluator removed successfully.")
    return redirect("director_dashboard")


@login_required
@role_required(["STAFF"])
def staff_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)

    # Pull ALL review rounds flagged as ready (latest first).
    # Do NOT filter by is_closed here — some workflows may close the round when marking ready.
    ready_rounds = (
        ProposalReviewRound.objects.filter(proposal__institution=get_user_institution(request.user), ready_for_staff_summary=True)
        .select_related("proposal", "proposal__created_by", "proposal__created_by__profile")
        .order_by("-id")
    )

    # Keep only the latest ready round per proposal (prevents duplicates if any historical rounds were flagged).
    latest_by_proposal = OrderedDict()
    for rr in ready_rounds:
        pid = rr.proposal_id
        if pid not in latest_by_proposal:
            latest_by_proposal[pid] = rr

    summary_queue = []
    pending_count = 0
    draft_count = 0

    for rr in latest_by_proposal.values():
        p = rr.proposal

        # Status flags for TEMPLATE (these are dynamic attrs, not model fields)
        p.active_round_no = getattr(rr, "round_no", None) or 1

        # Summaries are tied to the review round.
        # Prefer rr.summaries if your FK uses related_name="summaries"; fallback to ProposalCommentSummary.
        try:
            summaries_qs = rr.summaries.all()
        except AttributeError:
            # The FK does not declare related_name="summaries" on this model.
            summaries_qs = ProposalCommentSummary.objects.filter(review_round=rr)

        p.summary_sent = summaries_qs.filter(sent_to_proponent=True).exists()
        p.has_draft_summary = summaries_qs.filter(sent_to_proponent=False).exists()

        # Queue rule:
        # - show if NOT sent
        # - count as draft if saved but not sent
        # - count as pending if nothing saved yet
        if p.summary_sent:
            continue

        if p.has_draft_summary:
            draft_count += 1
        else:
            pending_count += 1

        summary_queue.append(p)

    # Sort newest first (submitted_at, then last_saved_at)
    summary_queue.sort(
        key=lambda x: (
            getattr(x, "submitted_at", None) or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()),
            getattr(x, "last_saved_at", None) or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()),
        ),
        reverse=True,
    )

    # --- Signed Proposal Verification queue (uploaded but not yet verified) ---
    signed_queue = ProposalFinalDocument.objects.filter(
        proposal__institution=get_user_institution(request.user),
        document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
        is_verified=False,
        proposal__proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
    ).select_related(
        "proposal",
        "proposal__created_by",
        "proposal__created_by__profile",
        "uploaded_by",
        "uploaded_by__profile",
    ).order_by("-uploaded_at")

    signed_pending_count = signed_queue.count()

    # --- MOA workflow queue ---
    # Once a proponent generates/uploads a draft MOA, it appears here so Staff can
    # open the MOA Tracker, send it to Legal Review, return it for revision,
    # mark Certification Ready, move it to Agenda Brief & Presentation, and
    # finally mark it as MOA Completed.
    active_moa_statuses = [
        Proposal.MOAStatus.NOT_STARTED,  # legacy uploads before automatic Draft status
        Proposal.MOAStatus.DRAFT,
        Proposal.MOAStatus.LEGAL_REVIEW,
        Proposal.MOAStatus.FOR_REVISION,
        Proposal.MOAStatus.CERTIFICATION_READY,
        Proposal.MOAStatus.AGENDA_AND_PRESENTATION,
    ]

    moa_proposals = list(
        Proposal.objects.filter(
            institution=get_user_institution(request.user),
            requires_moa=True,
            moa_status__in=active_moa_statuses,
        )
        .filter(
            Q(moa_submission__isnull=False)
            | Q(final_documents__document_type=ProposalFinalDocument.DocumentType.MOA)
            | Q(moa_draft_file__isnull=False)
        )
        .select_related("created_by", "created_by__profile")
        .distinct()
    )

    moa_proposal_ids = [proposal.id for proposal in moa_proposals]

    submissions_by_proposal = {
        submission.proposal_id: submission
        for submission in MOASubmission.objects.filter(
            proposal_id__in=moa_proposal_ids,
        ).select_related("submitted_by", "submitted_by__profile")
    }

    moa_docs_by_proposal = {}
    for doc in (
        ProposalFinalDocument.objects.filter(
            proposal_id__in=moa_proposal_ids,
            document_type=ProposalFinalDocument.DocumentType.MOA,
        )
        .select_related("uploaded_by", "uploaded_by__profile")
        .order_by("proposal_id", "-is_current", "-version", "-uploaded_at")
    ):
        moa_docs_by_proposal.setdefault(doc.proposal_id, doc)

    moa_status_action_labels = {
        Proposal.MOAStatus.NOT_STARTED: "Open tracker / initialize draft",
        Proposal.MOAStatus.DRAFT: "Prepare for Legal Review",
        Proposal.MOAStatus.LEGAL_REVIEW: "Record Legal Review outcome",
        Proposal.MOAStatus.FOR_REVISION: "Waiting for proponent revision",
        Proposal.MOAStatus.CERTIFICATION_READY: "Prepare Agenda Brief",
        Proposal.MOAStatus.AGENDA_AND_PRESENTATION: "Mark completed after signing",
    }

    def _safe_file_url(file_field):
        """Return a file's URL, or "" when the backing file is unavailable."""
        if not file_field:
            return ""
        try:
            return file_field.url
        except (ValueError, FileNotFoundError):
            # No file associated, or it is missing from storage.
            return ""
        except Exception:
            logger.exception("Could not resolve URL for %r.", file_field)
            return ""

    moa_queue = []
    for proposal in moa_proposals:
        submission = submissions_by_proposal.get(proposal.id)
        moa_doc = moa_docs_by_proposal.get(proposal.id)

        has_guided_draft_file = bool(getattr(proposal, "moa_draft_file", None))
        if not submission and not moa_doc and not has_guided_draft_file:
            continue

        draft_data = proposal.moa_draft_data or {}
        partner_name = (
            getattr(submission, "partner_agency_name", "")
            or draft_data.get("partner_name")
            or proposal.implementing_agency
            or "MOA draft"
        )

        uploaded_at = (
            getattr(submission, "updated_at", None)
            or getattr(moa_doc, "uploaded_at", None)
            or proposal.last_saved_at
        )

        file_url = (
            _safe_file_url(getattr(submission, "moa_file", None))
            or _safe_file_url(getattr(moa_doc, "file", None))
            or _safe_file_url(getattr(proposal, "moa_draft_file", None))
        )

        moa_queue.append({
            "proposal": proposal,
            "partner_name": partner_name,
            "uploaded_at": uploaded_at,
            "file_url": file_url,
            "source_label": (
                "Uploaded MOA form"
                if submission
                else "Generated/uploaded MOA document"
                if moa_doc
                else "Guided MOA draft upload"
            ),
            "next_action_label": moa_status_action_labels.get(
                proposal.moa_status,
                "Open MOA Tracker",
            ),
        })

    moa_queue.sort(
        key=lambda item: item.get("uploaded_at") or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()),
        reverse=True,
    )

    moa_active_count = len(moa_queue)
    moa_draft_count = sum(
        1 for item in moa_queue
        if item["proposal"].moa_status in {
            Proposal.MOAStatus.NOT_STARTED,
            Proposal.MOAStatus.DRAFT,
        }
    )

    context = {
        "profile": profile,
        "nav_notif_count": (pending_count + draft_count + signed_pending_count + moa_active_count),
        "summary_queue": summary_queue,
        "pending_count": pending_count,
        "draft_count": draft_count,
        "signed_queue": signed_queue,
        "signed_pending_count": signed_pending_count,
        "moa_queue": moa_queue,
        "moa_active_count": moa_active_count,
        "moa_draft_count": moa_draft_count,
    }
    return render(request, "dashboard/staff_dashboard.html", context)


@login_required
@role_required(["DEPARTMENT_COORDINATOR"])
def department_coordinator_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    review_queue = _get_department_review_queue(request.user)
    action_queue_count = review_queue.count()

    proposals_ctx = _get_user_proposals_context(request.user)

    pending_review = Proposal.objects.filter(
        institution=get_user_institution(request.user),
        proposal_status=Proposal.ProposalStatus.IN_REVIEW,
        review_level=Proposal.ReviewLevel.DEPARTMENT,
        # Only proposals the coordinator's campus/dept can see
    ).count()

    context = {
        "profile": profile,
        "nav_notif_count": (proposals_ctx.get("needs_attention_count", 0) + action_queue_count),
        **proposals_ctx,
        "review_queue": review_queue,
        "review_queue_count": review_queue.count(),
        "action_queue_count": action_queue_count,
        "pending_review_count": pending_review,
    }
    return render(request, "dashboard/department_coordinator_dashboard.html", context)


@login_required
@role_required(["CAMPUS_COORDINATOR"])
def campus_coordinator_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    review_queue = _get_campus_review_queue(request.user)
    action_queue_count = review_queue.count()

    proposals_ctx = _get_user_proposals_context(request.user)

    pending_review = Proposal.objects.filter(
        institution=get_user_institution(request.user),
        proposal_status=Proposal.ProposalStatus.IN_REVIEW,
        review_level=Proposal.ReviewLevel.CAMPUS,
        # Only proposals the coordinator's campus/dept can see
    ).count()

    context = {
        "profile": profile,
        "nav_notif_count": (proposals_ctx.get("needs_attention_count", 0) + action_queue_count),
        **proposals_ctx,
        "review_queue": review_queue,
        "review_queue_count": review_queue.count(),
        "action_queue_count": action_queue_count,
        "pending_review_count": pending_review,
    }
    return render(request, "dashboard/campus_coordinator_dashboard.html", context)


@login_required
@admin_required
def admin_dashboard(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    institution = None if request.user.is_superuser else get_user_institution(request.user)

    profiles_qs = Profile.objects.select_related("user", "institution")
    if institution is not None:
        profiles_qs = profiles_qs.filter(institution=institution)

    users_qs = User.objects.filter(profile__in=profiles_qs)

    def content_count(model, **filters):
        qs = model.objects.filter(**filters) if filters else model.objects.all()
        if institution is not None and hasattr(model, "institution"):
            qs = qs.filter(institution=institution)
        return qs.count()

    profiles = profiles_qs.order_by("-user__date_joined")

    site_control = SiteConfiguration.get_solo()
    site_logs = SiteConfigurationLog.objects.select_related("changed_by", "changed_by__profile")[:5]

    context = {
        "profiles": profiles,
        "current_institution": institution,
        "site_control": site_control,
        "site_logs": site_logs,
        "nav_notif_count": profiles_qs.filter(email_verified=False).count(),
        "total_users": users_qs.count(),
        "verified_users": profiles_qs.filter(email_verified=True).count(),
        "unverified_users": profiles_qs.filter(email_verified=False).count(),
        "active_today": users_qs.filter(last_login__gte=today_start).count(),
        "faculty_count": profiles_qs.filter(role=Profile.ROLE_FACULTY).count(),
        "evaluator_count": profiles_qs.filter(role=Profile.ROLE_EVALUATOR).count(),
        "department_coordinator_count": profiles_qs.filter(role=Profile.ROLE_DEPARTMENT_COORDINATOR).count(),
        "campus_coordinator_count": profiles_qs.filter(role=Profile.ROLE_CAMPUS_COORDINATOR).count(),
        "director_count": profiles_qs.filter(role=Profile.ROLE_DIRECTOR).count(),
        "staff_count": profiles_qs.filter(role=Profile.ROLE_STAFF).count(),
        "admin_count": profiles_qs.filter(role=Profile.ROLE_ADMIN).count(),
        "personnel_count": content_count(Personnel),
        "activities_count": content_count(Activity),
        "processes_count": content_count(ExtensionProcess),
        "targets_count": content_count(Target),
        "signatories_count": content_count(Signatory),
        "document_template_count": content_count(DocumentTemplate),
        "dynamic_form_count": content_count(DynamicFormTemplate),
        "wizard_step_config_count": content_count(ProposalWizardStepConfig),
        "role_capability_count": content_count(RoleCapability, enabled=True),
        "total_content": (
            content_count(Personnel)
            + content_count(Activity)
            + content_count(ExtensionProcess)
            + content_count(Target)
            + content_count(Signatory)
            + content_count(DocumentTemplate)
            + content_count(DynamicFormTemplate)
            + content_count(ProposalWizardStepConfig)
        ),
        "recent_users": profiles_qs.filter(user__date_joined__gte=week_ago).order_by("-user__date_joined")[:5],
        "editable_pages": [
            {
                "slug": page.slug,
                "title": page.title,
                "is_published": page.is_published,
                "visible_count": page.sections.filter(is_visible=True).count(),
            }
            for page in (SitePage.get_for(slug, institution=institution) for slug, _ in SitePage.Slug.choices)
        ],
    }
    return render(request, "dashboard/admin_dashboard.html", context)



@login_required
@faculty_like_required
@require_POST
def faculty_delete_draft(request, proposal_id):
    draft = Proposal.objects.filter(
        institution=get_user_institution(request.user),
        id=proposal_id,
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).first()

    if not draft:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "Draft not found."},
                status=404,
            )
        messages.error(request, "Draft not found.")
        return redirect("dashboard_redirect")

    if draft.created_by != request.user:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "Only the creator can delete this draft."},
                status=403,
            )
        messages.error(request, "Only the creator can delete this draft.")
        return redirect("dashboard_redirect")

    title = draft.title or draft.research_title or "Untitled Draft"
    draft.delete()

    remaining_drafts = Proposal.objects.filter(
        Q(created_by=request.user)
        | Q(proponents__user=request.user)
        | Q(collaborators__user=request.user),
        institution=get_user_institution(request.user),
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).distinct().count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "message": f'"{title}" draft deleted successfully.',
            "proposal_id": str(proposal_id),
            "draft_count": remaining_drafts,
        })

    messages.success(request, f'"{title}" draft deleted successfully.')
    return redirect("dashboard_redirect")
