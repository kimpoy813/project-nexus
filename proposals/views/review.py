"""
Review rounds, evaluator actions, and comment summary generation.
"""
import logging
from docx import Document
from accounts.models import Signatory

from collections import OrderedDict
from docx.shared import Mm
from docx.shared import Pt
from io import BytesIO
from pathlib import Path
from xhtml2pdf import pisa
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Proposal
from ..models import ProposalCommentSummary
from ..models import ProposalEvaluatorAssignment
from ..models import ProposalSectionComment
from accounts.decorators import role_required
from details.models import WizardFlow
from .constants import step_labels_for_flow, User
from .helpers import _extract_last_name, _extract_points, _get_signatory, _insert_paragraph_after, _proponent_line
from .permissions import _can_view_proposal, _can_view_summary, _ensure_open_review_round, _is_campus_coordinator, _is_department_coordinator, _is_director, _is_staff

logger = logging.getLogger(__name__)


@login_required
@require_POST
def proposal_return_for_revision(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_director(request.user):
        messages.error(request, "Only the Director can return this proposal for revision.")
        return redirect("dashboard_redirect")

    proposal.return_for_revision()

    messages.success(request, "Proposal returned for revision.")
    return redirect("dashboard_redirect")


@login_required
@require_POST
def proposal_approve(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_director(request.user):
        messages.error(request, "Only the Director can approve proposals.")
        return redirect("dashboard_redirect")

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if current_round and not current_round.is_closed:
        current_round.is_closed = True
        current_round.save(update_fields=["is_closed"])

        ProposalEvaluatorAssignment.objects.filter(
            proposal=proposal,
            review_round=current_round,
            is_active=True,
        ).update(is_active=False)

    # Director approval here means: cleared for printing (not final approval yet)
    proposal.mark_ready_for_printing()

    messages.success(request, "Proposal cleared for printing.")
    return redirect("dashboard_redirect")


@login_required
def proposal_review_comments(request, proposal_id, step=1):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not (
        _can_view_proposal(request.user, proposal)
        or request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    ):
        messages.error(request, "You don't have access to this proposal.")
        return redirect("dashboard_redirect")

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not current_round:
        messages.warning(request, "No review comments are available yet.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=1)

    step_comments = (
        ProposalSectionComment.objects
        .filter(
            proposal=proposal,
            review_round=current_round,
        )
        .select_related("reviewer", "reviewer__profile", "review_round")
        .order_by("step_no", "created_at")
    )

    flow_labels = step_labels_for_flow(
        WizardFlow.flow_for_extension_type(proposal.extension_type) or "ALL"
    )

    grouped_comments = OrderedDict()
    for item in step_comments:
        step_no = item.step_no or 1
        if step_no not in grouped_comments:
            step_meta = next((s for s in flow_labels if s["no"] == step_no), None)
            grouped_comments[step_no] = {
                "step_no": step_no,
                "step_title": step_meta["title"] if step_meta else f"Step {step_no}",
                "step_desc": step_meta["desc"] if step_meta else "",
                "comments": [],
            }
        grouped_comments[step_no]["comments"].append(item)

    summary = ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=current_round,
        sent_to_proponent=True
    ).first()

    context = {
        "proposal": proposal,
        "review_round": current_round,
        "grouped_comments": grouped_comments,
        "current_step": int(step or 1),
        "summary": summary,
    }
    return render(request, "services/review/proposal_review_summary.html", context)


def _serialize_user_for_eval(user):
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": getattr(user, "username", ""),
        "name": getattr(profile, "full_name", None) or getattr(user, "username", ""),
        "profile": {
            "full_name": getattr(profile, "full_name", None),
        },
    }


@login_required
@require_POST
def proposal_assign_evaluator(request, proposal_id, evaluator_id=None):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_director(request.user):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Only the Director can assign evaluators."}, status=403)
        messages.error(request, "Only the Director can assign evaluators.")
        return redirect("dashboard_redirect")

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not current_round:
        current_round = proposal.start_review_round()

    selected_evaluator_id = evaluator_id if evaluator_id is not None else (request.POST.get("evaluator_id") or "").strip()
    if not str(selected_evaluator_id).isdigit():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Invalid evaluator selected."}, status=400)
        messages.error(request, "Invalid evaluator selected.")
        return redirect("dashboard_redirect")

    evaluator = User.objects.filter(id=int(selected_evaluator_id)).select_related("profile").first()
    if not evaluator:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Selected faculty member was not found."}, status=404)
        messages.error(request, "Selected faculty member was not found.")
        return redirect("dashboard_redirect")

    evaluator_profile = getattr(evaluator, "profile", None)
    allowed_roles = {"FACULTY", "EVALUATOR", "DEPARTMENT_COORDINATOR", "CAMPUS_COORDINATOR"}

    if not evaluator_profile or evaluator_profile.role not in allowed_roles:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Selected user is not eligible to be assigned as evaluator."}, status=400)
        messages.error(request, "Selected user is not eligible to be assigned as evaluator.")
        return redirect("dashboard_redirect")

    if proposal.proponents.filter(user=evaluator).exists():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "A proponent of the proposal cannot be assigned as evaluator."}, status=400)
        messages.error(request, "A proponent of the proposal cannot be assigned as evaluator.")
        return redirect("dashboard_redirect")

    assignment, created = ProposalEvaluatorAssignment.objects.get_or_create(
        proposal=proposal,
        review_round=current_round,
        evaluator=evaluator,
        defaults={
            "assigned_by": request.user,
            "is_active": True,
            "is_completed": False,
        },
    )

    if not created:
        assignment.is_active = True
        assignment.is_completed = False
        assignment.assigned_by = request.user
        assignment.save(update_fields=["is_active", "is_completed", "assigned_by"])

    current_round.evaluator_review_required = True
    current_round.evaluator_review_done = False
    current_round.ready_for_staff_summary = False
    current_round.save(update_fields=["evaluator_review_required", "evaluator_review_done", "ready_for_staff_summary"])

    proposal.mark_in_review(review_level=Proposal.ReviewLevel.DIRECTOR)

    assigned_qs = ProposalEvaluatorAssignment.objects.filter(proposal=proposal, review_round=current_round, is_active=True).select_related("evaluator", "evaluator__profile")
    available_qs = User.objects.filter(profile__role__in=["FACULTY", "EVALUATOR", "DEPARTMENT_COORDINATOR", "CAMPUS_COORDINATOR"]).exclude(id__in=assigned_qs.values_list("evaluator_id", flat=True)).exclude(id__in=proposal.proponents.values_list("user_id", flat=True)).select_related("profile").order_by("profile__full_name", "username")

    response = {
        "ok": True,
        "message": f"{getattr(evaluator_profile, 'full_name', evaluator.username)} has been assigned as evaluator.",
        "assigned_evaluators": [_serialize_user_for_eval(item.evaluator) for item in assigned_qs],
        "available_evaluators": [_serialize_user_for_eval(item) for item in available_qs],
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(response)

    messages.success(request, response["message"])
    return redirect("dashboard_redirect")


@login_required
@require_POST
def proposal_remove_evaluator(request, proposal_id, evaluator_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_director(request.user):
        return JsonResponse({"ok": False, "message": "Only the Director can remove evaluators."}, status=403)

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not current_round:
        return JsonResponse({"ok": False, "message": "No active review round found."}, status=404)

    assignment = ProposalEvaluatorAssignment.objects.filter(
        proposal=proposal,
        review_round=current_round,
        evaluator_id=evaluator_id,
        is_active=True,
    ).first()

    if assignment:
        assignment.is_active = False
        assignment.is_completed = False
        assignment.save(update_fields=["is_active", "is_completed"])

    active_assignments = ProposalEvaluatorAssignment.objects.filter(proposal=proposal, review_round=current_round, is_active=True)
    current_round.evaluator_review_required = active_assignments.exists()
    current_round.evaluator_review_done = current_round.evaluator_review_required and not active_assignments.filter(is_completed=False).exists()
    current_round.ready_for_staff_summary = False
    current_round.save(update_fields=["evaluator_review_required", "evaluator_review_done", "ready_for_staff_summary"])

    assigned_qs = ProposalEvaluatorAssignment.objects.filter(proposal=proposal, review_round=current_round, is_active=True).select_related("evaluator", "evaluator__profile")
    available_qs = User.objects.filter(profile__role__in=["FACULTY", "EVALUATOR", "DEPARTMENT_COORDINATOR", "CAMPUS_COORDINATOR"]).exclude(id__in=assigned_qs.values_list("evaluator_id", flat=True)).exclude(id__in=proposal.proponents.values_list("user_id", flat=True)).select_related("profile").order_by("profile__full_name", "username")

    return JsonResponse({
        "ok": True,
        "assigned_evaluators": [_serialize_user_for_eval(item.evaluator) for item in assigned_qs],
        "available_evaluators": [_serialize_user_for_eval(item) for item in available_qs],
    })


@login_required
@require_POST
def proposal_complete_evaluation(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not current_round:
        messages.error(request, "No active review round found.")
        return redirect("dashboard_redirect")

    assignment = ProposalEvaluatorAssignment.objects.filter(
        proposal=proposal,
        review_round=current_round,
        evaluator=request.user,
        is_active=True,
    ).first()

    if not assignment:
        messages.error(request, "You are not assigned to evaluate this proposal.")
        return redirect("dashboard_redirect")

    has_comment = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=current_round,
        reviewer=request.user,
        reviewer_role="EVALUATOR",
    ).exists()

    if not has_comment:
        messages.error(request, "Please add at least one evaluator comment before completing the evaluation.")
        return redirect("dashboard_redirect")

    assignment.is_completed = True
    assignment.save(update_fields=["is_completed"])

    current_round.refresh_evaluator_review_done()

    messages.success(request, "Evaluation marked as completed.")
    return redirect("dashboard_redirect")


@login_required
@require_POST
def proposal_mark_ready_for_summary(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_director(request.user):
        messages.error(request, "Only the Director can mark a proposal ready for summary.")
        return redirect("dashboard_redirect")

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    # Ensure we operate on an OPEN round
    if not current_round or getattr(current_round, "is_closed", False):
        current_round = _ensure_open_review_round(proposal, request.user)
    if not current_round:
        messages.error(request, "No active review round found.")
        return redirect("dashboard_redirect")

    # Guard: don't re-queue a round that already has a SENT summary
    if ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=current_round,
        sent_to_proponent=True,
    ).exists():
        messages.error(request, "A summary has already been issued for the current review round.")
        return redirect("dashboard_redirect")

    director_has_comment = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=current_round,
        reviewer=request.user,
        reviewer_role="DIRECTOR",
    ).exists()

    if not director_has_comment:
        messages.error(request, "Please add at least one director comment before finishing the review round.")
        return redirect("dashboard_redirect")

    current_round.director_review_done = True
    current_round.save(update_fields=["director_review_done"])

    if current_round.evaluator_review_required:
        current_round.refresh_evaluator_review_done()

    try:
        current_round.mark_ready_for_staff_summary()
    except ValidationError as e:
        messages.error(request, e.messages[0])
        return redirect("dashboard_redirect")

    proposal.mark_in_review(review_level=Proposal.ReviewLevel.DIRECTOR)
    proposal.proposal_status = Proposal.ProposalStatus.IN_REVIEW
    proposal.save(update_fields=["proposal_status"])

    messages.success(request, "Proposal marked ready for staff summary.")
    return redirect("dashboard_redirect")


@login_required
@require_POST
def proposal_mark_department_review_done(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_department_coordinator(request.user):
        messages.error(request, "Only the Department Coordinator can mark department review done.")
        return redirect("dashboard_redirect")

    user_department = (getattr(request.user.profile, "department", "") or "").strip()
    proposal_department = (proposal.department or "").strip()

    if user_department != proposal_department:
        messages.error(request, "You can only mark review done for proposals in your department.")
        return redirect("dashboard_redirect")

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not current_round:
        messages.error(request, "No active review round found.")
        return redirect("dashboard_redirect")

    current_round.department_review_done = True
    current_round.save(update_fields=["department_review_done"])

    proposal.mark_in_review(review_level=Proposal.ReviewLevel.DEPARTMENT)

    messages.success(request, "Department review marked as done.")
    return redirect("dashboard_redirect")


@login_required
@require_POST
def proposal_mark_campus_review_done(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _is_campus_coordinator(request.user):
        messages.error(request, "Only the Campus Coordinator can mark campus review done.")
        return redirect("dashboard_redirect")

    user_campus = (getattr(request.user.profile, "campus", "") or "").strip()
    proposal_campus = (proposal.campus or "").strip()

    if user_campus != proposal_campus:
        messages.error(request, "You can only mark review done for proposals in your campus.")
        return redirect("dashboard_redirect")

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not current_round:
        messages.error(request, "No active review round found.")
        return redirect("dashboard_redirect")

    current_round.campus_review_done = True
    current_round.save(update_fields=["campus_review_done"])

    proposal.mark_in_review(review_level=Proposal.ReviewLevel.CAMPUS)

    messages.success(request, "Campus review marked as done.")
    return redirect("dashboard_redirect")


def _get_review_round_for_staff_summary(proposal):
    """
    Return the review round that STAFF should work on.

    Priority:
    1) Latest OPEN round that is already marked ready_for_staff_summary
    2) Latest OPEN round
    3) Latest round (fallback)
    """
    qs = proposal.review_rounds.order_by("-round_no")
    ready_open = qs.filter(is_closed=False, ready_for_staff_summary=True).first()
    if ready_open:
        return ready_open
    open_round = qs.filter(is_closed=False).first()
    if open_round:
        return open_round
    return qs.first()


def _get_latest_sent_summary(proposal):
    return (
        proposal.comment_summaries
        .filter(sent_to_proponent=True)
        .select_related("review_round")
        .order_by("-review_round__round_no", "-created_at")
        .first()
    )


def _get_director_name(proposal, review_round):
    director_comment = (
        ProposalSectionComment.objects.filter(
            proposal=proposal,
            review_round=review_round,
            reviewer_role="DIRECTOR",
        )
        .select_related("reviewer__profile")
        .order_by("-created_at")
        .first()
    )

    if not director_comment:
        return "Director"

    profile = getattr(director_comment.reviewer, "profile", None)
    return (getattr(profile, "full_name", "") or director_comment.reviewer.username or "Director")


def summarize_comments(comments_queryset, *, include_step_labels=True, proposal=None):
    """
    Convert raw reviewer comments into concrete "key revision points".

    Goals:
    - Use the *actual* comment text (not generic placeholders).
    - Group by step and extract 1–2 actionable points per step.
    - Keep output short and readable for the Summary letter.
    """
    flow = WizardFlow.flow_for_extension_type(proposal.extension_type) if proposal else None
    flow_labels = step_labels_for_flow(flow or "ALL")
    step_title_map = {s.get("no"): s.get("title") for s in flow_labels if isinstance(s, dict)}

    ACTION_WORDS = (
        "should", "must", "please", "kindly", "revise", "update", "add", "include",
        "clarify", "ensure", "provide", "remove", "align", "correct", "complete",
        "justify", "specify", "strengthen", "reword", "edit", "format",
    )

    def _normalize_ws(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _extract_keypoints(text: str, max_points: int = 2):
        """
        Pull the most actionable sentence/bullet(s) from a comment.
        """
        t = (text or "").strip()
        if not t:
            return []

        # Prefer explicit bullets when present.
        lines = [ln.strip(" \t\r") for ln in (text or "").splitlines() if ln.strip()]
        bullet_like = []
        for ln in lines:
            if re.match(r"^(\-|\*|•|\u2022|\d+[\.\)]|[a-zA-Z][\.\)])\s+", ln):
                ln = re.sub(r"^(\-|\*|•|\u2022|\d+[\.\)]|[a-zA-Z][\.\)])\s+", "", ln).strip()
                if ln:
                    bullet_like.append(_normalize_ws(ln))

        if bullet_like:
            out = []
            seen = set()
            for b in bullet_like:
                key = b.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(b)
                if len(out) >= max_points:
                    break
            return out

        # Otherwise, score sentences/clauses.
        compact = _normalize_ws(t)
        parts = re.split(r"(?<=[\.\?\!;:])\s+|\s+\-\s+|\s+\u2022\s+", compact)
        parts = [_normalize_ws(p) for p in parts if _normalize_ws(p)]
        if not parts:
            return []

        def score(p: str) -> float:
            lp = p.lower()
            hits = sum(1 for w in ACTION_WORDS if w in lp)
            # bias toward informative-but-not-too-long clauses
            length = len(p)
            length_score = min(length, 220) / 60.0
            return (hits * 3.0) + length_score

        ranked = sorted(parts, key=score, reverse=True)

        out = []
        seen = set()
        for p in ranked:
            if len(p) < 12:
                continue
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
            if len(out) >= max_points:
                break

        if not out and compact:
            out = [compact[:220].rstrip() + ("..." if len(compact) > 220 else "")]

        return out

    # Build (step_no -> [points...]) preserving step order later.
    grouped = {}
    global_seen = set()

    for c in comments_queryset:
        raw = (getattr(c, "comment", "") or "").strip()
        if not raw:
            continue

        step_no = int(getattr(c, "step_no", 0) or 0)

        for kp in _extract_keypoints(raw, max_points=2):
            kp = _normalize_ws(kp)
            if not kp:
                continue
            dedupe_key = (step_no, kp.lower())
            if dedupe_key in global_seen:
                continue
            global_seen.add(dedupe_key)
            grouped.setdefault(step_no, []).append(kp)

    if not grouped:
        return ["No significant comments were provided by reviewers."]

    bullets = []

    # Sort steps numerically; keep step_no==0 ("General") last.
    for step_no in sorted(grouped.keys(), key=lambda n: (n == 0, n)):
        points = grouped.get(step_no) or []
        if not points:
            continue

        title = step_title_map.get(step_no) if step_no else "General"
        joined = "; ".join(points[:2]).strip()

        if len(joined) > 220:
            joined = joined[:217].rstrip() + "..."

        if step_no and include_step_labels:
            bullets.append(f"Step {step_no} – {title}: {joined}")
        else:
            bullets.append(joined)

        if len(bullets) >= 8:
            break

    # Safety net: if bullets are still too few, add a tiny keyword-based hint (non-generic).
    if len(bullets) < 2:
        bullets.append("Please review each step and apply all reviewer notes before resubmission.")

    return bullets


def _generate_default_summary_text(proposal, review_round, director_name):
    """
    Default for STAFF textarea:
    - ONLY the consolidated comment points
    - NO greeting letter
    - NO 'Step X - ...' labels
    This keeps summary_text compatible with Clear Summary Preview/DOCX (points list).
    """
    comments_qs = (
        ProposalSectionComment.objects
        .filter(proposal=proposal, review_round=review_round)
        .order_by("step_no", "created_at")
    )

    points = summarize_comments(comments_qs, include_step_labels=False)
    # Keep as bullet lines; preview/docx will number them cleanly.
    return "\n".join([f"- {p}" for p in points])


def _finalize_summary_and_return_for_revision(proposal, review_round):
    # Deactivate evaluator assignments for this round
    ProposalEvaluatorAssignment.objects.filter(
        proposal=proposal,
        review_round=review_round,
        is_active=True,
    ).update(is_active=False)

    # Clear staff-ready flag (a round with a SENT summary should never remain in the staff queue)
    update_fields = []
    if hasattr(review_round, "ready_for_staff_summary") and review_round.ready_for_staff_summary:
        review_round.ready_for_staff_summary = False
        update_fields.append("ready_for_staff_summary")

    # Close round
    if not getattr(review_round, "is_closed", False):
        review_round.is_closed = True
        update_fields.append("is_closed")

    if update_fields:
        review_round.save(update_fields=update_fields)

    # Return proposal for revision (unlocks)
    proposal.return_for_revision()


@login_required
@role_required(["STAFF"])
def proposal_comment_summary(request, proposal_id):
    """
    STAFF drafts (and optionally sends) the official summary for a review round
    that has been marked ready_for_staff_summary by the Director.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)
    review_round = _get_review_round_for_staff_summary(proposal)

    if not review_round or not review_round.ready_for_staff_summary:
        messages.error(request, "This review round is not yet ready for staff summary.")
        return redirect("staff_dashboard")

    step_comments = (
        ProposalSectionComment.objects.filter(proposal=proposal, review_round=review_round)
        .select_related("reviewer", "reviewer__profile", "review_round")
        .order_by("step_no", "created_at")
    )

    summary = ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=review_round,
    ).first()

    director_name = _get_director_name(proposal, review_round)

    if request.method == "POST":
        summary_text = (request.POST.get("summary_text") or "").strip()

        # Primary driver: action buttons
        action = (request.POST.get("action") or "").strip() or "save_draft"

        # Optional: support a POST-based DOCX download if you wire the button as a submit
        if action == "download_docx":
            effective_text = summary_text or _generate_default_summary_text(proposal, review_round, director_name)
            points = _extract_points(effective_text) or ["No significant comments were provided by reviewers."]

            data = _build_clear_summary_docx(proposal=proposal, points=points)
            filename = f"Comment_Summary_{proposal.title}.docx"
            resp = HttpResponse(
                data,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            resp["Content-Disposition"] = f'attachment; filename="{filename}"'
            return resp

        if action == "send_to_proponent":
            if not summary_text:
                messages.error(request, "Summary text cannot be empty.")
                return redirect("proposal_comment_summary", proposal_id=proposal.id)

            if not summary:
                summary = ProposalCommentSummary.objects.create(
                    proposal=proposal,
                    review_round=review_round,
                    prepared_by=request.user,
                    summary_text=summary_text,
                    sent_to_proponent=True,
                )
            else:
                summary.summary_text = summary_text
                summary.sent_to_proponent = True
                if not summary.prepared_by_id:
                    summary.prepared_by = request.user
                summary.save(update_fields=["summary_text", "sent_to_proponent", "prepared_by"])

            _finalize_summary_and_return_for_revision(proposal, review_round)
            messages.success(request, f"Summary for '{proposal.display_title}' sent to proponent.")
            return redirect("staff_dashboard")

        # save_draft (default)
        if not summary_text:
            summary_text = _generate_default_summary_text(proposal, review_round, director_name)

        if not summary:
            summary = ProposalCommentSummary.objects.create(
                proposal=proposal,
                review_round=review_round,
                prepared_by=request.user,
                summary_text=summary_text,
                sent_to_proponent=False,
            )
        else:
            summary.summary_text = summary_text
            if not summary.prepared_by_id:
                summary.prepared_by = request.user
            # don't flip a sent summary back to draft silently
            if not summary.sent_to_proponent:
                summary.sent_to_proponent = False
            summary.save(update_fields=["summary_text", "prepared_by", "sent_to_proponent"])

        messages.success(request, "Summary saved.")
        return redirect("proposal_comment_summary", proposal_id=proposal.id)

    default_text = ((summary.summary_text or "").strip() if summary else "") or _generate_default_summary_text(
        proposal, review_round, director_name
    )

    context = {
        "proposal": proposal,
        "review_round": review_round,
        "step_comments": step_comments,
        "summary_text": default_text,
        "is_draft": (summary is None) or (not summary.sent_to_proponent),
        "summary": summary,
        "director_name": director_name,
    }
    return render(request, "services/review/proposal_comment_summary.html", context)


def proposal_send_summary(request, proposal_id):
    """
    Convenience endpoint: send an already-prepared DRAFT summary to the proponent.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)
    review_round = _get_review_round_for_staff_summary(proposal)

    if not review_round or not review_round.ready_for_staff_summary:
        messages.error(request, "This review round is not yet ready for staff summary.")
        return redirect("staff_dashboard")

    summary = ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=review_round,
        sent_to_proponent=False,
    ).first()

    if not summary:
        messages.error(request, "No draft summary found. Please prepare one first.")
        return redirect("proposal_comment_summary", proposal_id=proposal.id)

    summary.sent_to_proponent = True
    summary.save(update_fields=["sent_to_proponent"])

    _finalize_summary_and_return_for_revision(proposal, review_round)

    messages.success(request, f"Summary for '{proposal.display_title}' sent to proponent.")
    return redirect("staff_dashboard")


@login_required
def proposal_version_summary(request, proposal_id, round_no):
    """Open a specific proposal version in the existing readonly proposal view."""
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_summary(request.user, proposal):
        messages.error(request, "You do not have permission to view this proposal version.")
        return redirect("dashboard_redirect")

    if not proposal.review_rounds.filter(round_no=round_no).exists():
        messages.error(request, "That review version does not exist.")
        return redirect("proposal_storage", proposal_id=proposal.id)

    return redirect(f"{reverse('proposal_wizard', args=[proposal.id, 1])}?readonly=1")


@login_required
def proposal_view_summary(request, proposal_id):
    """Proponent view to read the latest issued summary and visible comments."""
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_summary(request.user, proposal):
        messages.error(request, "You do not have permission to view this summary.")
        return redirect("dashboard_redirect")

    summary = _get_latest_sent_summary(proposal)
    if not summary:
        messages.error(request, "No summary has been issued yet.")
        return redirect("dashboard_redirect")

    review_round = summary.review_round

    comments_qs = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=review_round,
    ).select_related("reviewer__profile").order_by("step_no", "created_at")

    if not _is_staff(request.user):
        comments_qs = comments_qs.filter(is_visible_to_proponent=True)

    context = {
        "proposal": proposal,
        "summary": summary,
        "comments": comments_qs,
        "review_round": review_round,
        "director_name": _get_director_name(proposal, review_round),
    }
    return render(request, "proposals/view_summary.html", context)


@login_required
def proposal_print_summary_page(request, proposal_id):
    """HTML print-friendly summary view (staff/proponent)."""
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_summary(request.user, proposal):
        messages.error(request, "You do not have permission to view this summary.")
        return redirect("dashboard_redirect")

    # Prefer latest sent summary; STAFF can still print the current draft.
    summary = _get_latest_sent_summary(proposal)
    if not summary and _is_staff(request.user):
        review_round = _get_review_round_for_staff_summary(proposal)
        summary = ProposalCommentSummary.objects.filter(
            proposal=proposal, review_round=review_round
        ).order_by("-created_at").first()
    else:
        review_round = summary.review_round if summary else None

    if not summary or not review_round:
        messages.error(request, "No summary available for printing.")
        return redirect("dashboard_redirect")

    comments_qs = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=review_round,
    ).select_related("reviewer__profile").order_by("step_no", "created_at")

    if not _is_staff(request.user):
        comments_qs = comments_qs.filter(is_visible_to_proponent=True)

    context = {
        "proposal": proposal,
        "summary": summary,
        "comments": comments_qs,
        "director_name": _get_director_name(proposal, review_round),
        "review_round": review_round,
    }
    return render(request, "proposals/print_summary.html", context)


