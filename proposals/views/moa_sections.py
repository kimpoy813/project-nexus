"""
The MOA drafting wizard's built-in *parts*, as a registry.

Like the proposal wizard (see :mod:`proposals.views.step_sections`), the MOA
wizard used to be four screens the code knew by number: a ``form_map`` keyed
1-4, an ``if step == N`` chain for saving, a second one for prefilling, a
third for the per-step help bullets, and a ``step_N.html`` each. The office
could not add a step, drop one, or reorder them.

Each part is now one :class:`MOAWizardSection` carrying its form class, the
columns it writes, its help bullets, and its template. The admin points a
:class:`~details.models.MOAWizardStepConfig` row at a part — or at nothing, in
which case the step is built entirely from forms the office attaches to it.

``Proposal.MOA_FLOW`` is deliberately untouched: that is the approval status
machine staff advance, not a screen a proponent fills in.
"""

from dataclasses import dataclass
from typing import Callable
from typing import Optional

from ..forms import MOAAttachmentsForm
from ..forms import MOADraftForm
from ..forms import MOAPartiesForm
from ..forms import MOATermsForm
from ..models import Proposal
from ..models import ProposalAttachment


@dataclass(frozen=True)
class MOAWizardSection:
    """One built-in part of the MOA drafting wizard."""

    key: str
    label: str
    template: str
    form_class: type
    #: ``(form field, proposal column)`` pairs copied on a valid submit.
    field_map: tuple = ()
    help_text: tuple = ()
    #: ``True`` for the part whose form takes file uploads, so it is bound with
    #: ``request.FILES`` as well as ``request.POST``.
    binds_files: bool = False
    #: ``(proposal, request) -> None`` for parts that read the raw request
    #: (file uploads) rather than validated form data.
    save_request: Optional[Callable] = None


def _save_moa_attachments(proposal, request):
    """Store the drafted MOA and any supporting papers."""
    changed_fields = []

    moa_file = request.FILES.get("moa_file")
    if moa_file and hasattr(proposal, "moa_draft_file"):
        proposal.moa_draft_file = moa_file
        changed_fields.append("moa_draft_file")

    if changed_fields:
        proposal.save(update_fields=changed_fields)

    moa_category = getattr(ProposalAttachment.Category, "MOA", None)
    other_category = getattr(ProposalAttachment.Category, "OTHER", None)

    for uploaded in request.FILES.getlist("supporting_docs"):
        kwargs = {"proposal": proposal, "file": uploaded}
        if moa_category is not None:
            kwargs["category"] = moa_category
        elif other_category is not None:
            kwargs["category"] = other_category
        ProposalAttachment.objects.create(**kwargs)


SECTIONS: dict = {}


def _register_moa_section(section):
    SECTIONS[section.key] = section
    return section


_register_moa_section(MOAWizardSection(
    key="agreement_basics",
    label="Agreement Basics",
    template="services/moa/step_1.html",
    form_class=MOADraftForm,
    field_map=(
        ("moa_title", "moa_title"),
        ("moa_reference_no", "moa_reference_no"),
        ("moa_start_date", "moa_start_date"),
        ("moa_end_date", "moa_end_date"),
        ("purpose", "moa_purpose"),
        ("background", "moa_background"),
    ),
    help_text=(
        "Write the formal title exactly as it should appear in the document.",
        "Fill in only the dates and reference number you already know.",
        "Use a clear, concise purpose statement.",
    ),
))

_register_moa_section(MOAWizardSection(
    key="parties_signatories",
    label="Parties and Signatories",
    template="services/moa/step_2.html",
    form_class=MOAPartiesForm,
    field_map=(
        ("party_one_name", "moa_party_one_name"),
        ("party_one_representative", "moa_party_one_representative"),
        ("party_two_name", "moa_party_two_name"),
        ("party_two_representative", "moa_party_two_representative"),
        ("signatories_notes", "moa_signatories_notes"),
    ),
    help_text=(
        "Enter the official names of both parties.",
        "Add representatives if the signatory names are already assigned.",
        "Use the notes box for signers, witnesses, and titles.",
    ),
))

_register_moa_section(MOAWizardSection(
    key="scope_terms",
    label="Scope and Terms",
    template="services/moa/step_3.html",
    form_class=MOATermsForm,
    field_map=(
        ("obligations", "moa_obligations"),
        ("deliverables", "moa_deliverables"),
        ("confidentiality", "moa_confidentiality"),
    ),
    help_text=(
        "Describe each party's responsibilities using bullets if possible.",
        "Include deliverables such as reports, outputs, or endorsements.",
        "Add confidentiality or data-sharing rules if relevant.",
    ),
))

_register_moa_section(MOAWizardSection(
    key="attachments_review",
    label="Attachments and Review",
    template="services/moa/step_4.html",
    form_class=MOAAttachmentsForm,
    help_text=(
        "Upload the draft MOA if you already have the file.",
        "Attach any endorsements, letters, or annexes.",
        "This is the final review step before moving forward.",
    ),
    binds_files=True,
    save_request=_save_moa_attachments,
))


DEFAULT_SECTION_ORDER = (
    "agreement_basics",
    "parties_signatories",
    "scope_terms",
    "attachments_review",
)

DEFAULT_DESCRIPTIONS = {
    "agreement_basics": "Title, reference, dates, and purpose",
    "parties_signatories": "Names, representatives, and signers",
    "scope_terms": "Responsibilities, deliverables, and rules",
    "attachments_review": "Upload files and finalize the draft",
}


def moa_section_choices():
    """``(key, label)`` pairs for the admin's "built-in part" dropdown."""
    return [("", "Office-built forms only (no built-in part)")] + [
        (key, SECTIONS[key].label) for key in DEFAULT_SECTION_ORDER
    ]


def apply_moa_section(section, proposal, cleaned):
    """Copy a validated form's data onto the proposal columns it owns."""
    changed_fields = []
    for form_field, model_field in section.field_map:
        if not hasattr(proposal, model_field):
            continue
        setattr(proposal, model_field, cleaned.get(form_field))
        changed_fields.append(model_field)
    if changed_fields:
        proposal.save(update_fields=changed_fields)
    return changed_fields


def moa_section_initial(section, proposal):
    """Prefill values for a part's form from the proposal."""
    initial = {}
    for form_field, model_field in section.field_map:
        if hasattr(proposal, model_field):
            initial[form_field] = getattr(proposal, model_field, None)
    return initial


def mark_moa_draft_complete(proposal):
    """Hand the finished draft to staff for review.

    Called when the *last visible* step is saved — not when a particular part
    is saved — because the office can add a step after the uploads one.
    """
    if hasattr(proposal, "moa_status"):
        proposal.moa_status = getattr(Proposal.MOAStatus, "DRAFT", "DRAFT")
        proposal.save(update_fields=["moa_status"])
