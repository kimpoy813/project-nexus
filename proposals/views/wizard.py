"""
The proposal creation wizard: steps, validation, sharing, and submission.
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
from django.template.loader import select_template
from django.utils import timezone
from django.views.decorators.http import require_GET
from details.models import DynamicFormField
from details.models import DynamicFormResponse
from details.models import DynamicFormTemplate
from details.models import ProposalWizardStepConfig
from details.models import RoleCapability
from details.proponent_fields import ensure_proponent_repeater_form
from ..models import ProgramProject
from ..models import Proposal
from ..models import ProposalCollaborator
from ..models import ProposalCommentSummary
from ..models import ProposalEditorPresence
from ..models import ProposalProponent
from ..models import ProposalSectionComment
from accounts.decorators import faculty_like_required, admin_required
from .constants import TOTAL_STEPS, User
from .dynamic_fields import (
    dependency_parent_value as _dependency_parent_value,
    dynamic_field_blocks_submission as _dynamic_field_blocks_submission,
    dynamic_parent_values_from_post as _dynamic_parent_values_from_post,
    dynamic_parent_values_from_saved as _dynamic_parent_values_from_saved,
)
from .dynamic_answers import (
    _attach_dynamic_forms_to_context,
    _dynamic_forms_for_proposal_step,
    _is_dynamic_step_complete,
    _proposal_dynamic_requirements_missing,
    _save_dynamic_form_answers,
    _save_step_repeaters,
)
from .helpers import _strip_phase_prefix, _to_int, _to_roman
from .step_flows import (
    _add_research_step_context_for_get,
    _add_training_step_context_for_get,
    _is_research_step_complete,
    _is_training_step_complete,
    _save_research_step,
    _save_training_step,
)
from .permissions import _can_edit, _can_review, _can_view_proposal, _ensure_open_review_round, _get_reviewer_role, _role_has_capability
from .proponents import _update_creator_role, save_step_three_proponents


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


def proposal_flow(proposal):
    """The wizard flow a proposal belongs to, based on its extension type.

    Research-based proposals answer the Extension Proposal form (RESEARCH
    flow); community-based and request-based proposals answer the Training
    Design form (TRAINING flow). Returns ``None`` while the type is unset -
    the proposal has only reached the shared Step 1.
    """
    from details.models import WizardFlow
    return WizardFlow.flow_for_extension_type(proposal.extension_type)


def _wizard_step_config_map(proposal=None):
    """Seed the step table on first use and return ``{step_no: config}``.

    With a proposal, only the rows that proposal answers are returned: the
    shared steps plus its flow's steps.
    """
    if not ProposalWizardStepConfig.objects.exists():
        from proposals.views.constants import (
            SHARED_STEP_LABELS,
            INITIAL_RESEARCH_STEPS,
            INITIAL_TRAINING_STEPS,
        )
        to_create = []
        for flow, items in (
            ("ALL", SHARED_STEP_LABELS),
            ("RESEARCH", INITIAL_RESEARCH_STEPS),
            ("TRAINING", INITIAL_TRAINING_STEPS),
        ):
            for item in items:
                to_create.append(
                    ProposalWizardStepConfig(
                        step_no=item["no"],
                        flow=flow,
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
            import traceback, sys
            traceback.print_exc(file=sys.stderr)

    rows = ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("flow", "step_no")
    if proposal is not None:
        flow = proposal_flow(proposal)
        if flow:
            rows = rows.filter(flow__in=["ALL", flow])
        else:
            # Not picked a type yet: the classic list (shared + research).
            rows = rows.filter(flow__in=["ALL", "RESEARCH"])
    return {item.step_no: item for item in rows}


def get_visible_wizard_step_numbers(proposal=None):
    rows = ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("flow", "step_no")
    if proposal is not None:
        # A draft that has not reached/picked a type yet keeps seeing the
        # classic (Extension Proposal shaped) list, exactly as before the
        # split; the flow locks in once Step 1 is saved.
        flow = proposal_flow(proposal) or "RESEARCH"
        rows = rows.filter(flow__in=["ALL", flow])
    numbers = [item.step_no for item in rows]
    # Step 1 (shared) first; flow steps may share its numbering space.
    return sorted(set(numbers)) or [1]


def get_required_wizard_step_numbers(proposal=None):
    rows = ProposalWizardStepConfig.objects.filter(is_visible=True, is_required=True).order_by("flow", "step_no")
    if proposal is not None:
        flow = proposal_flow(proposal) or "RESEARCH"
        rows = rows.filter(flow__in=["ALL", flow])
    return sorted({item.step_no for item in rows})


def normalize_wizard_step(step, proposal=None):
    visible = get_visible_wizard_step_numbers(proposal)
    if step in visible:
        return step
    for no in visible:
        if no > step:
            return no
    return visible[-1]


def next_visible_wizard_step(step, proposal=None):
    visible = get_visible_wizard_step_numbers(proposal)
    for no in visible:
        if no > step:
            return no
    return None


def previous_visible_wizard_step(step, proposal=None):
    visible = list(reversed(get_visible_wizard_step_numbers(proposal)))
    for no in visible:
        if no < step:
            return no
    return None


def is_step_complete(proposal, step):
    if step == 1:
        if not proposal.extension_type or not proposal.scope_type:
            return False
        if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"] and not (proposal.research_title or "").strip():
            return False
        return True

    # Steps 2-4 mean the same thing in both flows.
    if step == 2:
        if not (proposal.title or "").strip():
            return False
        if proposal.scope_type == "PROGRAM":
            return proposal.program_projects.exists()
        return True

    if step == 3:
        # At least one proponent, plus whatever the admin-made proponent fields
        # mark as required (the repeatable group's required columns and its
        # minimum row count).
        if not proposal.proponents.exists():
            return False
        return _is_dynamic_step_complete(proposal, step)

    if step == 4:
        return bool((proposal.implementing_agency or "").strip())

    # From step 5 on, the two flows diverge (the Training Design flow has no
    # Significance or Date & Venue, for example).
    if proposal_flow(proposal) == "TRAINING":
        return _is_training_step_complete(proposal, step)
    return _is_research_step_complete(proposal, step)


def build_wizard_steps(proposal, current_step, comment_counts=None):
    completed = set(proposal.completed_steps or [])
    skipped = set(proposal.skipped_steps or [])
    comment_counts = comment_counts or {}

    flow = proposal_flow(proposal)
    configs = ProposalWizardStepConfig.objects.filter(is_visible=True).order_by("flow", "step_no")
    if flow:
        configs = configs.filter(flow__in=["ALL", flow])
    else:
        # Not picked a type yet: the classic list (shared + research).
        configs = configs.filter(flow__in=["ALL", "RESEARCH"])

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


def _build_wizard_context(proposal, step, request_user, comment_counts=None):
    required_steps = set(get_required_wizard_step_numbers(proposal))
    completed_required = required_steps.intersection(set(proposal.completed_steps or []))
    progress = int((len(completed_required) / len(required_steps)) * 100) if required_steps else 100
    configs = _wizard_step_config_map(proposal)
    step_config = configs.get(step)

    ctx = {
        "proposal": proposal,
        "step": step,
        # Flow-aware total: the last step THIS proposal's form actually has,
        # so "Step N of M" and the read-only next links match the flow.
        "total_steps": max(get_visible_wizard_step_numbers(proposal), default=1),
        "progress": progress,
        "wizard_steps": build_wizard_steps(proposal, step, comment_counts=comment_counts),
        "wizard_step_config": step_config,
        "wizard_flow": proposal_flow(proposal) or "",
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


def _add_step_context_for_get(ctx, proposal, step):
    """Attach the per-step data the wizard templates need on GET.

    Split out of ``proposal_wizard`` purely for readability: this was ~100
    lines of ``if step == N`` inline in the view. Mutates and returns ``ctx``.
    """
    if step == 2 and proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")

    if step == 3:
        ctx["proponents"] = proposal.proponents.select_related("user").all().order_by("id")
        if proposal.scope_type == "PROGRAM":
            ctx["program_projects"] = proposal.program_projects.select_related("leader_user").all().order_by("order", "id")

    if proposal_flow(proposal) == "TRAINING":
        return _add_training_step_context_for_get(ctx, proposal, step)
    return _add_research_step_context_for_get(ctx, proposal, step)


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
    _wizard_step_config_map(proposal)

    # int() matters: min() returns the TOTAL_STEPS wrapper when the requested
    # step is past the end, and a wrapper is not a usable step number.
    step = normalize_wizard_step(max(1, min(step, int(TOTAL_STEPS))), proposal)
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

    # Flow-specific template first (the two forms ask for different things at
    # the same step number), then the shared step template, then the generic
    # admin-built page. A draft that has not picked a type yet is on the
    # classic (research-shaped) list, so it gets the research templates.
    flow = proposal_flow(proposal) or "RESEARCH"
    candidates = [
        f"services/wizard/step_{flow.lower()}_{step}.html",
        f"services/wizard/step_{step}.html",
        "services/wizard/step_dynamic.html",
    ]
    template = select_template(candidates).template.name

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

    if step == 1:
        previous_flow = proposal_flow(proposal)
        proposal.extension_type = request.POST.get("extension_type", "")
        proposal.scope_type = request.POST.get("scope_type", "")
        research_title = (request.POST.get("research_title") or "").strip()

        if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]:
            proposal.research_title = research_title
        else:
            proposal.research_title = ""

        if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"] and not research_title and action != "skip":
            messages.error(request, "Research Title is required for research-based extension type.")
            return redirect("proposal_wizard", proposal_id=proposal.id, step=1)

        # Switching between the Extension Proposal and Training Design forms
        # changes what steps 5+ mean, so progress above the shared steps is
        # re-answered rather than carried across misleadingly.
        new_flow = proposal_flow(proposal)
        if previous_flow and new_flow and previous_flow != new_flow:
            shared_end = 4
            mark_step_completed(proposal, 1)
            proposal.completed_steps = [
                no for no in (proposal.completed_steps or []) if no <= shared_end
            ] or [1]
            proposal.skipped_steps = [
                no for no in (proposal.skipped_steps or []) if no <= shared_end
            ]

        proposal.save(update_fields=["extension_type", "scope_type", "research_title"])
        _update_creator_role(proposal)

    elif step == 2:
        proposal.title = (request.POST.get("title") or "").strip()
        proposal.save(update_fields=["title"])

        if proposal.scope_type == "PROGRAM":
            raw_ids = request.POST.getlist("project_id[]")
            raw_titles = request.POST.getlist("project_titles[]")

            max_len = max(len(raw_ids), len(raw_titles), 0)
            raw_ids += [""] * (max_len - len(raw_ids))
            raw_titles += [""] * (max_len - len(raw_titles))

            existing = {str(p.id): p for p in proposal.program_projects.all()}
            keep_db_ids = []
            to_update = []
            to_create = []

            for i in range(max_len):
                pid = (raw_ids[i] or "").strip()
                clean_title = _strip_phase_prefix(raw_titles[i])

                if not clean_title:
                    continue

                order_no = len(keep_db_ids) + len(to_create) + 1
                stored_title = f"Phase {_to_roman(order_no)} {clean_title}"

                if pid and pid in existing:
                    prj = existing[pid]
                    prj.title = stored_title
                    prj.order = order_no
                    to_update.append(prj)
                    keep_db_ids.append(prj.id)
                else:
                    to_create.append(
                        ProgramProject(
                            proposal=proposal,
                            title=stored_title,
                            order=order_no,
                        )
                    )

            proposal.program_projects.exclude(id__in=keep_db_ids).delete()

            if to_update:
                ProgramProject.objects.bulk_update(to_update, ["title", "order"])
            if to_create:
                ProgramProject.objects.bulk_create(to_create)

    elif step == 3:
        step_missing.extend(save_step_three_proponents(proposal, request))

        if action in ("add_member", "save_members"):
            if is_step_complete(proposal, step):
                mark_step_completed(proposal, step)
            else:
                unmark_step_completed(proposal, step)

            proposal.save(update_fields=["completed_steps", "skipped_steps"])
            if step_missing:
                messages.error(
                    request,
                    "Saved, but some required proponent details are still missing: "
                    + "; ".join(step_missing[:5]),
                )
            else:
                messages.success(request, "Members updated.")
            return redirect("proposal_wizard", proposal_id=proposal.id, step=3)

    elif step == 4:
        proposal.implementing_agency = (request.POST.get("implementing_agency") or "").strip()
        proposal.save(update_fields=["implementing_agency"])

    else:
        save_fn = _save_training_step if proposal_flow(proposal) == "TRAINING" else _save_research_step
        early_redirect = save_fn(proposal, step, request, action)
        if early_redirect is not None:
            return early_redirect

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
        return redirect("proposal_wizard", proposal_id=proposal.id, step=previous_visible_wizard_step(step, proposal) or step)

    if action == "skip":
        mark_step_skipped(proposal, step)
        proposal.save(update_fields=["completed_steps", "skipped_steps"])
        messages.info(request, "Skipped.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=next_visible_wizard_step(step, proposal) or step)

    if is_step_complete(proposal, step):
        mark_step_completed(proposal, step)
    else:
        unmark_step_completed(proposal, step)

    proposal.save(update_fields=["completed_steps", "skipped_steps"])

    next_step = next_visible_wizard_step(step, proposal)
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

    all_required_steps = set(get_required_wizard_step_numbers(proposal))
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
