"""
The proposal wizard's built-in *parts*, as a registry.

The wizard used to hardcode its 19 screens three times over — once as
``step_N.html`` templates, once as an ``if step == N`` chain that saved the
POSTed data, and once as a second ``if step == N`` chain that decided whether
the step counted as complete. Adding a screen meant editing all three, and the
office could not touch any of it.

Each part is now one :class:`WizardSection` that owns those three things
together, keyed by a stable name (``extension_type``, ``proponents``,
``sdg_thrust``, ...). A :class:`~details.models.ProposalWizardStepConfig` row
points at a part through ``section_key``, so the admin decides *which* part
each step shows and *where* it sits — the part no longer knows or cares which
step number it landed on.

Steps whose ``section_key`` is blank have no part at all: they are rendered,
saved, and validated purely from the office's own attached forms, which is
what makes an entirely new office template a configuration change instead of a
code change.
"""

from dataclasses import dataclass
from typing import Callable
from typing import Optional

from django.contrib import messages
from django.shortcuts import redirect

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


RESEARCH_EXTENSION_TYPES = ("RESEARCH_FACULTY", "RESEARCH_STUDENT")


@dataclass(frozen=True)
class WizardSection:
    """One built-in part of the proposal wizard.

    ``save`` returns one of three things:

    * an ``HttpResponse`` — the part handled the request itself (an error to
      flash, or an action of its own such as "add member");
    * a list of missing field labels — the wizard merges them with the
      office-built fields and blocks "Save & Next" on the lot;
    * ``None`` — nothing to report, carry on.
    """

    key: str
    label: str
    template: str
    add_context: Optional[Callable[[dict, object, int], None]] = None
    save: Optional[Callable] = None
    is_complete: Optional[Callable[[object, int], bool]] = None
    prepare: Optional[Callable[[object, int], None]] = None
    #: Proposal columns this part renders itself. A dynamic field with one of
    #: these keys is not printed a second time under the built-in inputs.
    owned_keys: tuple = ()


def _redirect_to_step(proposal, step_no):
    return redirect("proposal_wizard", proposal_id=proposal.id, step=step_no)


# ---------------------------------------------------------------------------
# Part 1 — Extension Type and Scope
# ---------------------------------------------------------------------------

def _save_extension_type(request, proposal, step_no, action):
    from .proponents import _update_creator_role

    proposal.extension_type = request.POST.get("extension_type", "")
    proposal.scope_type = request.POST.get("scope_type", "")
    research_title = (request.POST.get("research_title") or "").strip()

    if proposal.extension_type in RESEARCH_EXTENSION_TYPES:
        proposal.research_title = research_title
    else:
        proposal.research_title = ""

    if (
        proposal.extension_type in RESEARCH_EXTENSION_TYPES
        and not research_title
        and action != "skip"
    ):
        messages.error(request, "Research Title is required for research-based extension type.")
        return _redirect_to_step(proposal, step_no)

    proposal.save(update_fields=["extension_type", "scope_type", "research_title"])
    _update_creator_role(proposal)
    return None


def _extension_type_complete(proposal, step_no):
    if not proposal.extension_type or not proposal.scope_type:
        return False
    if proposal.extension_type in RESEARCH_EXTENSION_TYPES:
        return bool((proposal.research_title or "").strip())
    return True


# ---------------------------------------------------------------------------
# Part 2 — Title
# ---------------------------------------------------------------------------

def _title_context(ctx, proposal, step_no):
    if proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")


def _save_title(request, proposal, step_no, action):
    proposal.title = (request.POST.get("title") or "").strip()
    proposal.save(update_fields=["title"])

    if proposal.scope_type != "PROGRAM":
        return None

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
                ProgramProject(proposal=proposal, title=stored_title, order=order_no)
            )

    proposal.program_projects.exclude(id__in=keep_db_ids).delete()

    if to_update:
        ProgramProject.objects.bulk_update(to_update, ["title", "order"])
    if to_create:
        ProgramProject.objects.bulk_create(to_create)
    return None


def _title_complete(proposal, step_no):
    if not (proposal.title or "").strip():
        return False
    if proposal.scope_type == "PROGRAM":
        return proposal.program_projects.exists()
    return True


