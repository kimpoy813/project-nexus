"""Flow-specific wizard step logic.

The office's two proposal forms each get their own flow:

- RESEARCH: research-based (faculty/student) proposals answer the
  **Extension Proposal** form. Steps follow its sections I-XVIII plus the
  research-only uploads.
- TRAINING: community-based and request-based proposals answer the
  **Extension Training Design** form.

This module holds the per-flow completion rules, GET context builders, and
POST save handlers; ``wizard.py`` dispatches into it based on the proposal's
extension type.
"""

from django.contrib import messages
from django.shortcuts import redirect

from ..models import (
    ProposalAttachment,
    ProposalGenderIssue,
    ProposalMethodology,
    ProposalOutputOutcome,
    ProposalSDG,
    ProposalSpecificObjective,
    ProposalThrust,
)
from .constants import GENDER_ISSUE_LIST, SDG_LIST, THRUST_LIST
from .helpers import _to_int


def _participants_profile_complete(proposal):
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


def _gender_issues_complete(proposal):
    issues = proposal.gender_issue_links.all()
    if not issues.exists():
        return False
    others = issues.filter(issue_key="others").first()
    if others and not (others.other_text or "").strip():
        return False
    return True


def _objectives_complete(proposal):
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


def _is_research_step_complete(proposal, step):
    """Completion rules for the Extension Proposal flow (research-based)."""
    if step == 5:
        return proposal.beneficiaries_count is not None and bool((proposal.beneficiaries_who or "").strip())

    if step == 6:
        return proposal.sdg_links.exists()

    if step == 7:
        return proposal.thrust_links.exists()

    if step == 8:
        return bool((proposal.budgetary_requirement or "").strip())

    if step == 9:
        return _participants_profile_complete(proposal)

    if step == 10:
        return _gender_issues_complete(proposal)

    if step == 11:
        return bool((proposal.extension_venue or "").strip())

    if step == 12:
        return bool((proposal.rationale_background or "").strip())

    if step == 13:
        return bool((proposal.significance or "").strip())

    if step == 14:
        return _objectives_complete(proposal)

    if step == 15:
        return proposal.methodologies.exists()

    if step == 16:
        return proposal.output_outcomes.exists()

    if step == 17:
        return bool(proposal.work_plan_file) and bool(proposal.gantt_chart_file)

    if step == 18:
        return bool(proposal.funding_file)

    if step == 19:
        return bool(proposal.monitoring_eval_file) or bool((proposal.monitoring_eval or "").strip())

    if step == 20:
        return bool(proposal.research_abstract_file)

    if step == 21:
        return bool(proposal.certificate_of_completion_file)

    return _is_dynamic_step_complete(proposal, step)


def _is_training_step_complete(proposal, step):
    """Completion rules for the Training Design flow (community/request-based)."""
    if step == 5:
        # Coordinating Units: names of the unit/beneficiaries; a count is not
        # part of the Training Design form.
        return bool((proposal.beneficiaries_who or "").strip())

    if step == 6:
        return proposal.sdg_links.exists()

    if step == 7:
        return proposal.thrust_links.exists()

    if step == 8:
        return bool((proposal.duration or "").strip())

    if step == 9:
        return bool((proposal.extension_venue or "").strip())

    if step == 10:
        return bool((proposal.funding_source or "").strip())

    if step == 11:
        return bool((proposal.budgetary_requirement or "").strip())

    if step == 12:
        return _participants_profile_complete(proposal)

    if step == 13:
        return _gender_issues_complete(proposal)

    if step == 14:
        return bool((proposal.rationale_background or "").strip())

    if step == 15:
        return _objectives_complete(proposal)

    if step == 16:
        return proposal.methodologies.exists()

    if step == 17:
        return bool(proposal.work_plan_file)

    if step == 18:
        return bool(proposal.funding_file)

    if step == 19:
        return proposal.output_outcomes.exists()

    return _is_dynamic_step_complete(proposal, step)




def _add_sdg_context(ctx, proposal):
    ctx["sdgs"] = SDG_LIST
    sdg_links = proposal.sdg_links.all()
    ctx["selected_sdg_codes"] = set(sdg_links.values_list("sdg_code", flat=True))
    ctx["sdg_explanations"] = {item.sdg_code: item.explanation for item in sdg_links}


