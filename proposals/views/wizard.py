"""
The proposal creation wizard: steps, validation, sharing, and submission.
"""

from collections import Counter
from datetime import timedelta
from urllib3 import request
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
from details.models import DynamicFormAnswer
from details.models import DynamicFormField
from details.models import DynamicFormResponse
from details.models import DynamicFormTemplate
from details.models import ProposalWizardStepConfig
from details.models import RoleCapability
from ..models import ProgramProject
from ..models import Proposal
from ..models import ProposalAttachment
from ..models import ProposalCollaborator
from ..models import ProposalCommentSummary
from ..models import ProposalEditorPresence
from ..models import ProposalGenderIssue
from ..models import ProposalMethodology
from ..models import ProposalOutputOutcome
from ..models import ProposalProponent
from ..models import ProposalSDG
from ..models import ProposalSectionComment
from ..models import ProposalSpecificObjective
from ..models import ProposalThrust
from accounts.decorators import faculty_like_required, admin_required
from .constants import GENDER_ISSUE_LIST, SDG_LIST, STEP_LABELS, THRUST_LIST, TOTAL_STEPS, User
from .dynamic_fields import (
    dependency_parent_value as _dependency_parent_value,
    dynamic_field_blocks_submission as _dynamic_field_blocks_submission,
    dynamic_parent_values_from_post as _dynamic_parent_values_from_post,
    dynamic_parent_values_from_saved as _dynamic_parent_values_from_saved,
)
from .helpers import _strip_phase_prefix, _to_int, _to_roman
from .permissions import _can_edit, _can_review, _can_view_proposal, _ensure_open_review_round, _get_reviewer_role, _role_has_capability


def mark_step_completed(proposal, step_no):
    completed = set(proposal.completed_steps or [])
    skipped = set(proposal.skipped_steps or [])
    completed.add(step_no)
    skipped.discard(step_no)
    proposal.completed_steps = sorted(completed)
    proposal.skipped_steps = sorted(skipped)
    messages.success(request, "Step saved successfully.")


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


def is_step_complete(proposal, step):
    if step == 1:
        if not proposal.extension_type or not proposal.scope_type:
            return False
        if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"] and not (proposal.research_title or "").strip():
            return False
        return True

    if step == 2:
        if not (proposal.title or "").strip():
            return False
        if proposal.scope_type == "PROGRAM":
            return proposal.program_projects.exists()
        return True

    if step == 3:
        return proposal.proponents.exists()

    if step == 4:
        return bool((proposal.implementing_agency or "").strip())

    if step == 5:
        return proposal.beneficiaries_count is not None and bool((proposal.beneficiaries_who or "").strip())

    if step == 6:
        return proposal.sdg_links.exists() or proposal.thrust_links.exists()

    if step == 7:
        return bool((proposal.budgetary_requirement or "").strip())

    if step == 8:
        sex_total = (proposal.sex_male or 0) + (proposal.sex_female or 0)
        gender_total = (
            (proposal.g_lesbian or 0)
            + (proposal.g_gay or 0)
            + (proposal.g_bisexual or 0)
            + (proposal.g_transgender or 0)
            + (proposal.g_straight or 0)
            + (proposal.g_others or 0)
        )
        return sex_total > 0 and sex_total == gender_total

    if step == 9:
        issues = proposal.gender_issue_links.all()
        if not issues.exists():
            return False
        others = issues.filter(issue_key="others").first()
        if others and not (others.other_text or "").strip():
            return False
        return True

    if step == 10:
        return bool((proposal.extension_venue or "").strip())

    if step == 11:
        return bool((proposal.rationale_background or "").strip())

    if step == 12:
        return bool((proposal.significance or "").strip())

    if step == 13:
        if not (proposal.general_objective or "").strip():
            return False

        if proposal.scope_type == "PROGRAM":
            projects = proposal.program_projects.all()
            if not projects.exists():
                return False
            for prj in projects:
                if not proposal.specific_objectives.filter(program_project=prj).exists():
                    return False
            return True

        return proposal.specific_objectives.filter(program_project__isnull=True).exists()

    if step == 14:
        return proposal.methodologies.exists()

    if step == 15:
        return proposal.output_outcomes.exists()

    if step == 16:
        return bool(proposal.work_plan_file) and bool(proposal.gantt_chart_file)

    if step == 17:
        return bool(proposal.funding_file)

    if step == 18:
        if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]:
            return bool(proposal.research_abstract_file)
        return True

    if step == 19:
        if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]:
            return bool(proposal.certificate_of_completion_file)
        return True

    return _is_dynamic_step_complete(proposal, step)


