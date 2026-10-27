"""One directory of extension programs, assembled from the records that hold them.

The Programs page answers a simple question — "what extension programs has the
institution run?" — but those programs live in two different places:

* **Proposals on the system.** A proposal that has been approved *is* an
  extension program once it is implemented. Its title, campus, year, extension
  type, objectives, and beneficiaries are already recorded by the proponent,
  and its signed document is already on file. Re-typing any of that into a
  second table would guarantee the two drift apart.
* **Legacy uploads.** Work that predates the system. The office imports it
  through *Legacy Proposals* (``Proposal.is_legacy``) with the original
  document attached, or — when there is no proposal record at all — adds an
  ``ExtensionProgram`` row with the paper trail uploaded as its document.

This module merges those three sources into one list of plain dictionaries, so
the directory block, its filters, and its totals all read a single shape and
nothing needs to know which table a program came from. Each entry keeps a
``key`` that the public document view resolves back to the stored file, so the
Programs page can hand out documents without exposing storage paths.
"""

from django.urls import reverse

from .models import ExtensionProgram

#: Directory entry sources, in display order of the badge.
SOURCE_APPROVED = "APPROVED"
SOURCE_LEGACY = "LEGACY"
SOURCE_RECORD = "RECORD"

SOURCE_LABELS = {
    SOURCE_APPROVED: "Approved proposal",
    SOURCE_LEGACY: "Legacy upload",
    SOURCE_RECORD: "Program record",
}

#: Proposal statuses that mean "the office approved this proposal".
APPROVED_PROPOSAL_STATUSES = (
    "APPROVED",
    "COMPLETED",
)


def proposal_document_key(proposal):
    """Public URL key for an approved or legacy proposal's document."""
    return f"p{proposal.pk}"


def record_document_key(program):
    """Public URL key for an uploaded legacy document on a program record."""
    return f"r{program.pk}"


def _extension_type_from_proposal(value):
    """Map ``Proposal.ExtensionType`` onto the directory's type + basis."""
    mapping = {
        "RESEARCH_FACULTY": ("RESEARCH_BASED", "FACULTY"),
        "RESEARCH_STUDENT": ("RESEARCH_BASED", "STUDENT"),
        "REQUEST_BASED": ("REQUEST_BASED", "OTHERS"),
        "COMMUNITY_BASED": ("COMMUNITY_BASED", "OTHERS"),
    }
    return mapping.get(value, ("COMMUNITY_BASED", "OTHERS"))


def _proposal_led_by(proposal):
    """Who led the work, from the proposal's assigned proponents.

    Faculty- and student-led proposals record that in the extension type; when
    proponents of both kinds are attached the work is joint.
    """
    roles = set()
    for proponent in proposal.proponents.all():
        profile = getattr(proponent.user, "profile", None)
        role = (getattr(profile, "role", "") or "").upper()
        if role == "FACULTY":
            roles.add("FACULTY")
        elif role:
            roles.add("STUDENT")
    if len(roles) > 1:
        return "JOINT"
    if roles:
        return roles.pop()
    if proposal.extension_type == "RESEARCH_STUDENT":
        return "STUDENT"
    return "FACULTY"


def _proposal_duration(proposal):
    parts = [part for part in (proposal.estimated_month, proposal.estimated_year) if part]
    return " ".join(str(part) for part in parts)[:150]


def _proposal_objectives(proposal):
    """The proposal's objective text, one line per objective."""
    lines = []
    general = (proposal.general_objective or "").strip()
    if general:
        lines.append(general)
    lines.extend(
        (objective.objective or "").strip()
        for objective in proposal.specific_objectives.all()
        if (objective.objective or "").strip()
    )
    return "\n".join(lines)


def _signed_proposal_exists(proposal):
    """Whether the proposal has a signed document the directory can hand out."""
    for document in proposal.final_documents.all():
        if document.document_type == "SIGNED_PROPOSAL" and document.file:
            return True
    return False