def _add_thrust_context(ctx, proposal):
    ctx["thrusts"] = THRUST_LIST
    thrust_links = proposal.thrust_links.all()
    ctx["selected_thrust_names"] = set(thrust_links.values_list("thrust_name", flat=True))
    ctx["thrust_explanations"] = {item.thrust_name: item.explanation for item in thrust_links}


def _add_participants_context(ctx, proposal):
    ctx["sex_total"] = (proposal.sex_male or 0) + (proposal.sex_female or 0)
    ctx["gender_total"] = (
        (proposal.g_lesbian or 0)
        + (proposal.g_gay or 0)
        + (proposal.g_bisexual or 0)
        + (proposal.g_transgender or 0)
        + (proposal.g_straight or 0)
        + (proposal.g_others or 0)
    )


def _add_gender_issues_context(ctx, proposal):
    ctx["gender_issues"] = GENDER_ISSUE_LIST
    ctx["selected_gender_issue_keys"] = set(
        proposal.gender_issue_links.values_list("issue_key", flat=True)
    )
    others_item = proposal.gender_issue_links.filter(issue_key="others").first()
    ctx["gender_issue_other_text"] = others_item.other_text if others_item else ""


def _add_venue_context(ctx, proposal):
    ctx["extension_venue"] = proposal.extension_venue or ""


def _add_date_venue_context(ctx, proposal):
    ctx["estimated_month"] = proposal.estimated_month or ""
    ctx["estimated_year"] = proposal.estimated_year or ""
    ctx["extension_venue"] = proposal.extension_venue or ""
    ctx["month_choices"] = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]


def _add_rationale_context(ctx, proposal):
    ctx["rationale_background"] = proposal.rationale_background or ""


def _add_objectives_context(ctx, proposal):
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


def _add_methodology_context(ctx, proposal):
    ctx["methodologies"] = list(proposal.methodologies.values_list("item", flat=True))


def _add_output_context(ctx, proposal):
    ctx["output_outcomes"] = list(proposal.output_outcomes.values_list("item", flat=True))


def _add_research_step_context_for_get(ctx, proposal, step):
    """Per-step GET data for the Extension Proposal flow (research-based)."""
    if step == 6:
        _add_sdg_context(ctx, proposal)

    if step == 7:
        _add_thrust_context(ctx, proposal)

    if step == 8:
        ctx["budgetary_requirement"] = proposal.budgetary_requirement or ""

    if step == 9:
        _add_participants_context(ctx, proposal)

    if step == 10:
        _add_gender_issues_context(ctx, proposal)

    if step == 11:
        _add_date_venue_context(ctx, proposal)

    if step == 12:
        _add_rationale_context(ctx, proposal)

    if step == 13:
        ctx["significance"] = proposal.significance or ""

    if step == 14:
        _add_objectives_context(ctx, proposal)

    if step == 15:
        _add_methodology_context(ctx, proposal)

    if step == 16:
        _add_output_context(ctx, proposal)

    if step == 17:
        ctx["existing_attachments"] = proposal.attachments.filter(
            category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES
        ).order_by("id")
        if proposal.scope_type == "PROGRAM":
            ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")

    if step == 18:
        ctx["existing_funding_attachments"] = proposal.attachments.filter(
            category=ProposalAttachment.Category.OTHER
        ).order_by("id")

    if step == 19:
        ctx["monitoring_eval"] = proposal.monitoring_eval or ""

    if step == 20:
        ctx["requires_abstract"] = proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]

    if step == 21:
        ctx["requires_certificate"] = proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]
    return ctx


def _add_training_step_context_for_get(ctx, proposal, step):
    """Per-step GET data for the Training Design flow (community/request-based)."""
    if step == 6:
        _add_sdg_context(ctx, proposal)

    if step == 7:
        _add_thrust_context(ctx, proposal)

    if step == 9:
        _add_venue_context(ctx, proposal)

    if step == 11:
        ctx["budgetary_requirement"] = proposal.budgetary_requirement or ""

    if step == 12:
        _add_participants_context(ctx, proposal)

    if step == 13:
        _add_gender_issues_context(ctx, proposal)

    if step == 14:
        _add_rationale_context(ctx, proposal)

    if step == 15:
        _add_objectives_context(ctx, proposal)

    if step == 16:
        _add_methodology_context(ctx, proposal)

    if step == 17:
        ctx["existing_attachments"] = proposal.attachments.filter(
            category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES
        ).order_by("id")
        if proposal.scope_type == "PROGRAM":
            ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")

    if step == 18:
        ctx["existing_funding_attachments"] = proposal.attachments.filter(
            category=ProposalAttachment.Category.OTHER
        ).order_by("id")

    if step == 19:
        _add_output_context(ctx, proposal)
    return ctx




