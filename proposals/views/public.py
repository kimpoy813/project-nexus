"""
Public-facing Services page.
"""

from urllib3 import request
from django.db.models import Prefetch
from django.shortcuts import render
from details.models import DocumentTemplate
from details.models import DynamicFormTemplate
from details.models import ExtensionProcess
from details.models import ProcessStep
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
    }
    return render(request, "services/services_home.html", context)