def _proposal_year(proposal):
    if proposal.estimated_year:
        return proposal.estimated_year
    return proposal.last_saved_at.year if proposal.last_saved_at else None


def _proposal_entry(proposal, source, record=None):
    """One directory entry for a proposal (approved or legacy).

    ``record`` is the linked ``ExtensionProgram`` row, when the office made one
    to add photos or corrections; its own values win over the proposal's.
    """
    extension_type, research_basis = _extension_type_from_proposal(
        proposal.extension_type
    )

    entry = {
        "key": proposal_document_key(proposal),
        "source": source,
        "source_label": SOURCE_LABELS[source],
        "title": proposal.display_title,
        "campus": proposal.campus or "",
        "year": _proposal_year(proposal),
        "extension_type": extension_type,
        "extension_type_label": dict(
            ExtensionProgram.ExtensionType.choices
        ).get(extension_type, extension_type),
        "research_basis": research_basis,
        "research_basis_label": dict(
            ExtensionProgram.ResearchBasis.choices
        ).get(research_basis, research_basis),
        "led_by": _proposal_led_by(proposal),
        "target_community": proposal.beneficiaries_who or "",
        "duration": _proposal_duration(proposal),
        "objectives": _proposal_objectives(proposal),
        "student_participants": 0,
        "faculty_participants": 0,
        "research_staff_participants": 0,
        # The proposal counts everyone it serves as beneficiaries; the
        # per-group split only exists on manually maintained records.
        "beneficiaries": proposal.beneficiaries_count or 0,
        "led_by_label": dict(ExtensionProgram.Proponent.choices).get(
            _proposal_led_by(proposal), ""
        ),
        "cover_image_url": "",
        "document_label": "",
        "document_url": "",
        "document_available": False,
        "record": record,
    }

    if source == SOURCE_LEGACY and getattr(proposal, "legacy_proposal_file", None):
        entry["document_label"] = "View legacy upload"
        entry["document_available"] = True
    elif source == SOURCE_APPROVED and _signed_proposal_exists(proposal):
        entry["document_label"] = "View approved proposal"
        entry["document_available"] = True

    if record is not None:
        # A record linked to this proposal fills in what the proposal does not
        # track (participant split, cover photo) and may correct the rest.
        for field in (
            "campus",
            "target_community",
            "duration",
            "objectives",
            "student_participants",
            "faculty_participants",
            "research_staff_participants",
        ):
            if getattr(record, field):
                entry[field] = getattr(record, field)
        if record.beneficiaries:
            entry["beneficiaries"] = record.beneficiaries
        if record.year:
            entry["year"] = record.year
        if record.cover_image:
            entry["cover_image_url"] = record.cover_image.url
        if record.document:
            entry["document_label"] = "View legacy upload"
            entry["document_available"] = True

    return entry


def _record_entry(record):
    """One directory entry for a standalone (legacy) program record."""
    entry = {
        "key": record_document_key(record),
        "source": SOURCE_RECORD,
        "source_label": SOURCE_LABELS[SOURCE_RECORD],
        "title": record.title,
        "campus": record.campus or "",
        "year": record.year,
        "extension_type": record.extension_type,
        "extension_type_label": record.get_extension_type_display(),
        "research_basis": record.research_basis,
        "research_basis_label": record.get_research_basis_display(),
        "led_by": record.led_by,
        "led_by_label": record.get_led_by_display(),
        "target_community": record.target_community,
        "duration": record.duration,
        "objectives": record.objectives,
        "student_participants": record.student_participants,
        "faculty_participants": record.faculty_participants,
        "research_staff_participants": record.research_staff_participants,
        "beneficiaries": record.beneficiaries,
        "cover_image_url": record.cover_image.url if record.cover_image else "",
        "document_label": "View legacy upload" if record.document else "",
        "document_url": "",
        "document_available": bool(record.document),
        "record": record,
    }
    return entry