# ---------------------------------------------------------------------------
# Part 3 — Proponents
# ---------------------------------------------------------------------------

def _prepare_proponents(proposal, step_no):
    """Seed the office's default proponent group the first time the part runs.

    Seeding only fills a completely empty form, so an admin who rearranges the
    columns is never overruled.
    """
    from details.proponent_fields import ensure_proponent_repeater_form

    ensure_proponent_repeater_form(step_no)


def _proponents_context(ctx, proposal, step_no):
    ctx["proponents"] = proposal.proponents.select_related("user").all().order_by("id")
    if proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = (
            proposal.program_projects.select_related("leader_user").all().order_by("order", "id")
        )


def _save_proponents(request, proposal, step_no, action):
    from .dynamic_answers import _is_dynamic_step_complete
    from .proponents import save_step_three_proponents
    from .wizard import mark_step_completed, unmark_step_completed

    missing = save_step_three_proponents(proposal, request)

    if action not in ("add_member", "save_members"):
        return missing

    if proposal.proponents.exists() and _is_dynamic_step_complete(proposal, step_no):
        mark_step_completed(proposal, step_no)
    else:
        unmark_step_completed(proposal, step_no)

    proposal.save(update_fields=["completed_steps", "skipped_steps"])
    if missing:
        messages.error(
            request,
            "Saved, but some required proponent details are still missing: "
            + "; ".join(missing[:5]),
        )
    else:
        messages.success(request, "Members updated.")
    return _redirect_to_step(proposal, step_no)


def _proponents_complete(proposal, step_no):
    from .dynamic_answers import _is_dynamic_step_complete

    if not proposal.proponents.exists():
        return False
    return _is_dynamic_step_complete(proposal, step_no)


# ---------------------------------------------------------------------------
# Parts 4, 7, 11, 12 — single free-text proposal columns
# ---------------------------------------------------------------------------

def _single_field_part(field_name, *, label, template, strip=True):
    """Build the trio for a part that is one proposal column."""

    def add_context(ctx, proposal, step_no):
        ctx[field_name] = getattr(proposal, field_name, "") or ""

    def save(request, proposal, step_no, action):
        value = request.POST.get(field_name) or ""
        setattr(proposal, field_name, value.strip() if strip else value)
        proposal.save(update_fields=[field_name])
        return None

    def is_complete(proposal, step_no):
        return bool((getattr(proposal, field_name, "") or "").strip())

    return WizardSection(
        key=field_name,
        label=label,
        template=template,
        add_context=add_context,
        save=save,
        is_complete=is_complete,
        owned_keys=(field_name,),
    )


# ---------------------------------------------------------------------------
# Part 5 — Collaborators / Beneficiaries
# ---------------------------------------------------------------------------

def _save_beneficiaries(request, proposal, step_no, action):
    raw_beneficiaries = request.POST.get("beneficiaries_count")
    proposal.beneficiaries_count = _to_int(raw_beneficiaries, default=None)
    if proposal.beneficiaries_count == 0 and (raw_beneficiaries or "").strip() == "":
        proposal.beneficiaries_count = None
    proposal.beneficiaries_who = (request.POST.get("beneficiaries_who") or "").strip()
    proposal.save(update_fields=["beneficiaries_count", "beneficiaries_who"])
    return None


def _beneficiaries_complete(proposal, step_no):
    return proposal.beneficiaries_count is not None and bool(
        (proposal.beneficiaries_who or "").strip()
    )


# ---------------------------------------------------------------------------
# Part 6 — SDGs / Extension Agenda
# ---------------------------------------------------------------------------

def _sdg_context(ctx, proposal, step_no):
    ctx["sdgs"] = SDG_LIST
    ctx["thrusts"] = THRUST_LIST
    sdg_links = proposal.sdg_links.all()
    thrust_links = proposal.thrust_links.all()
    ctx["selected_sdg_codes"] = set(sdg_links.values_list("sdg_code", flat=True))
    ctx["selected_thrust_names"] = set(thrust_links.values_list("thrust_name", flat=True))
    ctx["sdg_explanations"] = {item.sdg_code: item.explanation for item in sdg_links}
    ctx["thrust_explanations"] = {item.thrust_name: item.explanation for item in thrust_links}


