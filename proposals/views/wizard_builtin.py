"""
The built-in wizard step forms, kept behind a registry.

Every step of the original 19-step wizard had its save logic and its template
hard-coded into ``wizard.py``. That is what this module replaces: each built-in
step is one entry in ``_BUILTIN_STEP_SAVERS`` (plus its GET context in
``_builtin_step_context`` and its completion rule in ``_builtin_step_complete``)
and the wizard view dispatches through the registry **only when the step's
``ProposalWizardStepConfig.layout`` says the step still uses the built-in
form**.

When an admin switches a step to ``Layout.DYNAMIC`` (custom form) in the
no-code manager, the registry is bypassed for that step: the step renders and
saves through the admin-built ``DynamicFormTemplate`` alone (see
``proposals.views.dynamic_answers``). The office can therefore retire any
built-in step whose printed form no longer matches their process - without a
developer touching this file.

``BUILTIN_STEP_FIELD_KEYS`` lists, per built-in step, the Proposal columns its
system form owns. On a built-in step an admin field mapped to one of those
columns is a *label override* for the system input (it is not rendered or
validated twice); on a custom step the same mapping means the field's answer
is written into the real column so documents and reports keep working.
"""

from django.contrib import messages
from django.shortcuts import redirect

from details.models import ProposalWizardStepConfig

from ..models import ProgramProject
from ..models import ProposalAttachment
from ..models import ProposalGenderIssue
from ..models import ProposalMethodology
from ..models import ProposalOutputOutcome
from ..models import ProposalSDG
from ..models import ProposalSpecificObjective
from ..models import ProposalThrust
from .constants import GENDER_ISSUE_LIST, SDG_LIST, THRUST_LIST
from .helpers import _strip_phase_prefix, _to_int, _to_roman
from .proponents import _update_creator_role, save_step_three_proponents


#: Step numbers that ship with a system form. Any other step number is, by
#: definition, an admin-created step and always renders dynamically.
BUILTIN_STEP_NUMBERS = frozenset(range(1, 20))

#: Proposal columns each built-in step's system form owns. Only the columns
#: that a dynamic field can also map to are listed (see
#: ``DynamicFormField.ProposalMapsTo``); a step whose built-in form writes
#: rows instead of columns (SDG links, methodologies, uploads, ...) owns none.
BUILTIN_STEP_FIELD_KEYS = {
    1: {"extension_type", "scope_type", "research_title"},
    2: {"title"},
    3: set(),
    4: {"implementing_agency"},
    5: {"beneficiaries_count", "beneficiaries_who"},
    6: set(),
    7: {"budgetary_requirement"},
    8: set(),
    9: set(),
    10: {"extension_venue", "estimated_month", "estimated_year"},
    11: {"rationale_background"},
    12: {"significance"},
    13: {"general_objective"},
    14: set(),
    15: set(),
    16: set(),
    17: set(),
    18: set(),
    19: set(),
}


def uses_builtin_form(step, config=None):
    """True when ``step`` should render its built-in system form.

    A step uses the built-in form when it has one *and* the admin has not
    switched it to a custom form. A missing config row means "not managed
    yet", which keeps the classic behaviour.
    """
    if step not in BUILTIN_STEP_NUMBERS:
        return False
    if config is None:
        config = ProposalWizardStepConfig.objects.filter(step_no=step).first()
    if config is None:
        return True
    return config.layout == ProposalWizardStepConfig.Layout.BUILTIN


def builtin_handled_keys(step, config=None):
    """Proposal columns the built-in form of ``step`` already saves.

    Empty for custom-layout steps and steps without a built-in form: there the
    admin-built fields own everything.
    """
    if not uses_builtin_form(step, config=config):
        return set()
    return set(BUILTIN_STEP_FIELD_KEYS.get(step, set()))


# ---------------------------------------------------------------------------
# Step completion bookkeeping (moved from wizard.py; re-imported there)
# ---------------------------------------------------------------------------

def mark_step_completed(proposal, step_no):
    """Record a step as done. Callers flash their own message."""
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


# ---------------------------------------------------------------------------
# Built-in step savers
# ---------------------------------------------------------------------------
# Each saver is ``(request, proposal, action) -> (early_response, missing)``.
# ``early_response`` is a redirect the wizard view must return immediately
# (a validation failure, or the Step 3 member buttons); ``missing`` lists
# required problems the wizard view merges with the dynamic-field ones.


