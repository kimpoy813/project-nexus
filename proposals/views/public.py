"""
Public-facing Services page.
"""

from django.db.models import Prefetch
from django.shortcuts import render
from details.models import DocumentTemplate
from details.models import DynamicFormTemplate
from details.models import ExtensionProcess
from details.models import ProcessStep
from details.models import ServiceSectionCopy
from details.models import SitePage
from details.models import WorkflowPhase
from ..models import ExtensionThrust
from ..models import Proposal
from ..models import SDG
from .constants import STEP_LABELS, TOTAL_STEPS


def _build_status_flow(choices, progress_map):
    return [
        {
            "code": value,
            "label": label,
            "progress": progress_map.get(value, 0),
        }
        for value, label in choices
    ]


def services_home(request):
    sdgs = SDG.objects.all().order_by("code")
    thrusts = ExtensionThrust.objects.all().order_by("name")
    process_records = (
        ExtensionProcess.objects
        .prefetch_related(
            Prefetch(
                "steps",
                queryset=ProcessStep.objects.order_by("order", "id"),
            )
        )
        .order_by("order", "id")
    )
    office_templates = DocumentTemplate.objects.filter(is_active=True).order_by("category", "title")
    dynamic_form_templates = DynamicFormTemplate.objects.filter(is_active=True).prefetch_related("fields").order_by("applies_to", "name")

    # Status codes and progress maps stay in the model because they drive real
    # permissions; only the public presentation is admin-editable.
    status_flows = {
        "proposal": (Proposal.ProposalStatus.choices, Proposal.PROPOSAL_PROGRESS_MAP),
        "moa": (Proposal.MOAStatus.choices, Proposal.MOA_PROGRESS_MAP),
        "implementation": (Proposal.ImplementationStatus.choices, Proposal.IMPLEMENTATION_PROGRESS_MAP),
    }

    workflow_phases = []
    weight_total = 0
    for phase in WorkflowPhase.ordered_visible():
        choices_map = status_flows.get(phase.key)
        weight_total += phase.weight_percent
        workflow_phases.append({
            "key": phase.key,
            "label": phase.label,
            "summary": phase.summary,
            "weight_label": phase.weight_label,
            "weight_percent": phase.weight_percent,
            # The ring is announced as an image; the figure drawn inside it is
            # decorative, so the number is never read out twice.
            "ring_label": f"{phase.label}: {phase.weight_percent}% of overall progress",
            "statuses": _build_status_flow(*choices_map) if choices_map else [],
        })

    # Admin-editable section copy. Rows are seeded by migration; missing rows are
    # created on demand so the page renders its defaults even if a row was
    # somehow deleted, and the live placeholders get the current figures.
    stored_blocks = {block.key: block for block in ServiceSectionCopy.objects.all()}
    if len(stored_blocks) < len(ServiceSectionCopy.Key.choices):
        for key, _label in ServiceSectionCopy.Key.choices:
            stored_blocks.setdefault(key, ServiceSectionCopy.get_for(key))

    try:
        wizard_count = int(TOTAL_STEPS)
    except (TypeError, ValueError):
        wizard_count = len(list(STEP_LABELS))

    services_copy = {}
    jump_links = []
    ordered_blocks = sorted(
        stored_blocks.values(), key=lambda block: (block.order, block.id)
    )
    for block in ordered_blocks:
        values = {"count": wizard_count, "total": weight_total}
        rendered = {
            "eyebrow": block.eyebrow,
            "heading": block.rendered_heading(**values),
            "subheading": block.subheading,
            "footer": block.rendered_footer(**values),
            "empty_text": block.empty_text,
            "nav_label": block.nav_label,
            "anchor": block.anchor or block.key,
            "is_visible": block.is_visible,
        }
        services_copy[block.key] = rendered
        if rendered["is_visible"] and rendered["nav_label"] and rendered["anchor"]:
            jump_links.append({"anchor": rendered["anchor"], "label": rendered["nav_label"]})

    context = {
        "sdgs": sdgs,
        "thrusts": thrusts,
        "process_records": process_records,
        "workflow_phases": workflow_phases,
        "workflow_weight_total": weight_total,
        "wizard_steps": STEP_LABELS,
        "total_wizard_steps": TOTAL_STEPS,
        "office_templates": office_templates,
        "dynamic_form_templates": dynamic_form_templates,
        "page": SitePage.get_for(SitePage.Slug.SERVICES),
        "services_copy": services_copy,
        "jump_links": jump_links,
    }
    return render(request, "services/services_home.html", context)