def _save_sdg(request, proposal, step_no, action):
    sdg_codes = request.POST.getlist("sdg_codes")
    thrust_names = request.POST.getlist("thrust_names")

    ProposalSDG.objects.filter(proposal=proposal).delete()
    ProposalThrust.objects.filter(proposal=proposal).delete()

    for code in sdg_codes:
        code = (code or "").strip()
        if not code:
            continue
        ProposalSDG.objects.create(
            proposal=proposal,
            sdg_code=code,
            explanation=(request.POST.get(f"sdg_explanation_{code}") or "").strip(),
        )

    for name in thrust_names:
        name = (name or "").strip()
        if not name:
            continue
        ProposalThrust.objects.create(
            proposal=proposal,
            thrust_name=name,
            explanation=(request.POST.get(f"thrust_explanation_{name}") or "").strip(),
        )
    return None


def _sdg_complete(proposal, step_no):
    return proposal.sdg_links.exists() or proposal.thrust_links.exists()


# ---------------------------------------------------------------------------
# Part 8 — Participants / Proposed Clients
# ---------------------------------------------------------------------------

GENDER_COLUMNS = (
    "g_lesbian",
    "g_gay",
    "g_bisexual",
    "g_transgender",
    "g_straight",
    "g_others",
)


def _participants_context(ctx, proposal, step_no):
    ctx["sex_total"] = (proposal.sex_male or 0) + (proposal.sex_female or 0)
    ctx["gender_total"] = sum((getattr(proposal, column) or 0) for column in GENDER_COLUMNS)


def _save_participants(request, proposal, step_no, action):
    sex_male = _to_int(request.POST.get("sex_male"))
    sex_female = _to_int(request.POST.get("sex_female"))
    counts = {column: _to_int(request.POST.get(column)) for column in GENDER_COLUMNS}

    proposal.sex_male = sex_male
    proposal.sex_female = sex_female
    for column, value in counts.items():
        setattr(proposal, column, value)
    proposal.save(update_fields=["sex_male", "sex_female", *GENDER_COLUMNS])

    if action == "next" and (sex_male + sex_female) != sum(counts.values()):
        messages.error(
            request, "Sex total and Gender total must be the same before you can proceed."
        )
        return _redirect_to_step(proposal, step_no)
    return None


def _participants_complete(proposal, step_no):
    sex_total = (proposal.sex_male or 0) + (proposal.sex_female or 0)
    gender_total = sum((getattr(proposal, column) or 0) for column in GENDER_COLUMNS)
    return sex_total > 0 and sex_total == gender_total


# ---------------------------------------------------------------------------
# Part 9 — Gender Issues / Mandates Addressed
# ---------------------------------------------------------------------------

def _gender_issue_context(ctx, proposal, step_no):
    ctx["gender_issues"] = GENDER_ISSUE_LIST
    ctx["selected_gender_issue_keys"] = set(
        proposal.gender_issue_links.values_list("issue_key", flat=True)
    )
    others_item = proposal.gender_issue_links.filter(issue_key="others").first()
    ctx["gender_issue_other_text"] = others_item.other_text if others_item else ""


def _save_gender_issues(request, proposal, step_no, action):
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
    return None


def _gender_issues_complete(proposal, step_no):
    issues = proposal.gender_issue_links.all()
    if not issues.exists():
        return False
    others = issues.filter(issue_key="others").first()
    if others and not (others.other_text or "").strip():
        return False
    return True


# ---------------------------------------------------------------------------
# Part 10 — Date and Venue / Extension Site
# ---------------------------------------------------------------------------

MONTH_CHOICES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _schedule_context(ctx, proposal, step_no):
    ctx["estimated_month"] = proposal.estimated_month or ""
    ctx["estimated_year"] = proposal.estimated_year or ""
    ctx["extension_venue"] = proposal.extension_venue or ""
    ctx["month_choices"] = MONTH_CHOICES


