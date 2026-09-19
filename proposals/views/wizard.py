"""
The proposal creation wizard: steps, validation, sharing, and submission.
"""

from collections import Counter
from datetime import timedelta
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from details.models import RoleCapability
from ..models import Proposal
from ..models import ProposalCollaborator
from ..models import ProposalCommentSummary
from ..models import ProposalEditorPresence
from ..models import ProposalProponent
from ..models import ProposalSectionComment
from accounts.decorators import faculty_like_required, admin_required
from .constants import TOTAL_STEPS, User
from .wizard_flows import proposal_flow
from .dynamic_answers import (
    _attach_dynamic_forms_to_context,
    _attach_proposal_dynamic_forms,
    _dynamic_forms_for_proposal_step,
    _is_dynamic_step_complete,
    _proposal_dynamic_requirements_missing,
    _save_dynamic_form_answers,
    _save_step_repeaters,
)
from .permissions import _can_edit, _can_review, _can_view_proposal, _ensure_open_review_round, _get_reviewer_role, _role_has_capability
from .proponents import _update_creator_role


def mark_step_completed(proposal, step_no):
    """Record a step as done. Callers flash their own message.

    This used to call ``messages.success(request, ...)`` with no ``request`` in
    scope - ``request`` resolved to the (then imported) ``urllib3.request``
    module, so every "Save & Next" that completed a step raised a TypeError.
    """
    completed = set(proposal.completed_steps or [])
    skipped = set(proposal.skipped_steps or [])
    completed.add(step_no)
    skipped.discard(step_no)
    proposal.completed_steps = sorted(completed)
    proposal.skipped_steps = sorted(skipped)


def mark_step_skipped(proposal, step_no):
    completed = set(proposal.completed_steps or [])
    skipped = set(proposal.skipped_steps or [])
    completed.discard(step_no)
    skipped.add(step_no)
    proposal.completed_steps = sorted(completed)
    proposal.skipped_steps = sorted(skipped)


def unmark_step_completed(proposal, step_no):
    completed = set(proposal.completed_steps or [])
    completed.discard(step_no)
    proposal.completed_steps = sorted(completed)


def _wizard_step_config_map():
    """``{step_no: config}`` for every step, seeding the defaults on first use.

    The wizard used to seed this table in three places; the flow owns it now so
    the seed cannot drift between the wizard, the admin screens, and the
    sidebar.
    """
    proposal_flow.ensure_defaults()
    return proposal_flow.config_map()


def get_visible_wizard_step_numbers():
    return proposal_flow.visible_step_nos()


def get_required_wizard_step_numbers():
    return proposal_flow.required_step_nos()


def normalize_wizard_step(step):
    return proposal_flow.normalize(step)


def next_visible_wizard_step(step):
    return proposal_flow.step_after(step)


def previous_visible_wizard_step(step):
    return proposal_flow.step_before(step)


def wizard_section_for(step):
    """The built-in part on this step, or ``None`` for an office-built step."""
    return proposal_flow.section(step)


def is_step_complete(proposal, step):
    """Whether a step counts as done.

    Two halves, because a step can now carry both:

    * the completion rule of the built-in *part* the step points at (``None``
      when the step is office-built only); and
    * the required fields of any forms the office attached to that step.

    The second half is new and deliberate: attaching a required office form to
    a step must be able to hold the step open, or the admin's form would be
    cosmetic.
    """
    section = wizard_section_for(step)
    if section is not None and section.is_complete is not None:
        if not section.is_complete(proposal, step):
            return False

    return _is_dynamic_step_complete(proposal, step)


def build_wizard_steps(proposal, current_step, comment_counts=None):
    """Sidebar entries for every visible step, in the office's order."""
    completed = set(proposal.completed_steps or [])
    skipped = set(proposal.skipped_steps or [])
    comment_counts = comment_counts or {}

    def state_for(config, current):
        if config.step_no == current:
            return "current"
        if config.step_no in completed:
            return "completed"
        if config.step_no in skipped:
            return "skipped"
        return "upcoming"

    steps = proposal_flow.build_steps(current_step, state_for=state_for)
    for entry in steps:
        count = int(comment_counts.get(entry["no"], 0) or 0)
        entry["comment_count"] = count
        entry["has_comment"] = count > 0
    return steps


