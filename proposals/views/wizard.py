"""
The proposal creation wizard: steps, validation, sharing, and submission.

The step list, each step's form, and its completion rules are admin-managed
(see ``details.ProposalWizardStepConfig`` and the no-code builder). A step
whose layout is ``BUILTIN`` still runs its classic system form - those live in
``proposals.views.wizard_builtin`` behind a registry - while a ``DYNAMIC``
step renders and saves through the admin-built form alone.
"""

from collections import Counter
from datetime import timedelta
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from details.models import ProposalWizardStepConfig
from details.models import RoleCapability
from details.proponent_fields import ensure_proponent_repeater_form
from ..models import Proposal
from ..models import ProposalCollaborator
from ..models import ProposalCommentSummary
from ..models import ProposalEditorPresence
from ..models import ProposalProponent
from ..models import ProposalSectionComment
from accounts.decorators import faculty_like_required
from .constants import TOTAL_STEPS, User
from .dynamic_answers import (
    _attach_dynamic_forms_to_context,
    _is_dynamic_step_complete,
    _proposal_dynamic_requirements_missing,
    _save_dynamic_form_answers,
    _save_step_repeaters,
)
from .permissions import _can_edit, _can_review, _can_view_proposal, _ensure_open_review_round, _get_reviewer_role, _role_has_capability
from .proponents import _update_creator_role
from .wizard_builtin import (
    _builtin_step_complete,
    _builtin_step_context,
    _save_builtin_step,
    mark_step_completed,
    mark_step_skipped,
    unmark_step_completed,
    uses_builtin_form,
)


def _wizard_step_config_map():
    if not ProposalWizardStepConfig.objects.exists():
        from proposals.views.constants import INITIAL_STEP_LABELS
        to_create = []
        for item in INITIAL_STEP_LABELS:
            to_create.append(
                ProposalWizardStepConfig(
                    step_no=item["no"],
                    title=item["title"],
                    description=item["desc"],
                    is_visible=True,
                    is_required=True,
                )
            )
        if to_create:
            ProposalWizardStepConfig.objects.bulk_create(to_create)
        from accounts.views.builders import _seed_default_fields
        try:
            _seed_default_fields()
        except Exception:
            pass
    return {item.step_no: item for item in ProposalWizardStepConfig.objects.all()}


def get_visible_wizard_step_numbers():
    return [
        item.step_no
        for item in ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("step_no")
    ] or [1]


def get_required_wizard_step_numbers():
    return [
        item.step_no
        for item in ProposalWizardStepConfig.objects.filter(is_visible=True, is_required=True).order_by("step_no")
    ]


def normalize_wizard_step(step):
    visible = get_visible_wizard_step_numbers()
    if step in visible:
        return step
    for no in visible:
        if no > step:
            return no
    return visible[-1]


def next_visible_wizard_step(step):
    visible = get_visible_wizard_step_numbers()
    for no in visible:
        if no > step:
            return no
    return None


def previous_visible_wizard_step(step):
    visible = list(reversed(get_visible_wizard_step_numbers()))
    for no in visible:
        if no < step:
            return no
    return None


def is_step_complete(proposal, step, config=None):
    """Is ``step`` complete, judged by whichever form owns it?

    A built-in-layout step is judged by its classic system rule **and** by the
    admin-built extra questions below it (exactly how the Step 3 proponent
    group has always worked - the rule is simply applied to every step now).
    A custom-layout step is judged purely by its admin-built fields - that is
    the whole point of rebuilding a step in the no-code builder.
    """
    if uses_builtin_form(step, config=config):
        if not _builtin_step_complete(proposal, step):
            return False
        # Mirror fields (label overrides for the system form's own inputs) are
        # skipped inside this check, so only the extra questions count.
        return _is_dynamic_step_complete(proposal, step)

    return _is_dynamic_step_complete(proposal, step)