def _save_schedule(request, proposal, step_no, action):
    estimated_year_raw = (request.POST.get("estimated_year") or "").strip()
    proposal.estimated_month = (request.POST.get("estimated_month") or "").strip()
    proposal.estimated_year = int(estimated_year_raw) if estimated_year_raw.isdigit() else None
    proposal.extension_venue = (request.POST.get("extension_venue") or "").strip()
    proposal.save(update_fields=["estimated_month", "estimated_year", "extension_venue"])
    return None


def _schedule_complete(proposal, step_no):
    return bool((proposal.extension_venue or "").strip())


# ---------------------------------------------------------------------------
# Part 13 — Objectives
# ---------------------------------------------------------------------------

def _objectives_context(ctx, proposal, step_no):
    ctx["general_objective"] = proposal.general_objective or ""
    if proposal.scope_type != "PROGRAM":
        ctx["specific_objectives"] = list(
            proposal.specific_objectives.filter(program_project__isnull=True).values_list(
                "objective", flat=True
            )
        )
        return

    projects = proposal.program_projects.all().order_by("order", "id")
    ctx["program_projects"] = projects
    ctx["project_objectives_map"] = {
        prj.id: list(
            proposal.specific_objectives.filter(program_project=prj).values_list(
                "objective", flat=True
            )
        )
        for prj in projects
    }


def _save_objectives(request, proposal, step_no, action):
    proposal.general_objective = (request.POST.get("general_objective") or "").strip()
    proposal.save(update_fields=["general_objective"])

    proposal.specific_objectives.all().delete()

    if proposal.scope_type == "PROGRAM":
        for prj in proposal.program_projects.all():
            for objective in request.POST.getlist(f"specific_objectives_{prj.id}[]"):
                objective = (objective or "").strip()
                if objective:
                    ProposalSpecificObjective.objects.create(
                        proposal=proposal, program_project=prj, objective=objective
                    )
        return None

    for objective in request.POST.getlist("specific_objectives[]"):
        objective = (objective or "").strip()
        if objective:
            ProposalSpecificObjective.objects.create(
                proposal=proposal, program_project=None, objective=objective
            )
    return None


def _objectives_complete(proposal, step_no):
    if not (proposal.general_objective or "").strip():
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
# Parts 14 and 15 — simple repeatable lists of one-liners
# ---------------------------------------------------------------------------

def _list_part(relation, field_name, *, label, template):
    def add_context(ctx, proposal, step_no):
        ctx[field_name] = list(getattr(proposal, relation).values_list("item", flat=True))

    def save(request, proposal, step_no, action):
        model = ProposalMethodology if relation == "methodologies" else ProposalOutputOutcome
        getattr(proposal, relation).all().delete()
        for item in request.POST.getlist(f"{field_name}[]"):
            item = (item or "").strip()
            if item:
                model.objects.create(proposal=proposal, item=item)
        return None

    def is_complete(proposal, step_no):
        return getattr(proposal, relation).exists()

    return WizardSection(
        key=field_name,
        label=label,
        template=template,
        add_context=add_context,
        save=save,
        is_complete=is_complete,
    )


# ---------------------------------------------------------------------------
# Parts 16 and 17 — file uploads
# ---------------------------------------------------------------------------

def _details_of_activities_context(ctx, proposal, step_no):
    ctx["existing_attachments"] = proposal.attachments.filter(
        category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES
    ).order_by("id")
    if proposal.scope_type == "PROGRAM":
        ctx["program_projects"] = proposal.program_projects.all().order_by("order", "id")


def _save_details_of_activities(request, proposal, step_no, action):
    remove_attachment_ids = request.POST.getlist("remove_attachment_ids")
    if remove_attachment_ids:
        ProposalAttachment.objects.filter(
            proposal=proposal,
            category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES,
            id__in=remove_attachment_ids,
        ).delete()

    changed_fields = []
    for field_name in ("work_plan_file", "gantt_chart_file"):
        if request.FILES.get(field_name):
            setattr(proposal, field_name, request.FILES[field_name])
            changed_fields.append(field_name)
    if changed_fields:
        proposal.save(update_fields=changed_fields)

    for uploaded in request.FILES.getlist("attachment_files"):
        if uploaded:
            ProposalAttachment.objects.create(
                proposal=proposal,
                file=uploaded,
                category=ProposalAttachment.Category.DETAILS_OF_ACTIVITIES,
                label=getattr(uploaded, "name", ""),
            )
    return None