@login_required
def proposal_print_summary(request, proposal_id):
    """Generate PDF summary using xhtml2pdf."""
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_summary(request.user, proposal):
        messages.error(request, "You do not have permission to view this summary.")
        return redirect("dashboard_redirect")

    # Prefer latest sent summary; STAFF can still export the current draft.
    summary = _get_latest_sent_summary(proposal)
    if not summary and _is_staff(request.user):
        review_round = _get_review_round_for_staff_summary(proposal)
        summary = ProposalCommentSummary.objects.filter(
            proposal=proposal, review_round=review_round
        ).order_by("-created_at").first()
    else:
        review_round = summary.review_round if summary else None

    if not summary or not review_round:
        messages.error(request, "No summary available.")
        return redirect("dashboard_redirect")

    comments_qs = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=review_round,
    ).select_related("reviewer__profile").order_by("step_no", "created_at")

    if not _is_staff(request.user):
        comments_qs = comments_qs.filter(is_visible_to_proponent=True)

    html_string = render_to_string(
        "proposals/summary_pdf.html",
        {
            "proposal": proposal,
            "summary": summary,
            "comments": comments_qs,
            "director_name": _get_director_name(proposal, review_round),
            "review_round": review_round,
        },
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="summary_{proposal.id}.pdf"'

    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)

    return response