def _build_wizard_context(proposal, step, request_user, comment_counts=None):
    required_steps = set(get_required_wizard_step_numbers())
    completed_required = required_steps.intersection(set(proposal.completed_steps or []))
    progress = int((len(completed_required) / len(required_steps)) * 100) if required_steps else 100
    configs = _wizard_step_config_map()
    step_config = configs.get(step)

    ctx = {
        "proposal": proposal,
        "step": step,
        "total_steps": TOTAL_STEPS,
        "progress": progress,
        "wizard_steps": build_wizard_steps(proposal, step, comment_counts=comment_counts),
        "wizard_step_config": step_config,
        # Step numbers are stable handles, not positions: the office can hide
        # or delete a step, so "Step 6 of 19" would be a lie. Templates get the
        # real position and the real neighbours to link to.
        "step_position": proposal_flow.position(step),
        "step_total": proposal_flow.total_visible(),
        "step_section_key": step_config.section_key if step_config else "",
        "next_step_no": proposal_flow.step_after(step),
        "prev_step_no": proposal_flow.step_before(step),
    }

    active_cutoff = timezone.now() - timedelta(seconds=45)
    active_editors = (
        proposal.editor_presences
        .select_related("user", "user__profile")
        .filter(last_seen__gte=active_cutoff)
        .exclude(user=request_user)
    )
    # Presence chips say "Step 4", which has to be the *position* the sidebar
    # shows, not the step number that happens to be stored on the row.
    positions = {no: index for index, no in enumerate(proposal_flow.visible_step_nos(), start=1)}
    for editor in active_editors:
        editor.step_position = positions.get(editor.step, editor.step)
    ctx["active_editors"] = active_editors
    return ctx


@login_required
@faculty_like_required
def proposal_create(request):
    if not _role_has_capability(request.user, RoleCapability.Capability.CREATE_PROPOSAL):
        messages.error(request, "Your role is not currently allowed to create proposals. Please contact the administrator.")
        return redirect("dashboard_redirect")

    profile = getattr(request.user, "profile", None)

    proposal = Proposal.objects.create(
        created_by=request.user,
        campus=getattr(profile, "campus", "") or "",
        college=getattr(profile, "college", "") or "",
        department=getattr(profile, "department", "") or "",
        current_step=1,
    )

    ProposalProponent.objects.get_or_create(
        proposal=proposal,
        user=request.user,
        defaults={
            "full_name": getattr(profile, "full_name", request.user.username),
            "email": request.user.email or "",
            "role": "Proponent",
        },
    )

    _update_creator_role(proposal)
    return redirect("proposal_wizard", proposal_id=proposal.id, step=1)


def _sidebar_comment_counts(proposal, current_round):
    """Comments per wizard step, for the sidebar badges.

    Only populated while the proposal is FOR_REVISION: badges are a cue for
    the proponent to act, so they are noise at any other status.
    """
    if not current_round:
        return {}
    if proposal.proposal_status != Proposal.ProposalStatus.FOR_REVISION:
        return {}

    raw_steps = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=current_round,
    ).values_list("step_no", flat=True)

    counts = Counter()
    for raw in raw_steps:
        try:
            step_no = int(raw or 1)
        except (TypeError, ValueError):
            step_no = 1
        counts[step_no] += 1
    return dict(counts)


def _proponent_review_panel(proposal, current_round, step, *, is_proponent):
    """Return ``(review_summary, visible_comments)`` for the read-only panel.

    Reviewers see their own tooling elsewhere; this is what the *proponent*
    sees. Individual comments are only exposed once the proposal has been
    returned FOR_REVISION, so in-progress review notes stay private.
    """
    if not (is_proponent and current_round):
        return None, []

    review_summary = ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=current_round,
        sent_to_proponent=True,
    ).first()

    if proposal.proposal_status != Proposal.ProposalStatus.FOR_REVISION:
        return review_summary, []

    visible_comments = (
        ProposalSectionComment.objects.filter(
            proposal=proposal,
            review_round=current_round,
            step_no=step,
        )
        .select_related("reviewer", "reviewer__profile")
        .order_by("step_no", "created_at")
    )
    return review_summary, visible_comments