def _is_dynamic_step_complete(proposal, step):
    forms = DynamicFormTemplate.objects.filter(
        is_active=True,
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step=step,
        blocks_proposal_submission=True,
    ).prefetch_related("fields")
    
    if not forms.exists():
        return True

    responses = {
        res.form_id: res
        for res in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers")
    }

    saved_values = _dynamic_parent_values_from_saved(proposal)

    def _blocking_field_without_value(form, field, answer):
        parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
        if not _dynamic_field_blocks_submission(form, field, parent_value):
            return False
        return not answer or not answer.has_value

    for form in forms:
        res = responses.get(form.id)
        answer_map = {ans.field_id: ans for ans in res.answers.all()} if res else {}

        for field in form.fields.all():
            if _blocking_field_without_value(form, field, answer_map.get(field.id)):
                return False
    return True


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


def _update_creator_role(proposal):
    creator_pp = proposal.proponents.filter(user=proposal.created_by).first()
    if not creator_pp:
        return

    if proposal.scope_type == "PROGRAM":
        creator_pp.role = "Program Leader"
    elif proposal.scope_type == "PROJECT":
        creator_pp.role = "Project Leader"
    else:
        creator_pp.role = "Proponent"

    creator_pp.save(update_fields=["role"])


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


def _dynamic_forms_for_proposal_step(step):
    return (
        DynamicFormTemplate.objects.filter(
            is_active=True,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step,
        )
        .prefetch_related("fields")
        .order_by("name")
    )


def _attach_dynamic_forms_to_context(ctx, proposal, step):
    forms = list(_dynamic_forms_for_proposal_step(step))
    if not forms:
        ctx["dynamic_forms"] = []
        ctx["step_fields"] = {}
        return []

    responses = {
        response.form_id: response
        for response in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers", "answers__field")
    }

    step_fields = {}
    for form in forms:
        for field in form.fields.all():
            step_fields[field.field_key] = field

    ctx["step_fields"] = step_fields

    hardcoded_keys_by_step = {
        1: {"extension_type", "scope_type", "research_title"},
        2: {"title"},
        4: {"implementing_agency"},
        5: {"beneficiaries_count", "who_beneficiaries", "beneficiaries_who"},
        7: {"budgetary_requirement"},
        10: {"extension_venue", "estimated_month", "estimated_year"},
        11: {"rationale_background"},
        12: {"significance"},
        13: {"general_objective"},
    }
    exclude_keys = hardcoded_keys_by_step.get(step, set())

    for form in forms:
        response = responses.get(form.id)
        answer_by_field = {}
        if response:
            answer_by_field = {answer.field_id: answer for answer in response.answers.all()}
        form.response = response
        
        all_fields = list(form.fields.all())
        for field in all_fields:
            answer = answer_by_field.get(field.id)
            field.answer = answer
            field.answer_value = getattr(answer, "value", "") if answer else ""
            field.answer_file = getattr(answer, "file", None) if answer else None

        form.fields_to_render = [f for f in all_fields if f.field_key not in exclude_keys]

    ctx["dynamic_forms"] = forms
    return forms