def _save_sdg_links(proposal, request):
    """Replace the proposal's SDG links from the step form's chips."""
    ProposalSDG.objects.filter(proposal=proposal).delete()
    for code in request.POST.getlist("sdg_codes"):
        code = (code or "").strip()
        if code:
            explanation = (request.POST.get(f"sdg_explanation_{code}") or "").strip()
            ProposalSDG.objects.create(
                proposal=proposal,
                sdg_code=code,
                explanation=explanation,
            )


def _save_thrust_links(proposal, request):
    """Replace the proposal's extension thrust links from the step form."""
    ProposalThrust.objects.filter(proposal=proposal).delete()
    for name in request.POST.getlist("thrust_names"):
        name = (name or "").strip()
        if name:
            explanation = (request.POST.get(f"thrust_explanation_{name}") or "").strip()
            ProposalThrust.objects.create(
                proposal=proposal,
                thrust_name=name,
                explanation=explanation,
            )


def _save_participants_profile(proposal, request):
    """Store the sex-disaggregated participants table."""
    sex_male = _to_int(request.POST.get("sex_male"))
    sex_female = _to_int(request.POST.get("sex_female"))
    g_lesbian = _to_int(request.POST.get("g_lesbian"))
    g_gay = _to_int(request.POST.get("g_gay"))
    g_bisexual = _to_int(request.POST.get("g_bisexual"))
    g_transgender = _to_int(request.POST.get("g_transgender"))
    g_straight = _to_int(request.POST.get("g_straight"))
    g_others = _to_int(request.POST.get("g_others"))

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
    return (sex_male + sex_female), (g_lesbian + g_gay + g_bisexual + g_transgender + g_straight + g_others)


def _save_gender_issues(proposal, request):
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


def _save_objectives(proposal, request):
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


def _save_methodologies(proposal, request):
    proposal.methodologies.all().delete()
    for item in request.POST.getlist("methodologies[]"):
        item = (item or "").strip()
        if item:
            ProposalMethodology.objects.create(proposal=proposal, item=item)


def _save_output_outcomes(proposal, request):
    proposal.output_outcomes.all().delete()
    for item in request.POST.getlist("output_outcomes[]"):
        item = (item or "").strip()
        if item:
            ProposalOutputOutcome.objects.create(proposal=proposal, item=item)


def _save_rationale(proposal, request):
    proposal.rationale_background = (request.POST.get("rationale_background") or "").strip()
    proposal.save(update_fields=["rationale_background"])


def _save_details_of_activities_files(proposal, request, *, include_gantt=True):
    """Store the Details/Schedule of Activities uploads and extra attachments."""
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

    if include_gantt and request.FILES.get("gantt_chart_file"):
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


