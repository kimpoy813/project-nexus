"""
Public-facing Services page.
"""

from django.shortcuts import render
from details.models import SitePage
from details.models import WorkflowPhase
from details.views import build_visible_blocks
from ..models import Proposal
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
    """The Services page.

    Processes, the Template Library, and the office forms are no longer
    queried here: each is a content block on the page, so its data comes from
    ``build_visible_blocks`` via the source registry — one query, one renderer,
    one place to edit. What stays is what genuinely belongs to this page: the
    workflow phases and the status maps that drive real permissions.
    """
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

    page = SitePage.get_for(SitePage.Slug.SERVICES)
    context = {
        "workflow_phases": workflow_phases,
        "workflow_weight_total": weight_total,
        "wizard_steps": STEP_LABELS,
        "total_wizard_steps": TOTAL_STEPS,
        "page": page,
        "visible_blocks": build_visible_blocks(page),
    }
    return render(request, "services/services_home.html", context)