def _save_dynamic_form_answers(proposal, step, user, request):
    """Save admin-built dynamic fields attached to the current wizard step.

    Returns a list of missing required field labels. Values are saved even when
    some required fields are still empty so proponents can draft gradually.
    Required fields whose ``depends_on`` condition is not met are skipped:
    the user never saw them, so they cannot be missing.
    """
    forms = list(_dynamic_forms_for_proposal_step(step))
    missing = []
    post_values = _dynamic_parent_values_from_post(forms, request)

    for form in forms:
        response, _ = DynamicFormResponse.objects.get_or_create(
            form=form,
            proposal=proposal,
            defaults={"submitted_by": user},
        )
        if response.submitted_by_id is None and user.is_authenticated:
            response.submitted_by = user
            response.save(update_fields=["submitted_by", "updated_at"])

        for field in form.fields.all():
            input_name = f"dynamic_field_{field.id}"
            answer, _ = DynamicFormAnswer.objects.get_or_create(
                response=response,
                field=field,
            )

            if field.field_type == DynamicFormField.FieldType.FILE:
                uploaded = request.FILES.get(input_name)
                if uploaded:
                    answer.file = uploaded
                # Keep existing file when no new file is uploaded.
                answer.value = ""
            elif field.field_type == DynamicFormField.FieldType.CHECKBOX:
                answer.value = "Yes" if request.POST.get(input_name) == "on" else ""
            else:
                answer.value = (request.POST.get(input_name) or "").strip()

            answer.save()

            parent_value = _dependency_parent_value(proposal, field.depends_on_key, post_values=post_values)
            if not answer.has_value and _dynamic_field_blocks_submission(form, field, parent_value):
                missing.append(f"{form.name}: {field.label}")

    return missing