def _add_step_context_for_get(ctx, proposal, step):
    """Attach the per-step data the wizard templates need on GET.

    This was ~100 lines of ``if step == N`` inline in the view, and then a
    second copy of the same knowledge in the POST handler. Both now ask the
    step's built-in part, so a part carries its own rendering *and* its own
    saving, and a step with no part simply needs nothing here.
    """
    section = wizard_section_for(step)
    if section is not None and section.add_context is not None:
        section.add_context(ctx, proposal, step)
    return ctx


def _handle_save_comment(request, proposal, step, current_round, reviewer_role):
    """Persist a reviewer's comment for one wizard step.

    One comment per reviewer per step per round: re-submitting updates the
    existing row rather than adding another. Always returns a redirect.
    """
    comment_text = (request.POST.get("comment") or "").strip()
    if not comment_text:
        messages.error(request, "Comment cannot be empty.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=step)

    existing_step_comment = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=current_round,
        reviewer=request.user,
        step_no=step,
    ).first()

    if existing_step_comment:
        existing_step_comment.comment = comment_text
        existing_step_comment.reviewer_role = reviewer_role
        existing_step_comment.save(update_fields=["comment", "reviewer_role"])
        messages.success(request, f"Your comment for Step {step} was updated.")
    else:
        ProposalSectionComment.objects.create(
            proposal=proposal,
            review_round=current_round,
            reviewer=request.user,
            reviewer_role=reviewer_role,
            step_no=step,
            comment=comment_text,
        )
        messages.success(request, f"Your comment for Step {step} was saved.")

    if proposal.proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW:
        proposal.mark_in_review(review_level=proposal.review_level or Proposal.ReviewLevel.DEPARTMENT)

    return redirect("proposal_wizard", proposal_id=proposal.id, step=step)