def _details_of_activities_complete(proposal, step_no):
    return bool(proposal.work_plan_file) and bool(proposal.gantt_chart_file)


def _funding_context(ctx, proposal, step_no):
    ctx["existing_funding_attachments"] = proposal.attachments.filter(
        category=ProposalAttachment.Category.OTHER
    ).order_by("id")


def _single_file_part(field_name, *, key=None, label, template, ctx_key, required_for=None, extra_context=None):
    """Build a part that is one file upload on the proposal.

    ``required_for`` lists the extension types the upload is mandatory for;
    for every other proposal the part counts as complete on arrival, which is
    how the two research-only uploads behaved when they were hardcoded.
    """

    def add_context(ctx, proposal, step_no):
        if ctx_key:
            ctx[ctx_key] = _is_research(proposal)
        if extra_context:
            extra_context(ctx, proposal, step_no)

    def save(request, proposal, step_no, action):
        if request.FILES.get(field_name):
            setattr(proposal, field_name, request.FILES[field_name])
            proposal.save(update_fields=[field_name])
        return None

    def is_complete(proposal, step_no):
        if required_for and proposal.extension_type not in required_for:
            return True
        return bool(getattr(proposal, field_name, None))

    return WizardSection(
        key=key or field_name,
        label=label,
        template=template,
        add_context=add_context,
        save=save,
        is_complete=is_complete,
    )


def _is_research(proposal):
    return proposal.extension_type in RESEARCH_EXTENSION_TYPES


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

SECTIONS: dict = {}


def _register_proposal_section(section):
    SECTIONS[section.key] = section
    return section


_register_proposal_section(WizardSection(
    key="extension_type",
    label="Extension Type and Scope",
    template="services/wizard/step_1.html",
    save=_save_extension_type,
    is_complete=_extension_type_complete,
    owned_keys=("extension_type", "scope_type", "research_title"),
))

_register_proposal_section(WizardSection(
    key="title",
    label="Title",
    template="services/wizard/step_2.html",
    add_context=_title_context,
    save=_save_title,
    is_complete=_title_complete,
    owned_keys=("title",),
))

_register_proposal_section(WizardSection(
    key="proponents",
    label="Proponents",
    template="services/wizard/step_3.html",
    add_context=_proponents_context,
    save=_save_proponents,
    is_complete=_proponents_complete,
    prepare=_prepare_proponents,
))

_register_proposal_section(_single_field_part(
    "implementing_agency",
    label="Implementing Agency/Unit",
    template="services/wizard/step_4.html",
))

_register_proposal_section(WizardSection(
    key="beneficiaries",
    label="Collaborators/Beneficiaries",
    template="services/wizard/step_5.html",
    save=_save_beneficiaries,
    is_complete=_beneficiaries_complete,
    owned_keys=("beneficiaries_count", "who_beneficiaries", "beneficiaries_who"),
))

_register_proposal_section(WizardSection(
    key="sdg_thrust",
    label="SDGs / Extension Agenda",
    template="services/wizard/step_6.html",
    add_context=_sdg_context,
    save=_save_sdg,
    is_complete=_sdg_complete,
))

_register_proposal_section(_single_field_part(
    "budgetary_requirement",
    label="Budgetary Requirement",
    template="services/wizard/step_7.html",
))

_register_proposal_section(WizardSection(
    key="participants",
    label="Participants / Proposed Clients",
    template="services/wizard/step_8.html",
    add_context=_participants_context,
    save=_save_participants,
    is_complete=_participants_complete,
))

_register_proposal_section(WizardSection(
    key="gender_issues",
    label="Gender Issues / Mandates Addressed",
    template="services/wizard/step_9.html",
    add_context=_gender_issue_context,
    save=_save_gender_issues,
    is_complete=_gender_issues_complete,
))

_register_proposal_section(WizardSection(
    key="schedule_venue",
    label="Date and Venue / Extension Site",
    template="services/wizard/step_10.html",
    add_context=_schedule_context,
    save=_save_schedule,
    is_complete=_schedule_complete,
    owned_keys=("extension_venue", "estimated_month", "estimated_year"),
))