def _proposal_dynamic_requirements_missing(proposal):
    """Return missing required admin-built proposal fields across all wizard steps."""
    forms = list(
        DynamicFormTemplate.objects.filter(
            is_active=True,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            blocks_proposal_submission=True,
        )
        .exclude(proposal_wizard_step__isnull=True)
        .prefetch_related("fields")
    )
    if not forms:
        return []

    responses = {
        response.form_id: response
        for response in DynamicFormResponse.objects.filter(
            proposal=proposal,
            form__in=forms,
        ).prefetch_related("answers")
    }

    saved_values = _dynamic_parent_values_from_saved(proposal)

    missing = []
    for form in forms:
        response = responses.get(form.id)
        answer_map = {}
        if response:
            answer_map = {answer.field_id: answer for answer in response.answers.all()}

        for field in form.fields.all():
            if not field.required:
                continue
            parent_value = _dependency_parent_value(proposal, field.depends_on_key, saved_values=saved_values)
            answer = answer_map.get(field.id)
            if not _dynamic_field_blocks_submission(form, field, parent_value):
                continue
            if not answer or not answer.has_value:
                step_label = f"Step {form.proposal_wizard_step}" if form.proposal_wizard_step else "Proposal wizard"
                missing.append(f"{step_label} — {form.name}: {field.label}")

    return missing


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

    if step == 6:
        ctx["sdgs"] = SDG_LIST
        ctx["thrusts"] = THRUST_LIST
        sdg_links = proposal.sdg_links.all()
        thrust_links = proposal.thrust_links.all()
        ctx["selected_sdg_codes"] = set(sdg_links.values_list("sdg_code", flat=True))
        ctx["selected_thrust_names"] = set(thrust_links.values_list("thrust_name", flat=True))
        ctx["sdg_explanations"] = {item.sdg_code: item.explanation for item in sdg_links}
        ctx["thrust_explanations"] = {item.thrust_name: item.explanation for item in thrust_links}

    if step == 7:
        ctx["budgetary_requirement"] = proposal.budgetary_requirement or ""

    if step == 8:
        ctx["sex_total"] = (proposal.sex_male or 0) + (proposal.sex_female or 0)
        ctx["gender_total"] = (
            (proposal.g_lesbian or 0)
            + (proposal.g_gay or 0)
            + (proposal.g_bisexual or 0)
            + (proposal.g_transgender or 0)
            + (proposal.g_straight or 0)
            + (proposal.g_others or 0)
        )

    if step == 9:
        ctx["gender_issues"] = GENDER_ISSUE_LIST
        ctx["selected_gender_issue_keys"] = set(
            proposal.gender_issue_links.values_list("issue_key", flat=True)
        )
        others_item = proposal.gender_issue_links.filter(issue_key="others").first()
        ctx["gender_issue_other_text"] = others_item.other_text if others_item else ""

    if step == 10:
        ctx["estimated_month"] = proposal.estimated_month or ""
        ctx["estimated_year"] = proposal.estimated_year or ""
        ctx["extension_venue"] = proposal.extension_venue or ""
        ctx["month_choices"] = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

    if step == 11:
        ctx["rationale_background"] = proposal.rationale_background or ""

    if step == 12:
        ctx["significance"] = proposal.significance or ""

    if step == 13:
        ctx["general_objective"] = proposal.general_objective or ""
        if proposal.scope_type == "PROGRAM":
            projects = proposal.program_projects.all().order_by("order", "id")
            ctx["program_projects"] = projects
            ctx["project_objectives_map"] = {
                prj.id: list(
                    proposal.specific_objectives.filter(program_project=prj)
                    .values_list("objective", flat=True)
                )
                for prj in projects
            }
        else:
            ctx["specific_objectives"] = list(
                proposal.specific_objectives.filter(program_project__isnull=True)
                .values_list("objective", flat=True)
            )

    if step == 14:
        ctx["methodologies"] = list(proposal.methodologies.values_list("item", flat=True))

    if step == 15:
        ctx["output_outcomes"] = list(proposal.output_outcomes.values_list("item", flat=True))

    if step == 16:
        ctx["existing_attachments"] = proposal.attachments.filter(
            category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES
        ).order_by("id")
        if proposal.scope_type == "PROGRAM":
            ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")

    if step == 17:
        ctx["existing_funding_attachments"] = proposal.attachments.filter(
            category=ProposalAttachment.Category.OTHER
        ).order_by("id")

    if step == 18:
        ctx["requires_abstract"] = proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]

    if step == 19:
        ctx["requires_certificate"] = proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]
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

    step = normalize_wizard_step(max(1, min(step, TOTAL_STEPS)))
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

    template = f"services/wizard/step_{step}.html"
    from django.template.loader import select_template
    try:
        select_template([template])
    except Exception:
        template = "services/wizard/step_dynamic.html"

    if request.method == "GET":
        _add_step_context_for_get(ctx, proposal, step)
        return render(request, template, ctx)

    if action == "save_comment":
        return _handle_save_comment(
            request, proposal, step, current_round, reviewer_role
        )

    if step == 1:
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
        remove_ids = request.POST.getlist("remove_proponent_ids")
        if remove_ids:
            ProposalProponent.objects.filter(
                proposal=proposal,
                id__in=remove_ids,
            ).exclude(user=proposal.created_by).delete()

        add_user_id = (request.POST.get("add_user_id") or "").strip()
        if add_user_id.isdigit():
            user_obj = User.objects.filter(id=int(add_user_id)).first()
            if user_obj:
                prof = getattr(user_obj, "profile", None)
                ProposalProponent.objects.get_or_create(
                    proposal=proposal,
                    user=user_obj,
                    defaults={
                        "full_name": getattr(prof, "full_name", user_obj.username),
                        "email": user_obj.email or "",
                        "role": "Proponent",
                        "designation": "",
                        "specialization": "",
                        "cp_number": "",
                    },
                )

        for p in proposal.proponents.all():
            prefix = f"p_{p.id}_"
            p.designation = request.POST.get(prefix + "designation", p.designation)
            p.specialization = request.POST.get(prefix + "specialization", p.specialization)
            p.cp_number = request.POST.get(prefix + "cp_number", p.cp_number)
            p.email = request.POST.get(prefix + "email", p.email)
            p.save(update_fields=["designation", "specialization", "cp_number", "email"])

        _update_creator_role(proposal)

        if proposal.scope_type == "PROGRAM":
            proposal.proponents.exclude(user=proposal.created_by).update(role="Proponent")

            for prj in proposal.program_projects.all():
                uid = (request.POST.get(f"project_leader_{prj.id}") or "").strip()
                if uid.isdigit():
                    prj.leader_user_id = int(uid)
                    prj.save(update_fields=["leader_user"])

                    pp = proposal.proponents.filter(user_id=int(uid)).first()
                    if pp and pp.user_id != proposal.created_by_id:
                        pp.role = "Project Leader"
                        pp.save(update_fields=["role"])
                else:
                    prj.leader_user = None
                    prj.save(update_fields=["leader_user"])

        if action in ("add_member", "save_members"):
            if is_step_complete(proposal, step):
                mark_step_completed(proposal, step)
            else:
                unmark_step_completed(proposal, step)

            proposal.save(update_fields=["completed_steps", "skipped_steps"])
            messages.success(request, "Members updated.")
            return redirect("proposal_wizard", proposal_id=proposal.id, step=3)

    elif step == 4:
        proposal.implementing_agency = (request.POST.get("implementing_agency") or "").strip()
        proposal.save(update_fields=["implementing_agency"])

    elif step == 5:
        raw_beneficiaries = request.POST.get("beneficiaries_count")
        proposal.beneficiaries_count = _to_int(raw_beneficiaries, default=None)
        if proposal.beneficiaries_count == 0 and (raw_beneficiaries or "").strip() == "":
            proposal.beneficiaries_count = None
        proposal.beneficiaries_who = (request.POST.get("beneficiaries_who") or "").strip()
        proposal.save(update_fields=["beneficiaries_count", "beneficiaries_who"])

    elif step == 6:
        sdg_codes = request.POST.getlist("sdg_codes")
        thrust_names = request.POST.getlist("thrust_names")

        ProposalSDG.objects.filter(proposal=proposal).delete()
        ProposalThrust.objects.filter(proposal=proposal).delete()

        for code in sdg_codes:
            code = (code or "").strip()
            if code:
                explanation = (request.POST.get(f"sdg_explanation_{code}") or "").strip()
                ProposalSDG.objects.create(
                    proposal=proposal,
                    sdg_code=code,
                    explanation=explanation,
                )

        for name in thrust_names:
            name = (name or "").strip()
            if name:
                explanation = (request.POST.get(f"thrust_explanation_{name}") or "").strip()
                ProposalThrust.objects.create(
                    proposal=proposal,
                    thrust_name=name,
                    explanation=explanation,
                )

    elif step == 7:
        proposal.budgetary_requirement = (request.POST.get("budgetary_requirement") or "").strip()
        proposal.save(update_fields=["budgetary_requirement"])

    elif step == 8:
        sex_male = _to_int(request.POST.get("sex_male"))
        sex_female = _to_int(request.POST.get("sex_female"))
        g_lesbian = _to_int(request.POST.get("g_lesbian"))
        g_gay = _to_int(request.POST.get("g_gay"))
        g_bisexual = _to_int(request.POST.get("g_bisexual"))
        g_transgender = _to_int(request.POST.get("g_transgender"))
        g_straight = _to_int(request.POST.get("g_straight"))
        g_others = _to_int(request.POST.get("g_others"))

        sex_total = sex_male + sex_female
        gender_total = g_lesbian + g_gay + g_bisexual + g_transgender + g_straight + g_others

        proposal.sex_male = sex_male
        proposal.sex_female = sex_female
        proposal.g_lesbian = g_lesbian
        proposal.g_gay = g_gay
        proposal.g_bisexual = g_bisexual
        proposal.g_transgender = g_transgender
        proposal.g_straight = g_straight
        proposal.g_others = g_others
        proposal.save(update_fields=[
            "sex_male", "sex_female", "g_lesbian", "g_gay",
            "g_bisexual", "g_transgender", "g_straight", "g_others",
        ])

        if action == "next" and sex_total != gender_total:
            messages.error(request, "Sex total and Gender total must be the same before you can proceed.")
            return redirect("proposal_wizard", proposal_id=proposal.id, step=8)

    elif step == 9:
        selected_keys = request.POST.getlist("gender_issue_keys")
        other_text = (request.POST.get("gender_issue_other_text") or "").strip()

        ProposalGenderIssue.objects.filter(proposal=proposal).delete()
        label_map = dict(GENDER_ISSUE_LIST)

        for key in selected_keys:
            key = (key or "").strip()
            if not key or key not in label_map:
                continue

            ProposalGenderIssue.objects.create(
                proposal=proposal,
                issue_key=key,
                issue_label=label_map[key],
                other_text=other_text if key == "others" else "",
            )

    elif step == 10:
        estimated_month = (request.POST.get("estimated_month") or "").strip()
        estimated_year_raw = (request.POST.get("estimated_year") or "").strip()
        extension_venue = (request.POST.get("extension_venue") or "").strip()

        proposal.estimated_month = estimated_month or ""
        proposal.estimated_year = int(estimated_year_raw) if estimated_year_raw.isdigit() else None
        proposal.extension_venue = extension_venue
        proposal.save(update_fields=["estimated_month", "estimated_year", "extension_venue"])

    elif step == 11:
        proposal.rationale_background = (request.POST.get("rationale_background") or "").strip()
        proposal.save(update_fields=["rationale_background"])

    elif step == 12:
        proposal.significance = (request.POST.get("significance") or "").strip()
        proposal.save(update_fields=["significance"])

    elif step == 13:
        proposal.general_objective = (request.POST.get("general_objective") or "").strip()
        proposal.save(update_fields=["general_objective"])

        proposal.specific_objectives.all().delete()

        if proposal.scope_type == "PROGRAM":
            for prj in proposal.program_projects.all():
                objectives = request.POST.getlist(f"specific_objectives_{prj.id}[]")
                for obj in objectives:
                    obj = (obj or "").strip()
                    if obj:
                        ProposalSpecificObjective.objects.create(
                            proposal=proposal,
                            program_project=prj,
                            objective=obj,
                        )
        else:
            objectives = request.POST.getlist("specific_objectives[]")
            for obj in objectives:
                obj = (obj or "").strip()
                if obj:
                    ProposalSpecificObjective.objects.create(
                        proposal=proposal,
                        program_project=None,
                        objective=obj,
                    )

    elif step == 14:
        proposal.methodologies.all().delete()
        for item in request.POST.getlist("methodologies[]"):
            item = (item or "").strip()
            if item:
                ProposalMethodology.objects.create(proposal=proposal, item=item)

    elif step == 15:
        proposal.output_outcomes.all().delete()
        for item in request.POST.getlist("output_outcomes[]"):
            item = (item or "").strip()
            if item:
                ProposalOutputOutcome.objects.create(proposal=proposal, item=item)

    elif step == 16:
        remove_attachment_ids = request.POST.getlist("remove_attachment_ids")
        if remove_attachment_ids:
            ProposalAttachment.objects.filter(
                proposal=proposal,
                category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES,
                id__in=remove_attachment_ids,
            ).delete()

        changed_fields = []
        if request.FILES.get("work_plan_file"):
            proposal.work_plan_file = request.FILES["work_plan_file"]
            changed_fields.append("work_plan_file")

        if request.FILES.get("gantt_chart_file"):
            proposal.gantt_chart_file = request.FILES["gantt_chart_file"]
            changed_fields.append("gantt_chart_file")

        if changed_fields:
            proposal.save(update_fields=changed_fields)

        for f in request.FILES.getlist("attachment_files"):
            if f:
                ProposalAttachment.objects.create(
                    proposal=proposal,
                    file=f,
                    category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES,
                    label=getattr(f, "name", ""),
                )

    elif step == 17:
        if request.FILES.get("funding_file"):
            proposal.funding_file = request.FILES["funding_file"]
            proposal.save(update_fields=["funding_file"])

    elif step == 18:
        if request.FILES.get("research_abstract_file"):
            proposal.research_abstract_file = request.FILES["research_abstract_file"]
            proposal.save(update_fields=["research_abstract_file"])

    elif step == 19:
        if request.FILES.get("certificate_of_completion_file"):
            proposal.certificate_of_completion_file = request.FILES["certificate_of_completion_file"]
            proposal.save(update_fields=["certificate_of_completion_file"])

    dynamic_missing = _save_dynamic_form_answers(proposal, step, request.user, request)
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