def _build_clear_summary_docx(*, proposal: Proposal, points):
    template_path = Path(__file__).resolve().parent / "template_files" / "clear_summary_template.docx"
    doc = Document(str(template_path))
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)

    title = proposal.title or proposal.research_title or "Untitled Proposal"
    campus = (proposal.campus or "").strip()

    campus_director = _get_signatory(Signatory.Position.CAMPUS_DIRECTOR, campus=campus) if campus else None
    campus_coordinator = _get_signatory(Signatory.Position.CAMPUS_EXTENSION_COORDINATOR, campus=campus) if campus else None
    director_ext = _get_signatory(Signatory.Position.DIRECTOR_EXTENSION)

    # Full names (for last name extraction)
    cd_full = (campus_director.full_name if campus_director else "").strip() or "[NAME OF THE CAMPUS DIRECTOR]"
    cc_full = (campus_coordinator.full_name if campus_coordinator else "").strip() or "[NAME OF CAMPUS COORDINATOR]"

    # Display names (include credentials)
    cd_cred = (campus_director.credentials if campus_director else "").strip()
    cc_cred = (campus_coordinator.credentials if campus_coordinator else "").strip()
    cd_display = cd_full + (f", {cd_cred}" if cd_cred else "")
    cc_display = cc_full + (f", {cc_cred}" if cc_cred else "")

    director_name = (director_ext.full_name if director_ext else "").strip() or "[NAME OF THE DIRECTOR]"
    director_cred = (director_ext.credentials if director_ext else "").strip()
    proponent_line = _proponent_line(proposal)
    date_str = timezone.localdate().strftime("%B %d, %Y")

    # Placeholder → value
    repl = {
        "[TITLE]": title,
        "[Date]": date_str,
        "[Campus]": campus or "[Campus]",
        "[NAME OF THE CAMPUS DIRECTOR]": cd_display,
        "[NAME OF CAMPUS COORDINATOR]": cc_display,
        "[NAME OF PROPONENT]": proponent_line,
        "[LAST NAME OF THE CAMPUS DIRECTOR]": _extract_last_name(cd_full) or "[LAST NAME OF THE CAMPUS DIRECTOR]",
        "[NAME OF THE DIRECTOR]": director_name,
        "[Credentials]": director_cred,
    }

    def replace_in_paragraph_runs(paragraph):
        for run in paragraph.runs:
            if not run.text:
                continue
            for k, v in repl.items():
                if k in run.text:
                    run.text = run.text.replace(k, v)

        # cleanup if credentials missing -> remove dangling ", "
        if not director_cred and "[NAME OF THE DIRECTOR]" not in paragraph.text:
            if paragraph.text.strip().endswith(","):
                # remove trailing comma by trimming last run that contains it
                for run in reversed(paragraph.runs):
                    if run.text and run.text.strip().endswith(","):
                        run.text = run.text.rstrip().rstrip(",")
                        break

    # Replace in body paragraphs
    for p in doc.paragraphs:
        replace_in_paragraph_runs(p)

    # Replace in tables too (safe)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_in_paragraph_runs(p)

    # Insert comments where [Comments] is
    comments_para = None
    for p in doc.paragraphs:
        if "[Comments]" in p.text:
            comments_para = p
            break

    if comments_para is not None:
        if not points:
            points = ["No significant comments were provided by reviewers."]

        def _apply_manual_list_format(paragraph):
            pf = paragraph.paragraph_format
            pf.left_indent = Pt(68)   # indent the number to the right
            pf.first_line_indent = Pt(0)
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            try:
                pf.tab_stops.add_tab_stop(Pt(80))  # align comment text
            except (AttributeError, ValueError):
                # Some paragraph styles do not expose tab stops; cosmetic only.
                pass

        # Replace [Comments] run text WITHOUT resetting paragraph.runs
        first_text = f"1.	{points[0]}"
        replaced = False
        for run in comments_para.runs:
            if "[Comments]" in (run.text or ""):
                run.text = run.text.replace("[Comments]", first_text)
                replaced = True

        # If the placeholder was split oddly, fallback to setting the whole paragraph text
        if not replaced:
            comments_para.text = first_text

        _apply_manual_list_format(comments_para)

        # Force Arial 12 in list item runs (numbers + text)
        for run in comments_para.runs:
            run.font.name = "Arial"
            run.font.size = Pt(12)

        last = comments_para
        for idx, pt in enumerate(points[1:], start=2):
            newp = _insert_paragraph_after(last, text=f"{idx}.	{pt}", style=comments_para.style)
            _apply_manual_list_format(newp)

            for run in newp.runs:
                run.font.name = "Arial"
                run.font.size = Pt(12)

            last = newp


    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.getvalue()