def build_program_entries():
    """Every published program, newest year first.

    Approved proposals come first within a year, then legacy uploads, then
    standalone records — the order the office thinks in when reviewing a year.
    """
    from proposals.models import Proposal

    records = list(ExtensionProgram.objects.filter(is_visible=True).select_related("proposal"))
    records_by_proposal = {
        record.proposal_id: record for record in records if record.proposal_id
    }

    proposals = list(
        Proposal.objects.filter(
            proposal_status__in=APPROVED_PROPOSAL_STATUSES,
        )
        .exclude(created_by__isnull=True)
        .prefetch_related(
            "proponents__user__profile",
            "specific_objectives",
            "final_documents",
        )
        .order_by("-last_saved_at")
    )

    entries = []
    proposal_ids = set()
    for proposal in proposals:
        if proposal.pk in proposal_ids:
            continue
        proposal_ids.add(proposal.pk)
        source = SOURCE_LEGACY if proposal.is_legacy else SOURCE_APPROVED
        entries.append(
            _proposal_entry(proposal, source, record=records_by_proposal.get(proposal.pk))
        )

    for record in records:
        if record.proposal_id and record.proposal_id in proposal_ids:
            continue
        entries.append(_record_entry(record))

    # A document that lives in this system is served through the public
    # document route, keyed by the entry — never by a storage path.
    for entry in entries:
        if not entry["document_url"] and entry["document_available"]:
            entry["document_url"] = reverse(
                "program_document", kwargs={"key": entry["key"]}
            )

    source_rank = {SOURCE_APPROVED: 0, SOURCE_LEGACY: 1, SOURCE_RECORD: 2}
    entries.sort(
        key=lambda entry: (
            -(entry["year"] or 0),
            source_rank.get(entry["source"], 9),
            (entry["title"] or "").lower(),
        )
    )
    return entries


def program_entry_stats(entries):
    """The totals row above the directory."""
    return {
        "program_count": len(entries),
        "campus_count": len({entry["campus"] for entry in entries if entry["campus"]}),
        "beneficiaries": sum(entry["beneficiaries"] or 0 for entry in entries),
        "students": sum(entry["student_participants"] or 0 for entry in entries),
        "faculty": sum(entry["faculty_participants"] or 0 for entry in entries),
        "research_staff": sum(
            entry["research_staff_participants"] or 0 for entry in entries
        ),
        "approved": sum(1 for entry in entries if entry["source"] == SOURCE_APPROVED),
        "legacy": sum(1 for entry in entries if entry["source"] == SOURCE_LEGACY),
    }


def find_program_document(key):
    """Resolve a public document ``key`` to ``(file_field, filename, title)``.

    Returns ``None`` when the key names nothing public. The rules mirror the
    directory: a proposal is only reachable once approved, and a record only
    while it is published — so a draft's signed document cannot be fetched by
    guessing its id.
    """
    from proposals.models import Proposal

    key = (key or "").strip()
    if len(key) < 2:
        return None

    prefix, _, identifier = key[0], key[0], key[1:]

    if prefix == "p":
        proposal = (
            Proposal.objects.filter(pk=identifier)
            .prefetch_related("final_documents")
            .first()
        )
        if proposal is None:
            return None
        if proposal.proposal_status not in APPROVED_PROPOSAL_STATUSES:
            return None

        if proposal.is_legacy and proposal.legacy_proposal_file:
            return (
                proposal.legacy_proposal_file,
                proposal.legacy_proposal_file.name.rsplit("/", 1)[-1],
                proposal.display_title,
            )

        signed = proposal.final_documents.filter(
            document_type="SIGNED_PROPOSAL", is_current=True
        ).first() or proposal.final_documents.filter(
            document_type="SIGNED_PROPOSAL"
        ).first()
        if signed and signed.file:
            return (
                signed.file,
                signed.file.name.rsplit("/", 1)[-1],
                proposal.display_title,
            )
        return None

    if prefix == "r":
        record = ExtensionProgram.objects.filter(pk=identifier).first()
        if record is None or not record.is_visible or not record.document:
            return None
        return (
            record.document,
            record.document.name.rsplit("/", 1)[-1],
            record.title,
        )

    return None
