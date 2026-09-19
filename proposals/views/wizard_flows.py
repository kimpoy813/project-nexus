"""
The two wizard flows: which parts exist, and where the office put them.

Everything that needs to know "how many steps are there", "what comes after
step 7", or "does this step render a built-in part" goes through one of the
two :class:`~proposals.views.step_flow.StepFlow` objects built here. The
default rows are declared next to the registries so the seeding in the data
migration, the admin screens, and the runtime backfill cannot drift apart.
"""

from details.models import MOAWizardStepConfig
from details.models import ProposalWizardStepConfig

from . import moa_sections
from . import step_sections
from .step_flow import StepFlow


def _build_defaults(section_order, descriptions, sections):
    return [
        {
            "step_no": index,
            "section_key": key,
            "title": sections[key].label,
            "description": descriptions.get(key, ""),
        }
        for index, key in enumerate(section_order, start=1)
    ]


DEFAULT_PROPOSAL_STEPS = _build_defaults(
    step_sections.DEFAULT_SECTION_ORDER,
    step_sections.DEFAULT_DESCRIPTIONS,
    step_sections.SECTIONS,
)

DEFAULT_MOA_STEPS = _build_defaults(
    moa_sections.DEFAULT_SECTION_ORDER,
    moa_sections.DEFAULT_DESCRIPTIONS,
    moa_sections.SECTIONS,
)


proposal_flow = StepFlow(
    model=ProposalWizardStepConfig,
    defaults=DEFAULT_PROPOSAL_STEPS,
    sections=step_sections.SECTIONS,
    fallback_template="services/wizard/step_dynamic.html",
    label="Proposal",
)

moa_flow = StepFlow(
    model=MOAWizardStepConfig,
    defaults=DEFAULT_MOA_STEPS,
    sections=moa_sections.SECTIONS,
    fallback_template="services/moa/step_dynamic.html",
    label="MOA",
)


def section_choices_for(wizard):
    """``(key, label)`` pairs for the given wizard's built-in-part dropdown."""
    if wizard == "moa":
        return moa_sections.moa_section_choices()
    return step_sections.proposal_section_choices()