def _save_builtin_step_one(request, proposal, action):
    proposal.extension_type = request.POST.get("extension_type", "")
    proposal.scope_type = request.POST.get("scope_type", "")
    research_title = (request.POST.get("research_title") or "").strip()

    if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"]:
        proposal.research_title = research_title
    else:
        proposal.research_title = ""

    if proposal.extension_type in ["RESEARCH_FACULTY", "RESEARCH_STUDENT"] and not research_title and action != "skip":
        messages.error(request, "Research Title is required for research-based extension type.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=1), []

    proposal.save(update_fields=["extension_type", "scope_type", "research_title"])
    _update_creator_role(proposal)
    return None, []


def _save_builtin_step_two(request, proposal, action):
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
    return None, []


def _save_builtin_step_three(request, proposal, action):
    step = 3
    missing = list(save_step_three_proponents(proposal, request))

    if action in ("add_member", "save_members"):
        # Lazy import: dynamic_answers imports this module for the registry,
        # so importing it back at module load would be circular.
        from .dynamic_answers import _is_dynamic_step_complete

        if proposal.proponents.exists() and _is_dynamic_step_complete(proposal, step):
            mark_step_completed(proposal, step)
        else:
            unmark_step_completed(proposal, step)

        proposal.save(update_fields=["completed_steps", "skipped_steps"])
        if missing:
            messages.error(
                request,
                "Saved, but some required proponent details are still missing: "
                + "; ".join(missing[:5]),
            )
        else:
            messages.success(request, "Members updated.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=3), []

    return None, missing


def _save_builtin_step_four(request, proposal, action):
    proposal.implementing_agency = (request.POST.get("implementing_agency") or "").strip()
    proposal.save(update_fields=["implementing_agency"])
    return None, []


def _save_builtin_step_five(request, proposal, action):
    raw_beneficiaries = request.POST.get("beneficiaries_count")
    proposal.beneficiaries_count = _to_int(raw_beneficiaries, default=None)
    if proposal.beneficiaries_count == 0 and (raw_beneficiaries or "").strip() == "":
        proposal.beneficiaries_count = None
    proposal.beneficiaries_who = (request.POST.get("beneficiaries_who") or "").strip()
    proposal.save(update_fields=["beneficiaries_count", "beneficiaries_who"])
    return None, []


def _save_builtin_step_six(request, proposal, action):
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
    return None, []


def _save_builtin_step_seven(request, proposal, action):
    proposal.budgetary_requirement = (request.POST.get("budgetary_requirement") or "").strip()
    proposal.save(update_fields=["budgetary_requirement"])
    return None, []


def _save_builtin_step_eight(request, proposal, action):
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
        return redirect("proposal_wizard", proposal_id=proposal.id, step=8), []

    return None, []


def _save_builtin_step_nine(request, proposal, action):
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
    return None, []


def _save_builtin_step_ten(request, proposal, action):
    estimated_month = (request.POST.get("estimated_month") or "").strip()
    estimated_year_raw = (request.POST.get("estimated_year") or "").strip()
    extension_venue = (request.POST.get("extension_venue") or "").strip()

    proposal.estimated_month = estimated_month or ""
    proposal.estimated_year = int(estimated_year_raw) if estimated_year_raw.isdigit() else None
    proposal.extension_venue = extension_venue
    proposal.save(update_fields=["estimated_month", "estimated_year", "extension_venue"])
    return None, []


def _save_builtin_step_eleven(request, proposal, action):
    proposal.rationale_background = (request.POST.get("rationale_background") or "").strip()
    proposal.save(update_fields=["rationale_background"])
    return None, []


def _save_builtin_step_twelve(request, proposal, action):
    proposal.significance = (request.POST.get("significance") or "").strip()
    proposal.save(update_fields=["significance"])
    return None, []


def _save_builtin_step_thirteen(request, proposal, action):
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
    return None, []


def _save_builtin_step_fourteen(request, proposal, action):
    proposal.methodologies.all().delete()
    for item in request.POST.getlist("methodologies[]"):
        item = (item or "").strip()
        if item:
            ProposalMethodology.objects.create(proposal=proposal, item=item)
    return None, []


def _save_builtin_step_fifteen(request, proposal, action):
    proposal.output_outcomes.all().delete()
    for item in request.POST.getlist("output_outcomes[]"):
        item = (item or "").strip()
        if item:
            ProposalOutputOutcome.objects.create(proposal=proposal, item=item)
    return None, []


def _save_builtin_step_sixteen(request, proposal, action):
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
    return None, []


def _save_builtin_step_seventeen(request, proposal, action):
    if request.FILES.get("funding_file"):
        proposal.funding_file = request.FILES["funding_file"]
        proposal.save(update_fields=["funding_file"])
    return None, []


def _save_builtin_step_eighteen(request, proposal, action):
    if request.FILES.get("research_abstract_file"):
        proposal.research_abstract_file = request.FILES["research_abstract_file"]
        proposal.save(update_fields=["research_abstract_file"])
    return None, []


def _save_builtin_step_nineteen(request, proposal, action):
    if request.FILES.get("certificate_of_completion_file"):
        proposal.certificate_of_completion_file = request.FILES["certificate_of_completion_file"]
        proposal.save(update_fields=["certificate_of_completion_file"])
    return None, []


_BUILTIN_STEP_SAVERS = {
    1: _save_builtin_step_one,
    2: _save_builtin_step_two,
    3: _save_builtin_step_three,
    4: _save_builtin_step_four,
    5: _save_builtin_step_five,
    6: _save_builtin_step_six,
    7: _save_builtin_step_seven,
    8: _save_builtin_step_eight,
    9: _save_builtin_step_nine,
    10: _save_builtin_step_ten,
    11: _save_builtin_step_eleven,
    12: _save_builtin_step_twelve,
    13: _save_builtin_step_thirteen,
    14: _save_builtin_step_fourteen,
    15: _save_builtin_step_fifteen,
    16: _save_builtin_step_sixteen,
    17: _save_builtin_step_seventeen,
    18: _save_builtin_step_eighteen,
    19: _save_builtin_step_nineteen,
}


def _save_builtin_step(request, proposal, step, action):
    """Run the built-in saver for ``step`` when one exists."""
    saver = _BUILTIN_STEP_SAVERS.get(step)
    if saver is None:
        return None, []
    return saver(request, proposal, action)


# ---------------------------------------------------------------------------
# Built-in GET context (per-step data the system templates need)
# ---------------------------------------------------------------------------

def _builtin_step_context(proposal, step):
    """Attach the per-step data the built-in step templates need on GET."""
    ctx = {}

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


# ---------------------------------------------------------------------------
# Built-in completion rules
# ---------------------------------------------------------------------------

def _builtin_step_complete(proposal, step):
    """The completion rule of a built-in step, read from saved data.

    Step 3 is the one exception: its rule also depends on the admin-built
    proponent group, so the wizard view composes it with
    ``_is_dynamic_step_complete`` (see ``wizard.is_step_complete``).
    """
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

    return False