@login_required
@role_required(["STAFF"])
def staff_comment_summary_preview(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    # ✅ Use the same round as the staff summary editor
    review_round = _get_review_round_for_staff_summary(proposal)

    summary = (
        ProposalCommentSummary.objects.filter(proposal=proposal, review_round=review_round).first()
        if review_round else None
    )

    comments_qs = (
        ProposalSectionComment.objects.filter(proposal=proposal, review_round=review_round)
        .order_by("step_no", "created_at")
        if review_round else ProposalSectionComment.objects.none()
    )

    # ✅ Prefer saved summary; otherwise generate from comments (no Step labels)
    points = _extract_points(summary.summary_text) if (summary and summary.summary_text) else []
    if not points:
        try:
            points = summarize_comments(comments_qs, include_step_labels=False)
        except Exception:
            logger.exception(
                "summarize_comments failed for proposal %s; using raw comments.", proposal.pk
            )
            points = [c.comment.strip() for c in comments_qs[:12] if (c.comment or "").strip()]

    campus = (proposal.campus or "").strip()
    campus_director = _get_signatory(Signatory.Position.CAMPUS_DIRECTOR, campus=campus) if campus else None
    campus_coordinator = _get_signatory(Signatory.Position.CAMPUS_EXTENSION_COORDINATOR, campus=campus) if campus else None
    director_ext = _get_signatory(Signatory.Position.DIRECTOR_EXTENSION)

    # Full names (for last name extraction)
    campus_director_name = (campus_director.full_name if campus_director else "").strip()
    campus_coordinator_name = (campus_coordinator.full_name if campus_coordinator else "").strip()

    # ✅ Display names with credentials
    campus_director_cred = (campus_director.credentials if campus_director else "").strip()
    campus_coordinator_cred = (campus_coordinator.credentials if campus_coordinator else "").strip()

    campus_director_display = (campus_director_name + (f", {campus_director_cred}" if campus_director_cred else "")).strip() \
        or "[NAME OF THE CAMPUS DIRECTOR]"
    campus_coordinator_display = (campus_coordinator_name + (f", {campus_coordinator_cred}" if campus_coordinator_cred else "")).strip() \
        or "[NAME OF CAMPUS COORDINATOR]"

    director_name = (director_ext.full_name if director_ext else "").strip()
    director_cred = (director_ext.credentials if director_ext else "").strip()
    director_signature = (director_name + (f", {director_cred}" if director_cred else "")).strip() \
        or "[NAME OF THE DIRECTOR], [Credentials]"

    ctx = {
        "proposal": proposal,
        "review_round": review_round,
        "title": proposal.title or proposal.research_title or "Untitled Proposal",
        "date_str": timezone.localdate().strftime("%B %d, %Y"),
        "campus": campus or "[Campus]",
        "campus_director_name": campus_director_name,              # keep for last name extraction
        "campus_director_display": campus_director_display,        # ✅ show with credentials
        "campus_coordinator_display": campus_coordinator_display,  # ✅ show with credentials
        "proponent_line": _proponent_line(proposal),
        "dear_last_name": _extract_last_name(campus_director_name) or "[LAST NAME OF THE CAMPUS DIRECTOR]",
        "points": points,
        "director_signature": director_signature,                  # ✅ already includes credentials
    }
    return render(request, "services/review/proposal_comment_summary_preview.html", ctx)


@login_required
@role_required(["STAFF"])
def staff_comment_summary_docx(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    review_round = _get_review_round_for_staff_summary(proposal)

    summary = (
        ProposalCommentSummary.objects.filter(proposal=proposal, review_round=review_round).first()
        if review_round else None
    )
    comments_qs = (
        ProposalSectionComment.objects.filter(
            proposal=proposal,
            review_round=review_round,
        ).order_by("step_no", "created_at")
        if review_round else ProposalSectionComment.objects.none()
    )

    # Prefer staff-written summary; otherwise generate from comments (NO "Step X ...")
    points = _extract_points(summary.summary_text) if (summary and summary.summary_text) else []
    if not points:
        try:
            points = summarize_comments(comments_qs, include_step_labels=False)
        except Exception:
            logger.exception(
                "summarize_comments failed for proposal %s; using raw comments.", proposal.pk
            )
            points = [c.comment.strip() for c in comments_qs[:8] if (c.comment or "").strip()]

    data = _build_clear_summary_docx(proposal=proposal, points=points)

    filename = f"Comment_Summary_{proposal.title}.docx"
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