_register_proposal_section(_single_field_part(
    "rationale_background",
    label="Rationale / Background",
    template="services/wizard/step_11.html",
))

_register_proposal_section(_single_field_part(
    "significance",
    label="Significance",
    template="services/wizard/step_12.html",
))

_register_proposal_section(WizardSection(
    key="objectives",
    label="Objectives",
    template="services/wizard/step_13.html",
    add_context=_objectives_context,
    save=_save_objectives,
    is_complete=_objectives_complete,
    owned_keys=("general_objective",),
))

_register_proposal_section(_list_part(
    "methodologies",
    "methodologies",
    label="Methodology / Mechanics",
    template="services/wizard/step_14.html",
))

_register_proposal_section(_list_part(
    "output_outcomes",
    "output_outcomes",
    label="Output / Outcome",
    template="services/wizard/step_15.html",
))

_register_proposal_section(WizardSection(
    key="details_of_activities",
    label="Details of Activities",
    template="services/wizard/step_16.html",
    add_context=_details_of_activities_context,
    save=_save_details_of_activities,
    is_complete=_details_of_activities_complete,
))

_register_proposal_section(_single_file_part(
    "funding_file",
    key="funding_strategy",
    label="Funding Strategy",
    template="services/wizard/step_17.html",
    ctx_key="",
    extra_context=_funding_context,
))

_register_proposal_section(_single_file_part(
    "research_abstract_file",
    key="research_abstract",
    label="Research Abstract Upload",
    template="services/wizard/step_18.html",
    ctx_key="requires_abstract",
    required_for=RESEARCH_EXTENSION_TYPES,
))

_register_proposal_section(_single_file_part(
    "certificate_of_completion_file",
    key="certificate_of_completion",
    label="Certificate of Completion Upload",
    template="services/wizard/step_19.html",
    ctx_key="requires_certificate",
    required_for=RESEARCH_EXTENSION_TYPES,
))


#: Section keys in the order the wizard shipped with. The admin reorders steps
#: afterwards; this is only the seed.
DEFAULT_SECTION_ORDER = (
    "extension_type",
    "title",
    "proponents",
    "implementing_agency",
    "beneficiaries",
    "sdg_thrust",
    "budgetary_requirement",
    "participants",
    "gender_issues",
    "schedule_venue",
    "rationale_background",
    "significance",
    "objectives",
    "methodologies",
    "output_outcomes",
    "details_of_activities",
    "funding_strategy",
    "research_abstract",
    "certificate_of_completion",
)

DEFAULT_DESCRIPTIONS = {
    "extension_type": "Type of extension and proposal scope",
    "title": "Program, project, or activity title",
    "proponents": "Proponent details and assigned roles",
    "implementing_agency": "Office, agency, or unit responsible",
    "beneficiaries": "Beneficiary count and target group",
    "sdg_thrust": "SDGs covered and extension thrust",
    "budgetary_requirement": "Funding source and budget",
    "participants": "Participant profiling and counts",
    "gender_issues": "Applicable GAD mandates",
    "schedule_venue": "Schedule and implementation site",
    "rationale_background": "Context and alignment with SDG / thrust / GAD",
    "significance": "Importance of the proposed extension",
    "objectives": "General and specific SMART objectives",
    "methodologies": "Implementation approach",
    "output_outcomes": "Expected outputs and outcomes",
    "details_of_activities": "Work plan, Gantt chart, and related files",
    "funding_strategy": "Funding strategy template and related supporting files",
    "research_abstract": "Required for research-based proposals",
    "certificate_of_completion": "Required for research-based proposals",
}


def proposal_section_choices():
    """``(key, label)`` pairs for the admin's "built-in part" dropdown."""
    return [("", "Office-built forms only (no built-in part)")] + [
        (key, SECTIONS[key].label) for key in DEFAULT_SECTION_ORDER
    ]


def get_proposal_section(key):
    """Look a part up by key, tolerating a blank or retired key."""
    if not key:
        return None
    return SECTIONS.get(key)