def _save_research_step(proposal, step, request, action):
    """Save one step of the Extension Proposal flow (research-based).

    Returns a redirect when the step asked to stop (validation), else ``None``
    so the caller finishes the shared bookkeeping.
    """
    if step == 5:
        raw_beneficiaries = request.POST.get("beneficiaries_count")
        proposal.beneficiaries_count = _to_int(raw_beneficiaries, default=None)
        if proposal.beneficiaries_count == 0 and (raw_beneficiaries or "").strip() == "":
            proposal.beneficiaries_count = None
        proposal.beneficiaries_who = (request.POST.get("beneficiaries_who") or "").strip()
        proposal.save(update_fields=["beneficiaries_count", "beneficiaries_who"])

    elif step == 6:
        _save_sdg_links(proposal, request)

    elif step == 7:
        _save_thrust_links(proposal, request)

    elif step == 8:
        proposal.budgetary_requirement = (request.POST.get("budgetary_requirement") or "").strip()
        proposal.save(update_fields=["budgetary_requirement"])

    elif step == 9:
        sex_total, gender_total = _save_participants_profile(proposal, request)
        if action == "next" and sex_total != gender_total:
            messages.error(request, "Sex total and Gender total must be the same before you can proceed.")
            return redirect("proposal_wizard", proposal_id=proposal.id, step=9)

    elif step == 10:
        _save_gender_issues(proposal, request)

    elif step == 11:
        estimated_month = (request.POST.get("estimated_month") or "").strip()
        estimated_year_raw = (request.POST.get("estimated_year") or "").strip()
        extension_venue = (request.POST.get("extension_venue") or "").strip()

        proposal.estimated_month = estimated_month or ""
        proposal.estimated_year = int(estimated_year_raw) if estimated_year_raw.isdigit() else None
        proposal.extension_venue = extension_venue
        proposal.save(update_fields=["estimated_month", "estimated_year", "extension_venue"])

    elif step == 12:
        _save_rationale(proposal, request)

    elif step == 13:
        proposal.significance = (request.POST.get("significance") or "").strip()
        proposal.save(update_fields=["significance"])

    elif step == 14:
        _save_objectives(proposal, request)

    elif step == 15:
        _save_methodologies(proposal, request)

    elif step == 16:
        _save_output_outcomes(proposal, request)

    elif step == 17:
        _save_details_of_activities_files(proposal, request, include_gantt=True)

    elif step == 18:
        if request.FILES.get("funding_file"):
            proposal.funding_file = request.FILES["funding_file"]
            proposal.save(update_fields=["funding_file"])

    elif step == 19:
        proposal.monitoring_eval = (request.POST.get("monitoring_eval") or "").strip()
        if request.FILES.get("monitoring_eval_file"):
            proposal.monitoring_eval_file = request.FILES["monitoring_eval_file"]
            proposal.save(update_fields=["monitoring_eval", "monitoring_eval_file"])
        else:
            proposal.save(update_fields=["monitoring_eval"])

    elif step == 20:
        if request.FILES.get("research_abstract_file"):
            proposal.research_abstract_file = request.FILES["research_abstract_file"]
            proposal.save(update_fields=["research_abstract_file"])

    elif step == 21:
        if request.FILES.get("certificate_of_completion_file"):
            proposal.certificate_of_completion_file = request.FILES["certificate_of_completion_file"]
            proposal.save(update_fields=["certificate_of_completion_file"])

    return None


def _save_training_step(proposal, step, request, action):
    """Save one step of the Training Design flow (community/request-based).

    Returns a redirect when the step asked to stop (validation), else ``None``
    so the caller finishes the shared bookkeeping.
    """
    if step == 5:
        # Coordinating Units. The Training Design form lists units, not a
        # headcount, but a count typed in is still stored.
        raw_beneficiaries = request.POST.get("beneficiaries_count")
        proposal.beneficiaries_count = _to_int(raw_beneficiaries, default=None)
        if proposal.beneficiaries_count == 0 and (raw_beneficiaries or "").strip() == "":
            proposal.beneficiaries_count = None
        proposal.beneficiaries_who = (request.POST.get("beneficiaries_who") or "").strip()
        proposal.save(update_fields=["beneficiaries_count", "beneficiaries_who"])

    elif step == 6:
        _save_sdg_links(proposal, request)

    elif step == 7:
        _save_thrust_links(proposal, request)

    elif step == 8:
        proposal.duration = (request.POST.get("duration") or "").strip()
        proposal.save(update_fields=["duration"])

    elif step == 9:
        proposal.extension_venue = (request.POST.get("extension_venue") or "").strip()
        proposal.save(update_fields=["extension_venue"])

    elif step == 10:
        proposal.funding_source = (request.POST.get("funding_source") or "").strip()
        proposal.save(update_fields=["funding_source"])

    elif step == 11:
        proposal.budgetary_requirement = (request.POST.get("budgetary_requirement") or "").strip()
        proposal.save(update_fields=["budgetary_requirement"])

    elif step == 12:
        sex_total, gender_total = _save_participants_profile(proposal, request)
        if action == "next" and sex_total != gender_total:
            messages.error(request, "Sex total and Gender total must be the same before you can proceed.")
            return redirect("proposal_wizard", proposal_id=proposal.id, step=12)

    elif step == 13:
        _save_gender_issues(proposal, request)

    elif step == 14:
        _save_rationale(proposal, request)

    elif step == 15:
        _save_objectives(proposal, request)

    elif step == 16:
        _save_methodologies(proposal, request)

    elif step == 17:
        # Schedule of Activities: the work plan table (no Gantt chart on the
        # Training Design form).
        _save_details_of_activities_files(proposal, request, include_gantt=False)

    elif step == 18:
        # Budgetary Requirements: the line-item budget upload.
        if request.FILES.get("funding_file"):
            proposal.funding_file = request.FILES["funding_file"]
            proposal.save(update_fields=["funding_file"])

    elif step == 19:
        _save_output_outcomes(proposal, request)

    return None


