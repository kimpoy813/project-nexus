"""
The built-in *sections* of the proposal form, and the step -> section lookup.

A section is one self-contained part of the proposal (the title input, the
proponent roster, the SDG picker, a file upload, ...). It knows how to:

* render itself (``template``),
* add what its template needs to the context (``context``),
* read a submitted form back onto the proposal (``save``),
* say whether it is complete (``is_complete``), and
* describe the fields the admin can edit through the form builder
  (``default_fields`` / ``native_keys``).

The wizard used to branch on ``step == 7`` and friends in four different
places, so the admin could rename step 7 but never move, remove, or replace
it. Now a ``ProposalWizardStepConfig`` row carries a ``section_key`` and the
wizard asks the section - whichever step it currently sits on - to do the
work. A step with no section is a plain container for admin-built fields.

Adding a new built-in section is a matter of registering it in ``SECTIONS``
and writing its ``sections/<key>.html`` partial.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from details.models import ProposalWizardStepConfig
from details.proponent_fields import is_proponents_step, proponents_step_no  # noqa: F401  (re-exported)
from details.wizard_defaults import PROPONENTS_SECTION_KEY, default_section_for_step

from ..models import (
    ProgramProject,
    ProposalAttachment,
    ProposalGenderIssue,
    ProposalMethodology,
    ProposalOutputOutcome,
    ProposalSDG,
    ProposalSpecificObjective,
    ProposalThrust,
)
from .constants import GENDER_ISSUE_LIST, SDG_LIST, THRUST_LIST
from .helpers import _strip_phase_prefix, _to_int, _to_roman
from .proponents import _update_creator_role, save_step_three_proponents


RESEARCH_TYPES = ("RESEARCH_FACULTY", "RESEARCH_STUDENT")

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@dataclass
class SaveOutcome:
    """What a section's ``save`` hands back to the wizard view.

    ``missing`` lists required inputs still empty (blocks *Save & Next*).
    ``stay`` asks the view to redirect back to the same step after flashing
    ``message`` (``(level, text)``) - used for in-step actions such as adding
    a proponent, or a validation failure that must not advance the wizard.
    """

    missing: list = field(default_factory=list)
    stay: bool = False
    message: Optional[tuple] = None
    refresh_completion: bool = False


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    summary: str
    template: str
    #: Field keys the section's template renders itself. The admin may edit
    #: the label / placeholder / help text / required flag of these through
    #: the form builder, but their values live on the Proposal, not in
    #: ``DynamicFormAnswer``.
    native_keys: frozenset = frozenset()
    #: Admin-editable defaults seeded into the step's form the first time it
    #: is used. Same shape as ``DynamicFormField`` columns.
    default_fields: tuple = ()
    context: Callable = lambda proposal, ctx, fields: None
    save: Callable = lambda proposal, request, action, fields, step: SaveOutcome()
    is_complete: Callable = lambda proposal, fields: True
    #: Only one step may carry this section (e.g. the proponent roster).
    unique: bool = True

    @property
    def is_proponents(self):
        return self.key == PROPONENTS_SECTION_KEY


def _required(fields, key, default=True):
    """Whether the admin still marks a native field as required."""
    f = (fields or {}).get(key)
    return default if f is None else bool(f.required)


def _text(request, name):
    return (request.POST.get(name) or "").strip()


def _is_research(proposal):
    return proposal.extension_type in RESEARCH_TYPES


# ---------------------------------------------------------------------------
# extension_type
# ---------------------------------------------------------------------------

def _save_extension_type(proposal, request, action, fields, step):
    proposal.extension_type = request.POST.get("extension_type", "")
    proposal.scope_type = request.POST.get("scope_type", "")
    research_title = _text(request, "research_title")
    proposal.research_title = research_title if _is_research(proposal) else ""
    proposal.save(update_fields=["extension_type", "scope_type", "research_title"])
    _update_creator_role(proposal)

    if _is_research(proposal) and not research_title and action != "skip" and _required(fields, "research_title"):
        return SaveOutcome(
            stay=True,
            message=("error", "Research Title is required for research-based extension type."),
        )
    return SaveOutcome()


def _complete_extension_type(proposal, fields):
    if not proposal.extension_type or not proposal.scope_type:
        return False
    if _is_research(proposal) and _required(fields, "research_title") and not (proposal.research_title or "").strip():
        return False
    return True


# ---------------------------------------------------------------------------
# title (+ program phases)
# ---------------------------------------------------------------------------

def _context_title(proposal, ctx, fields):
    if proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")


def _save_title(proposal, request, action, fields, step):
    proposal.title = _text(request, "title")
    proposal.save(update_fields=["title"])

    if proposal.scope_type != "PROGRAM":
        return SaveOutcome()

    raw_ids = request.POST.getlist("project_id[]")
    raw_titles = request.POST.getlist("project_titles[]")
    max_len = max(len(raw_ids), len(raw_titles), 0)
    raw_ids += [""] * (max_len - len(raw_ids))
    raw_titles += [""] * (max_len - len(raw_titles))

    existing = {str(p.id): p for p in proposal.program_projects.all()}
    keep_db_ids, to_update, to_create = [], [], []

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
            to_create.append(ProgramProject(proposal=proposal, title=stored_title, order=order_no))

    proposal.program_projects.exclude(id__in=keep_db_ids).delete()
    if to_update:
        ProgramProject.objects.bulk_update(to_update, ["title", "order"])
    if to_create:
        ProgramProject.objects.bulk_create(to_create)
    return SaveOutcome()


def _complete_title(proposal, fields):
    if not (proposal.title or "").strip():
        return False
    if proposal.scope_type == "PROGRAM":
        return proposal.program_projects.exists()
    return True


# ---------------------------------------------------------------------------
# proponents
# ---------------------------------------------------------------------------

def _context_proponents(proposal, ctx, fields):
    ctx["proponents"] = proposal.proponents.select_related("user").all().order_by("id")
    if proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = (
            proposal.program_projects.select_related("leader_user").all().order_by("order", "id")
        )


def _save_proponents(proposal, request, action, fields, step):
    missing = save_step_three_proponents(proposal, request, step=step)
    if action in ("add_member", "save_members"):
        if missing:
            message = (
                "error",
                "Saved, but some required proponent details are still missing: " + "; ".join(missing[:5]),
            )
        else:
            message = ("success", "Members updated.")
        return SaveOutcome(missing=missing, stay=True, message=message, refresh_completion=True)
    return SaveOutcome(missing=missing)


def _complete_proponents(proposal, fields):
    # The repeatable group's own required columns / minimum rows are checked
    # by the dynamic-form gate that the wizard applies to every step.
    return proposal.proponents.exists()


# ---------------------------------------------------------------------------
# simple single-value sections
# ---------------------------------------------------------------------------

def _save_beneficiaries(proposal, request, action, fields, step):
    raw = request.POST.get("beneficiaries_count")
    proposal.beneficiaries_count = _to_int(raw, default=None)
    if proposal.beneficiaries_count == 0 and (raw or "").strip() == "":
        proposal.beneficiaries_count = None
    proposal.beneficiaries_who = _text(request, "beneficiaries_who")
    proposal.save(update_fields=["beneficiaries_count", "beneficiaries_who"])
    return SaveOutcome()


def _complete_beneficiaries(proposal, fields):
    count_ok = proposal.beneficiaries_count is not None or not _required(fields, "beneficiaries_count")
    who_ok = bool((proposal.beneficiaries_who or "").strip()) or not _required(fields, "beneficiaries_who")
    return count_ok and who_ok


def _context_budget(proposal, ctx, fields):
    ctx["budgetary_requirement"] = proposal.budgetary_requirement or ""


def _save_budget(proposal, request, action, fields, step):
    proposal.budgetary_requirement = _text(request, "budgetary_requirement")
    proposal.save(update_fields=["budgetary_requirement"])
    return SaveOutcome()


def _context_schedule(proposal, ctx, fields):
    ctx["estimated_month"] = proposal.estimated_month or ""
    ctx["estimated_year"] = proposal.estimated_year or ""
    ctx["extension_venue"] = proposal.extension_venue or ""
    ctx["month_choices"] = MONTHS


def _save_schedule(proposal, request, action, fields, step):
    year_raw = _text(request, "estimated_year")
    proposal.estimated_month = _text(request, "estimated_month")
    proposal.estimated_year = int(year_raw) if year_raw.isdigit() else None
    proposal.extension_venue = _text(request, "extension_venue")
    proposal.save(update_fields=["estimated_month", "estimated_year", "extension_venue"])
    return SaveOutcome()


def _complete_schedule(proposal, fields):
    if _required(fields, "extension_venue") and not (proposal.extension_venue or "").strip():
        return False
    if _required(fields, "estimated_month", default=False) and not proposal.estimated_month:
        return False
    if _required(fields, "estimated_year", default=False) and not proposal.estimated_year:
        return False
    return True


def _text_field_section(attr, ctx_key=None):
    """Context / save / completeness for a section that is one text column."""

    def context(proposal, ctx, fields):
        ctx[ctx_key or attr] = getattr(proposal, attr) or ""

    def save(proposal, request, action, fields, step):
        setattr(proposal, attr, _text(request, attr))
        proposal.save(update_fields=[attr])
        return SaveOutcome()

    def is_complete(proposal, fields):
        return bool((getattr(proposal, attr) or "").strip()) or not _required(fields, attr)

    return context, save, is_complete


_ctx_agency, _save_agency, _complete_agency = _text_field_section("implementing_agency")
_ctx_rationale, _save_rationale, _complete_rationale = _text_field_section("rationale_background")
_ctx_significance, _save_significance, _complete_significance = _text_field_section("significance")
_, _, _complete_budget = _text_field_section("budgetary_requirement")


# ---------------------------------------------------------------------------
# sdg_thrust
# ---------------------------------------------------------------------------

def _context_sdg(proposal, ctx, fields):
    ctx["sdgs"] = SDG_LIST
    ctx["thrusts"] = THRUST_LIST
    sdg_links = proposal.sdg_links.all()
    thrust_links = proposal.thrust_links.all()
    ctx["selected_sdg_codes"] = set(sdg_links.values_list("sdg_code", flat=True))
    ctx["selected_thrust_names"] = set(thrust_links.values_list("thrust_name", flat=True))
    ctx["sdg_explanations"] = {item.sdg_code: item.explanation for item in sdg_links}
    ctx["thrust_explanations"] = {item.thrust_name: item.explanation for item in thrust_links}


def _save_sdg(proposal, request, action, fields, step):
    ProposalSDG.objects.filter(proposal=proposal).delete()
    ProposalThrust.objects.filter(proposal=proposal).delete()
    for code in request.POST.getlist("sdg_codes"):
        code = (code or "").strip()
        if code:
            ProposalSDG.objects.create(
                proposal=proposal,
                sdg_code=code,
                explanation=_text(request, f"sdg_explanation_{code}"),
            )
    for name in request.POST.getlist("thrust_names"):
        name = (name or "").strip()
        if name:
            ProposalThrust.objects.create(
                proposal=proposal,
                thrust_name=name,
                explanation=_text(request, f"thrust_explanation_{name}"),
            )
    return SaveOutcome()


def _complete_sdg(proposal, fields):
    return proposal.sdg_links.exists() or proposal.thrust_links.exists()


# ---------------------------------------------------------------------------
# participants
# ---------------------------------------------------------------------------

_SEX_FIELDS = ("sex_male", "sex_female")
_GENDER_FIELDS = ("g_lesbian", "g_gay", "g_bisexual", "g_transgender", "g_straight", "g_others")


def _totals(proposal):
    sex_total = sum(getattr(proposal, f) or 0 for f in _SEX_FIELDS)
    gender_total = sum(getattr(proposal, f) or 0 for f in _GENDER_FIELDS)
    return sex_total, gender_total


def _context_participants(proposal, ctx, fields):
    ctx["sex_total"], ctx["gender_total"] = _totals(proposal)


def _save_participants(proposal, request, action, fields, step):
    for name in _SEX_FIELDS + _GENDER_FIELDS:
        setattr(proposal, name, _to_int(request.POST.get(name)))
    proposal.save(update_fields=list(_SEX_FIELDS + _GENDER_FIELDS))
    sex_total, gender_total = _totals(proposal)
    if action == "next" and sex_total != gender_total:
        return SaveOutcome(
            stay=True,
            message=("error", "Sex total and Gender total must be the same before you can proceed."),
        )
    return SaveOutcome()


def _complete_participants(proposal, fields):
    sex_total, gender_total = _totals(proposal)
    return sex_total > 0 and sex_total == gender_total


# ---------------------------------------------------------------------------
# gender_issues
# ---------------------------------------------------------------------------

def _context_gender_issues(proposal, ctx, fields):
    ctx["gender_issues"] = GENDER_ISSUE_LIST
    ctx["selected_gender_issue_keys"] = set(proposal.gender_issue_links.values_list("issue_key", flat=True))
    others = proposal.gender_issue_links.filter(issue_key="others").first()
    ctx["gender_issue_other_text"] = others.other_text if others else ""


def _save_gender_issues(proposal, request, action, fields, step):
    other_text = _text(request, "gender_issue_other_text")
    label_map = dict(GENDER_ISSUE_LIST)
    ProposalGenderIssue.objects.filter(proposal=proposal).delete()
    for key in request.POST.getlist("gender_issue_keys"):
        key = (key or "").strip()
        if key in label_map:
            ProposalGenderIssue.objects.create(
                proposal=proposal,
                issue_key=key,
                issue_label=label_map[key],
                other_text=other_text if key == "others" else "",
            )
    return SaveOutcome()


def _complete_gender_issues(proposal, fields):
    issues = proposal.gender_issue_links.all()
    if not issues.exists():
        return False
    others = issues.filter(issue_key="others").first()
    return not (others and not (others.other_text or "").strip())


# ---------------------------------------------------------------------------
# objectives
# ---------------------------------------------------------------------------

def _context_objectives(proposal, ctx, fields):
    ctx["general_objective"] = proposal.general_objective or ""
    if proposal.scope_type == "PROGRAM":
        projects = proposal.program_projects.all().order_by("order", "id")
        ctx["program_projects"] = projects
        ctx["project_objectives_map"] = {
            prj.id: list(
                proposal.specific_objectives.filter(program_project=prj).values_list("objective", flat=True)
            )
            for prj in projects
        }
    else:
        ctx["specific_objectives"] = list(
            proposal.specific_objectives.filter(program_project__isnull=True).values_list("objective", flat=True)
        )


def _save_objectives(proposal, request, action, fields, step):
    proposal.general_objective = _text(request, "general_objective")
    proposal.save(update_fields=["general_objective"])
    proposal.specific_objectives.all().delete()

    def _create(objectives, project):
        for obj in objectives:
            obj = (obj or "").strip()
            if obj:
                ProposalSpecificObjective.objects.create(
                    proposal=proposal, program_project=project, objective=obj
                )

    if proposal.scope_type == "PROGRAM":
        for prj in proposal.program_projects.all():
            _create(request.POST.getlist(f"specific_objectives_{prj.id}[]"), prj)
    else:
        _create(request.POST.getlist("specific_objectives[]"), None)
    return SaveOutcome()


def _complete_objectives(proposal, fields):
    if _required(fields, "general_objective") and not (proposal.general_objective or "").strip():
        return False
    if proposal.scope_type == "PROGRAM":
        projects = proposal.program_projects.all()
        if not projects.exists():
            return False
        return all(
            proposal.specific_objectives.filter(program_project=prj).exists() for prj in projects
        )
    return proposal.specific_objectives.filter(program_project__isnull=True).exists()


# ---------------------------------------------------------------------------
# list sections: methodology / outputs
# ---------------------------------------------------------------------------

def _list_section(related_name, model, post_key, ctx_key):
    def context(proposal, ctx, fields):
        ctx[ctx_key] = list(getattr(proposal, related_name).values_list("item", flat=True))

    def save(proposal, request, action, fields, step):
        getattr(proposal, related_name).all().delete()
        for item in request.POST.getlist(post_key):
            item = (item or "").strip()
            if item:
                model.objects.create(proposal=proposal, item=item)
        return SaveOutcome()

    def is_complete(proposal, fields):
        return getattr(proposal, related_name).exists()

    return context, save, is_complete


_ctx_methodology, _save_methodology, _complete_methodology = _list_section(
    "methodologies", ProposalMethodology, "methodologies[]", "methodologies"
)
_ctx_outputs, _save_outputs, _complete_outputs = _list_section(
    "output_outcomes", ProposalOutputOutcome, "output_outcomes[]", "output_outcomes"
)


# ---------------------------------------------------------------------------
# activities (work plan / gantt / attachments)
# ---------------------------------------------------------------------------

def _context_activities(proposal, ctx, fields):
    ctx["existing_attachments"] = proposal.attachments.filter(
        category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES
    ).order_by("id")
    if proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")


def _save_activities(proposal, request, action, fields, step):
    remove_ids = request.POST.getlist("remove_attachment_ids")
    if remove_ids:
        ProposalAttachment.objects.filter(
            proposal=proposal,
            category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES,
            id__in=remove_ids,
        ).delete()

    changed = []
    for name in ("work_plan_file", "gantt_chart_file"):
        if request.FILES.get(name):
            setattr(proposal, name, request.FILES[name])
            changed.append(name)
    if changed:
        proposal.save(update_fields=changed)

    for f in request.FILES.getlist("attachment_files"):
        if f:
            ProposalAttachment.objects.create(
                proposal=proposal,
                file=f,
                category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES,
                label=getattr(f, "name", ""),
            )
    return SaveOutcome()


def _complete_activities(proposal, fields):
    return bool(proposal.work_plan_file) and bool(proposal.gantt_chart_file)


# ---------------------------------------------------------------------------
# single file uploads
# ---------------------------------------------------------------------------

def _file_section(attr, *, research_only=False, ctx_flag=None):
    def context(proposal, ctx, fields):
        if ctx_flag:
            ctx[ctx_flag] = _is_research(proposal)

    def save(proposal, request, action, fields, step):
        if request.FILES.get(attr):
            setattr(proposal, attr, request.FILES[attr])
            proposal.save(update_fields=[attr])
        return SaveOutcome()

    def is_complete(proposal, fields):
        if research_only and not _is_research(proposal):
            return True
        return bool(getattr(proposal, attr))

    return context, save, is_complete


def _context_funding(proposal, ctx, fields):
    ctx["existing_funding_attachments"] = proposal.attachments.filter(
        category=ProposalAttachment.Category.OTHER
    ).order_by("id")


_, _save_funding, _complete_funding = _file_section("funding_file")
_ctx_abstract, _save_abstract, _complete_abstract = _file_section(
    "research_abstract_file", research_only=True, ctx_flag="requires_abstract"
)
_ctx_certificate, _save_certificate, _complete_certificate = _file_section(
    "certificate_of_completion_file", research_only=True, ctx_flag="requires_certificate"
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _f(key, label, ftype="TEXT", **extra):
    spec = {"field_key": key, "label": label, "field_type": ftype, "required": True}
    spec.update(extra)
    return spec


_T = "services/wizard/sections/"

SECTIONS = {
    s.key: s
    for s in [
        Section(
            key="extension_type",
            label="Extension type and scope",
            summary="Research/request/community type, program/project/activity scope, research title.",
            template=_T + "extension_type.html",
            native_keys=frozenset({"extension_type", "scope_type", "research_title"}),
            default_fields=(
                _f("extension_type", "Extension Type", "SELECT", placeholder="Choose extension type",
                   choices_text="RESEARCH_FACULTY|Research-based (Faculty)\nRESEARCH_STUDENT|Research-based (Student)\nREQUEST_BASED|Request-based\nCOMMUNITY_BASED|Community-based"),
                _f("scope_type", "Scope", "SELECT", placeholder="Choose scope",
                   choices_text="PROGRAM|Program\nPROJECT|Project\nACTIVITY|Activity"),
                _f("research_title", "Research Title", placeholder="Enter research title if applicable",
                   required=True, depends_on_key="extension_type",
                   depends_on_value="RESEARCH_FACULTY,RESEARCH_STUDENT"),
            ),
            save=_save_extension_type,
            is_complete=_complete_extension_type,
        ),
        Section(
            key="title",
            label="Title (and program phases)",
            summary="Official title; for programs, the list of component projects.",
            template=_T + "title.html",
            native_keys=frozenset({"title"}),
            default_fields=(_f("title", "Title of the Program / Project / Activity", placeholder="Enter official title"),),
            context=_context_title,
            save=_save_title,
            is_complete=_complete_title,
        ),
        Section(
            key="proponents",
            label="Proponents",
            summary="Account search, the repeatable proponent roster, and per-phase project leaders.",
            template=_T + "proponents.html",
            context=_context_proponents,
            save=_save_proponents,
            is_complete=_complete_proponents,
        ),
        Section(
            key="implementing_agency",
            label="Implementing agency / unit",
            summary="A single text input.",
            template=_T + "implementing_agency.html",
            native_keys=frozenset({"implementing_agency"}),
            default_fields=(_f("implementing_agency", "Implementing Agency / Unit", placeholder="Enter implementing agency"),),
            context=_ctx_agency,
            save=_save_agency,
            is_complete=_complete_agency,
        ),
        Section(
            key="beneficiaries",
            label="Collaborators / beneficiaries",
            summary="Beneficiary count and a description of the target group.",
            template=_T + "beneficiaries.html",
            native_keys=frozenset({"beneficiaries_count", "beneficiaries_who", "who_beneficiaries"}),
            default_fields=(
                _f("beneficiaries_count", "Beneficiary Count", "NUMBER", placeholder="Estimated count of beneficiaries"),
                _f("beneficiaries_who", "Target Group / Beneficiaries Description", placeholder="Describe who they are"),
            ),
            save=_save_beneficiaries,
            is_complete=_complete_beneficiaries,
        ),
        Section(
            key="sdg_thrust",
            label="SDGs / extension agenda",
            summary="SDG and extension-thrust pickers with explanations.",
            template=_T + "sdg_thrust.html",
            context=_context_sdg,
            save=_save_sdg,
            is_complete=_complete_sdg,
        ),
        Section(
            key="budget",
            label="Budgetary requirement",
            summary="Funding source and amount.",
            template=_T + "budget.html",
            native_keys=frozenset({"budgetary_requirement"}),
            default_fields=(_f("budgetary_requirement", "Budgetary Requirement", "TEXTAREA", placeholder="Describe budget details"),),
            context=_context_budget,
            save=_save_budget,
            is_complete=_complete_budget,
        ),
        Section(
            key="participants",
            label="Participants / proposed clients",
            summary="Sex and gender counts (totals must match).",
            template=_T + "participants.html",
            context=_context_participants,
            save=_save_participants,
            is_complete=_complete_participants,
        ),
        Section(
            key="gender_issues",
            label="Gender issues / mandates",
            summary="GAD mandate checklist with an 'Others' free text.",
            template=_T + "gender_issues.html",
            context=_context_gender_issues,
            save=_save_gender_issues,
            is_complete=_complete_gender_issues,
        ),
        Section(
            key="schedule_venue",
            label="Date and venue / extension site",
            summary="Estimated month and year plus the venue.",
            template=_T + "schedule_venue.html",
            native_keys=frozenset({"extension_venue", "estimated_month", "estimated_year"}),
            default_fields=(
                _f("extension_venue", "Extension Venue / Site", placeholder="Enter venue"),
                _f("estimated_month", "Estimated Month", "SELECT", placeholder="Choose month",
                   choices_text="\n".join(f"{m}|{m}" for m in MONTHS)),
                _f("estimated_year", "Estimated Year", "NUMBER", placeholder="e.g., 2026"),
            ),
            context=_context_schedule,
            save=_save_schedule,
            is_complete=_complete_schedule,
        ),
        Section(
            key="rationale",
            label="Rationale / background",
            summary="Long text with a word counter.",
            template=_T + "rationale.html",
            native_keys=frozenset({"rationale_background"}),
            default_fields=(_f("rationale_background", "Rationale / Background", "TEXTAREA", placeholder="Provide rationale background"),),
            context=_ctx_rationale,
            save=_save_rationale,
            is_complete=_complete_rationale,
        ),
        Section(
            key="significance",
            label="Significance",
            summary="Long text with a word counter.",
            template=_T + "significance.html",
            native_keys=frozenset({"significance"}),
            default_fields=(_f("significance", "Significance", "TEXTAREA", placeholder="Describe significance"),),
            context=_ctx_significance,
            save=_save_significance,
            is_complete=_complete_significance,
        ),
        Section(
            key="objectives",
            label="Objectives",
            summary="General objective and SMART specific objectives (per phase for programs).",
            template=_T + "objectives.html",
            native_keys=frozenset({"general_objective"}),
            default_fields=(_f("general_objective", "General Objective", "TEXTAREA", placeholder="Enter general objective"),),
            context=_context_objectives,
            save=_save_objectives,
            is_complete=_complete_objectives,
        ),
        Section(
            key="methodology",
            label="Methodology / mechanics",
            summary="A growable list of implementation steps.",
            template=_T + "methodology.html",
            context=_ctx_methodology,
            save=_save_methodology,
            is_complete=_complete_methodology,
        ),
        Section(
            key="outputs",
            label="Output / outcome",
            summary="A growable list of expected outputs and outcomes.",
            template=_T + "outputs.html",
            context=_ctx_outputs,
            save=_save_outputs,
            is_complete=_complete_outputs,
        ),
        Section(
            key="activities",
            label="Details of activities",
            summary="Work plan and Gantt chart uploads with template downloads and extra attachments.",
            template=_T + "activities.html",
            context=_context_activities,
            save=_save_activities,
            is_complete=_complete_activities,
        ),
        Section(
            key="funding",
            label="Funding strategy",
            summary="Line-item budget upload with a template download.",
            template=_T + "funding.html",
            context=_context_funding,
            save=_save_funding,
            is_complete=_complete_funding,
        ),
        Section(
            key="research_abstract",
            label="Research abstract upload",
            summary="Only required for research-based proposals.",
            template=_T + "research_abstract.html",
            context=_ctx_abstract,
            save=_save_abstract,
            is_complete=_complete_abstract,
        ),
        Section(
            key="certificate",
            label="Certificate of completion upload",
            summary="Only required for research-based proposals.",
            template=_T + "certificate.html",
            context=_ctx_certificate,
            save=_save_certificate,
            is_complete=_complete_certificate,
        ),
    ]
}


def section_choices():
    """``(key, label, summary)`` for the admin's section dropdown."""
    return [(s.key, s.label, s.summary) for s in SECTIONS.values()]


def get_section(key):
    return SECTIONS.get((key or "").strip())


def section_key_for_step(step_no):
    """The section configured on ``step_no``.

    A wizard that has never been opened has no config rows yet, so the
    built-in layout applies. Once rows exist, a missing row means the admin
    removed that step, and an empty ``section_key`` means a fields-only step.
    """
    config = ProposalWizardStepConfig.objects.filter(step_no=step_no).only("section_key").first()
    if config is not None:
        return config.section_key or ""
    if not ProposalWizardStepConfig.objects.exists():
        return default_section_for_step(step_no)
    return ""


def section_for_step(step_no):
    return get_section(section_key_for_step(step_no))


def native_keys_for_step(step_no):
    section = section_for_step(step_no)
    return section.native_keys if section else frozenset()