def build_wizard_steps(proposal, current_step, comment_counts=None):
    completed = set(proposal.completed_steps or [])
    skipped = set(proposal.skipped_steps or [])
    comment_counts = comment_counts or {}
    configs = ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("step_no")

    steps = []
    for config in configs:
        no = config.step_no

        if no == current_step:
            state = "current"
        elif no in completed:
            state = "completed"
        elif no in skipped:
            state = "skipped"
        else:
            state = "upcoming"

        ccount = int(comment_counts.get(no, 0) or 0)
        steps.append({
            "no": no,
            "title": config.title,
            "desc": config.description,
            "is_required": config.is_required,
            "state": state,
            "comment_count": ccount,
            "has_comment": ccount > 0,
        })
    return steps


def _build_wizard_context(proposal, step, request_user, comment_counts=None, step_config=None):
    required_steps = set(get_required_wizard_step_numbers())
    completed_required = required_steps.intersection(set(proposal.completed_steps or []))
    progress = int((len(completed_required) / len(required_steps)) * 100) if required_steps else 100
    if step_config is None:
        configs = _wizard_step_config_map()
        step_config = configs.get(step)

    ctx = {
        "proposal": proposal,
        "step": step,
        "total_steps": TOTAL_STEPS,
        "progress": progress,
        "wizard_steps": build_wizard_steps(proposal, step, comment_counts=comment_counts),
        "wizard_step_config": step_config,
    }

    active_cutoff = timezone.now() - timedelta(seconds=45)
    active_editors = (
        proposal.editor_presences
        .select_related("user", "user__profile")
        .filter(last_seen__gte=active_cutoff)
        .exclude(user=request_user)
    )
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


def _step_context_for_get(ctx, proposal, step, step_config):
    """Attach the per-step data the step template needs on GET.

    Built-in steps get their classic context from the registry module; custom
    steps carry everything they need on the admin-built forms themselves.
    """
    if uses_builtin_form(step, config=step_config):
        ctx.update(_builtin_step_context(proposal, step))
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
    step_configs = _wizard_step_config_map()

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
    step_config = step_configs.get(step)
    ctx = _build_wizard_context(
        proposal, step, request.user,
        comment_counts=step_comment_counts,
        step_config=step_config,
    )

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
    if step == 3:
        # Seeds the default proponent group (Name, Designation, ...) the first
        # time the step is opened, so Step 3 works before an admin ever visits
        # the builder. Admins who change or delete those fields are not
        # overruled: seeding only fills a completely empty form.
        ensure_proponent_repeater_form(step)
    _attach_dynamic_forms_to_context(ctx, proposal, step)

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

    # A built-in-layout step renders its classic template; a custom-layout
    # step renders the generic dynamic template, where the admin-built form
    # *is* the step content.
    builtin_step = uses_builtin_form(step, config=step_config)
    template = "services/wizard/step_dynamic.html"
    if builtin_step:
        from django.template.loader import select_template
        try:
            select_template([f"services/wizard/step_{step}.html"])
            template = f"services/wizard/step_{step}.html"
        except Exception:
            template = "services/wizard/step_dynamic.html"
    ctx["dynamic_only_step"] = template == "services/wizard/step_dynamic.html"

    if request.method == "GET":
        _step_context_for_get(ctx, proposal, step, step_config)
        return render(request, template, ctx)

    if action == "save_comment":
        return _handle_save_comment(
            request, proposal, step, current_round, reviewer_role
        )

    # Required-field problems found by a step's own save path (currently the
    # Step 3 proponent group); merged with the admin-managed fields below so
    # "Save & Next" blocks on both. Custom-layout steps have no built-in
    # save path - their fields are saved by the dynamic-form code below.
    step_missing = []

    if builtin_step:
        early_response, builtin_missing = _save_builtin_step(request, proposal, step, action)
        step_missing.extend(builtin_missing)
        if early_response is not None:
            return early_response

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

    if action in ("add_member", "save_members"):
        # A repeatable group's row buttons (add / remove / move) submit these
        # actions: save what was posted and stay on the step instead of
        # advancing, matching the built-in Step 3 behaviour. On a built-in
        # Step 3 the saver above already returned; this covers custom steps.
        if is_step_complete(proposal, step):
            mark_step_completed(proposal, step)
        else:
            unmark_step_completed(proposal, step)
        proposal.save(update_fields=["completed_steps", "skipped_steps"])
        messages.success(request, "Saved.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=step)

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