@login_required
@faculty_like_required
def proposal_wizard(request, proposal_id, step):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_proposal(request.user, proposal):
        messages.error(request, "You don't have access to this proposal.")
        return redirect("dashboard_redirect")

    # The step list is seeded on first use; do it before clamping the requested
    # step, otherwise an empty table makes every step clamp to step 1.
    _wizard_step_config_map()

    # int() matters: min() returns the TOTAL_STEPS wrapper when the requested
    # step is past the end, and a wrapper is not a usable step number.
    step = normalize_wizard_step(max(1, min(step, int(TOTAL_STEPS))))
    can_edit = _can_edit(request.user, proposal)
    can_review = _can_review(request.user, proposal)

    if can_edit:
        ProposalEditorPresence.objects.update_or_create(
            proposal=proposal,
            user=request.user,
            defaults={
                "last_seen": timezone.now(),
                "step": step,
            },
        )

    if can_edit and step > (proposal.current_step or 1):
        proposal.current_step = step
        proposal.save(update_fields=["current_step"])

    current_round = proposal.get_active_review_round() or proposal.get_current_review_round()

    step_comment_counts = _sidebar_comment_counts(proposal, current_round)


    is_proponent_view = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )

    review_summary, visible_comments = _proponent_review_panel(
        proposal, current_round, step, is_proponent=is_proponent_view
    )

    # 🔥 IMPORTANT: ctx must exist first
    ctx = _build_wizard_context(proposal, step, request.user, comment_counts=step_comment_counts)

    # add review panel data
    ctx["review_summary"] = review_summary
    ctx["visible_comments"] = visible_comments
    ctx["show_readonly_review_panel"] = bool(review_summary or visible_comments)

    reviewer_role = _get_reviewer_role(request.user, proposal, current_round)
    can_comment = bool(reviewer_role and current_round)

    action = request.POST.get("action", "next") if request.method == "POST" else "next"

    if request.method == "POST":
        if action == "save_comment":
            if not can_comment:
                messages.error(request, "You are not allowed to comment on this proposal.")
                return redirect("proposal_wizard", proposal_id=proposal.id, step=step)
        else:
            if not can_edit:
                messages.error(request, "You can review this proposal, but you cannot edit it.")
                return redirect("proposal_wizard", proposal_id=proposal.id, step=step)

            editable_statuses = {
                Proposal.ProposalStatus.DRAFTING,
                Proposal.ProposalStatus.FOR_REVISION,
            }
            if proposal.is_locked and proposal.proposal_status not in editable_statuses:
                messages.warning(request, "This proposal is currently locked for editing.")
                return redirect("proposal_wizard", proposal_id=proposal.id, step=step)

    ctx["is_edit_mode"] = proposal.proposal_status in [
        Proposal.ProposalStatus.DRAFTING,
        Proposal.ProposalStatus.FOR_REVISION,
    ]
    ctx["is_review_mode"] = can_review and not can_edit
    ctx["current_review_round"] = current_round
    ctx["can_comment"] = can_comment
    ctx["reviewer_role"] = reviewer_role
    ctx["can_edit_proposal"] = can_edit
    step_section = wizard_section_for(step)
    if step_section is not None and step_section.prepare is not None:
        # Parts that need first-run defaults run them here. The Proponents part
        # uses this to seed the office's default repeatable group (Name,
        # Designation, ...) so the step works before an admin ever visits the
        # builder; seeding only fills a completely empty form, so an admin's
        # own layout is never overruled.
        step_section.prepare(proposal, step)
    _attach_proposal_dynamic_forms(ctx, proposal, step)

    if ctx["can_comment"]:
        ctx["existing_step_comment"] = ProposalSectionComment.objects.filter(
            proposal=proposal,
            review_round=current_round,
            reviewer=request.user,
            step_no=step,
        ).first()

        ctx["step_comments"] = ProposalSectionComment.objects.filter(
            proposal=proposal,
            review_round=current_round,
            step_no=step,
        ).select_related("reviewer", "reviewer__profile").order_by("created_at")
    else:
        ctx["existing_step_comment"] = None
        ctx["step_comments"] = []

    # The part decides the template, so re-pointing a step at another part - or
    # at no part at all - changes what renders without touching this view.
    template = proposal_flow.template_for(step)

    if request.method == "GET":
        _add_step_context_for_get(ctx, proposal, step)
        return render(request, template, ctx)

    if action == "save_comment":
        return _handle_save_comment(
            request, proposal, step, current_round, reviewer_role
        )

    # Required-field problems found by a step's own save path (currently the
    # Step 3 proponent group); merged with the admin-managed fields below so
    # "Save & Next" blocks on both.
    step_missing = []

    section = wizard_section_for(step)
    if section is not None and section.save is not None:
        section_result = section.save(request, proposal, step, action)
        if isinstance(section_result, HttpResponse):
            # The part handled the request itself: an error to flash, or an
            # action of its own (the Proponents part's "add member" button).
            return section_result
        if section_result:
            step_missing.extend(section_result)

    step_missing.extend(_save_step_repeaters(proposal, step, request, request.user))
    dynamic_missing = step_missing + _save_dynamic_form_answers(proposal, step, request.user, request)
    if action == "next" and dynamic_missing:
        unmark_step_completed(proposal, step)
        proposal.save(update_fields=["completed_steps", "skipped_steps"])
        messages.error(
            request,
            "Please complete the required admin-managed field(s): " + "; ".join(dynamic_missing[:5]),
        )
        return redirect("proposal_wizard", proposal_id=proposal.id, step=step)

    if action == "back":
        return redirect("proposal_wizard", proposal_id=proposal.id, step=previous_visible_wizard_step(step) or step)

    if action == "skip":
        mark_step_skipped(proposal, step)
        proposal.save(update_fields=["completed_steps", "skipped_steps"])
        messages.info(request, "Skipped.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=next_visible_wizard_step(step) or step)

    if is_step_complete(proposal, step):
        mark_step_completed(proposal, step)
    else:
        unmark_step_completed(proposal, step)

    proposal.save(update_fields=["completed_steps", "skipped_steps"])

    next_step = next_visible_wizard_step(step)
    if not next_step:
        messages.success(request, "All visible required steps completed.")
        return redirect("proposal_submit", proposal_id=proposal.id)

    messages.success(request, "Draft saved.")
    return redirect("proposal_wizard", proposal_id=proposal.id, step=next_step)


@login_required
@faculty_like_required
def proposal_submit(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_edit(request.user, proposal):
        messages.error(request, "No access.")
        return redirect("services_home")

    editable_statuses = {
        Proposal.ProposalStatus.DRAFTING,
        Proposal.ProposalStatus.FOR_REVISION,
    }
    if proposal.is_locked and proposal.proposal_status not in editable_statuses:
        messages.warning(request, "This proposal has already been submitted or is not editable.")
        return redirect("services_home")

    all_required_steps = set(get_required_wizard_step_numbers())
    completed_steps = set(proposal.completed_steps or [])

    if not all_required_steps.issubset(completed_steps):
        messages.error(request, "Please complete all required steps before submitting.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=proposal.current_step)

    dynamic_missing = _proposal_dynamic_requirements_missing(proposal)
    if dynamic_missing:
        messages.error(
            request,
            "Please complete the admin-managed requirement(s): " + "; ".join(dynamic_missing[:5]),
        )
        first_missing_step = None
        for item in dynamic_missing:
            match = re.search(r"Step (\d+)", item)
            if match:
                first_missing_step = int(match.group(1))
                break
        return redirect("proposal_wizard", proposal_id=proposal.id, step=first_missing_step or proposal.current_step)

    if request.method == "POST":
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION:

            current_round = proposal.get_current_review_round()
            if current_round:
                current_round.is_closed = True
                current_round.ready_for_staff_summary = False
                current_round.save()

            proposal.is_locked = False
            proposal.start_review_round()
            _ensure_open_review_round(proposal, request.user)

            proposal.transition_proposal_status(
                Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW
            )

            messages.success(request, "Proposal resubmitted successfully.")
        else:
            proposal.lock_and_submit()
            proposal.start_review_round()
            _ensure_open_review_round(proposal, request.user)
            messages.success(request, "Proposal submitted successfully.")

        return redirect("services_home")

    return render(request, "services/proposal_submit.html", {"proposal": proposal})


@login_required
@faculty_like_required
def proposal_share(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if proposal.created_by_id != request.user.id:
        messages.error(request, "Only the creator can manage sharing.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=proposal.current_step)

    if request.method == "POST":
        query = (request.POST.get("q") or "").strip()
        if not query:
            messages.error(request, "Enter username or email.")
            return redirect("proposal_share", proposal_id=proposal.id)

        user_obj = User.objects.filter(Q(username__iexact=query) | Q(email__iexact=query)).first()
        if not user_obj:
            messages.error(request, "User not found.")
            return redirect("proposal_share", proposal_id=proposal.id)

        ProposalCollaborator.objects.get_or_create(
            proposal=proposal,
            user=user_obj,
            defaults={"can_edit": True},
        )
        messages.success(request, f"Shared with {user_obj.username}.")
        return redirect("proposal_share", proposal_id=proposal.id)

    collaborators = proposal.collaborators.select_related("user").all()
    return render(
        request,
        "services/proposal_share.html",
        {"proposal": proposal, "collaborators": collaborators},
    )


@login_required
def proposal_editor_ping(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_edit(request.user, proposal):
        return JsonResponse({"ok": False}, status=403)

    step = request.GET.get("step")
    try:
        step = int(step)
    except (TypeError, ValueError):
        step = 1

    ProposalEditorPresence.objects.update_or_create(
        proposal=proposal,
        user=request.user,
        defaults={
            "last_seen": timezone.now(),
            "step": step,
        },
    )

    return JsonResponse({"ok": True})


@login_required
@faculty_like_required
def title_suggest(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 3:
        return JsonResponse({"suggestions": []})

    suggestions = (
        Proposal.objects.filter(title__icontains=query)
        .values_list("title", flat=True)
        .distinct()[:8]
    )
    return JsonResponse({"suggestions": list(suggestions)})


@require_GET
@login_required
@faculty_like_required
def proponent_search(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    users = (
        User.objects.select_related("profile")
        .filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(profile__full_name__icontains=query)
        )
        .distinct()[:10]
    )

    results = []
    for user_obj in users:
        prof = getattr(user_obj, "profile", None)
        results.append({
            "id": user_obj.id,
            "username": user_obj.username,
            "name": getattr(prof, "full_name", user_obj.username),
            "email": user_obj.email or "",
            "designation": getattr(prof, "department", "") or "",
            "campus": getattr(prof, "campus", "") or "",
        })

    return JsonResponse({"results": results})
