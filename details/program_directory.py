"""The Programs directory, assembled from proposals — the one place programs live.

The Programs page answers "what extension work has this institution done?", and
that work is recorded as a **proposal**:

* an approved proposal (``proposal_status`` APPROVED or COMPLETED) is the
  program once it has been implemented;
* a **legacy** proposal (``is_legacy``) is older work the office imported
  through *Admin → Legacy Records Upload*, with its own document attached.

There is deliberately no second program table. A separate table would need the
same fields entered twice, and the two copies would drift apart — which is
exactly what happened before: the office could hand-add or CSV-import a
"program" that existed nowhere in the proposal workflow.

This module therefore builds plain dictionaries from proposals, so the
directory block, its filters, and its totals all read one shape. Each entry
keeps a ``key`` that the public document view resolves back to the stored file,
so the Programs page can hand out documents without exposing storage paths.
"""

from django.urls import reverse

#: Directory entry sources, in display order of the badge.
SOURCE_APPROVED = "APPROVED"
SOURCE_LEGACY = "LEGACY"

SOURCE_LABELS = {
    SOURCE_APPROVED: "Approved proposal",
    SOURCE_LEGACY: "Legacy upload",
}

#: Proposal statuses that mean "the office approved this work".
APPROVED_PROPOSAL_STATUSES = (
    "APPROVED",
    "COMPLETED",
)

#: ``Proposal.ExtensionType`` → (directory type, research basis).
EXTENSION_TYPE_MAP = {
    "RESEARCH_FACULTY": ("RESEARCH_BASED", "FACULTY"),
    "RESEARCH_STUDENT": ("RESEARCH_BASED", "STUDENT"),
    "REQUEST_BASED": ("REQUEST_BASED", "OTHERS"),
    "COMMUNITY_BASED": ("COMMUNITY_BASED", "OTHERS"),
}

#: Choice labels for the two facets the directory reports on.
EXTENSION_TYPE_LABELS = {
    "COMMUNITY_BASED": "Community-based",
    "REQUEST_BASED": "Request-based",
    "RESEARCH_BASED": "Research-based",
}

RESEARCH_BASIS_LABELS = {
    "FACULTY": "Based on Faculty Research",
    "STUDENT": "Based on Student Research",
    "OTHERS": "Others",
}

LED_BY_LABELS = {
    "FACULTY": "Faculty",
    "JOINT": "Joint",
    "STUDENT": "Student",
}

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}


def proposal_document_key(proposal):
    """Public URL key for an approved or legacy proposal's document."""
    return f"p{proposal.pk}"


def normalize_campus_key(value):
    """Normalise a campus name so 'Sta. Maria Campus' matches 'Sta Maria'."""
    text = (value or "").lower().replace("campus", "")
    return "".join(character for character in text if character.isalnum())


def normalize_org_key(value):
    """Normalise a college, academic program, or person name for matching."""
    return "".join(character for character in (value or "").lower() if character.isalnum())


def scoped_org_key(campus_key, value):
    """Key a college or academic program within its campus."""
    org_key = normalize_org_key(value)
    if not org_key:
        return ""
    return f"{campus_key or 'all'}::{org_key}"


def _format_campus_short(raw_campus):
    text = (raw_campus or "").strip()
    if not text:
        return ""
    if text.lower() == "sta maria":
        return "Sta. Maria Campus"
    if text.lower().endswith("campus"):
        return text
    return f"{text} Campus"


def _proposal_org_units(proposal):
    """Resolve (campus, college, department) with proponent-profile fallback."""
    campus = (proposal.campus or "").strip()
    college = (proposal.college or "").strip()
    department = (proposal.department or "").strip()

    if college and department and campus:
        return campus, college, department

    candidate_profiles = []
    for prop in proposal.proponents.all():
        user = getattr(prop, "user", None)
        profile = getattr(user, "profile", None) if user else None
        if profile is not None:
            candidate_profiles.append(profile)

    if not proposal.is_legacy and getattr(proposal, "created_by_id", None):
        creator_profile = getattr(proposal.created_by, "profile", None)
        if creator_profile is not None and getattr(creator_profile, "role", "") not in {"ADMIN", "STAFF"}:
            candidate_profiles.append(creator_profile)

    campus_key = normalize_campus_key(campus)
    for profile in candidate_profiles:
        prof_campus = (getattr(profile, "campus", "") or "").strip()
        prof_campus_key = normalize_campus_key(prof_campus)
        if campus_key and prof_campus_key and prof_campus_key != campus_key:
            continue
        if not campus and prof_campus:
            campus = _format_campus_short(prof_campus)
            campus_key = prof_campus_key
        if not college and getattr(profile, "college", ""):
            college = profile.college.strip()
        if not department and getattr(profile, "department", ""):
            department = profile.department.strip()
        if campus and college and department:
            break

    return campus, college, department


def _proposal_faculty_credits(proposal, campus, college, department):
    """Unique faculty proponents credited on a published extension activity."""
    credits = []
    seen = set()

    def add_credit(key, label, subtitle_parts):
        clean_label = (label or "").strip()
        if not key or not clean_label or key in seen:
            return
        seen.add(key)
        subtitle = " · ".join(part for part in subtitle_parts if part)
        credits.append(
            {
                "key": key,
                "label": clean_label,
                "subtitle": subtitle,
            }
        )

    proponents = list(proposal.proponents.all())
    for prop in proponents:
        user = getattr(prop, "user", None)
        profile = getattr(user, "profile", None) if user else None
        if user is not None:
            name = (
                (prop.full_name or "").strip()
                or (getattr(profile, "full_name", "") or "").strip()
                or user.get_full_name().strip()
                or user.username
            )
            prof_campus = _format_campus_short(getattr(profile, "campus", "") or campus)
            prof_unit = (
                (getattr(profile, "department", "") or "").strip()
                or (getattr(profile, "college", "") or "").strip()
                or department
                or college
                or (prop.designation or "").strip()
            )
            add_credit(f"user-{user.pk}", name, [prof_campus, prof_unit])
        else:
            name = (prop.full_name or "").strip()
            norm = normalize_org_key(name)
            if norm:
                unit = department or college or (prop.designation or "").strip()
                add_credit(f"name-{norm}", name, [_format_campus_short(campus), unit])

    if not credits and not proposal.is_legacy and getattr(proposal, "created_by_id", None):
        creator = proposal.created_by
        profile = getattr(creator, "profile", None)
        role = getattr(profile, "role", "") if profile is not None else ""
        if role not in {"ADMIN", "STAFF"}:
            name = (
                (getattr(profile, "full_name", "") or "").strip()
                or creator.get_full_name().strip()
                or creator.username
            )
            prof_campus = _format_campus_short(getattr(profile, "campus", "") or campus)
            prof_unit = (
                (getattr(profile, "department", "") or "").strip()
                or (getattr(profile, "college", "") or "").strip()
                or department
                or college
            )
            add_credit(f"user-{creator.pk}", name, [prof_campus, prof_unit])

    return credits


def _proposal_led_by(proposal):
    """Who led the work: the institution's Faculty / Joint / Student split.

    The proposal does not ask the question directly — it asks what the
    extension is *based on* — so the answer comes from the extension type: a
    student-research extension is student-led, everything else faculty-led.
    The directory says so rather than guessing from account roles, which do not
    include students.
    """
    if proposal.extension_type == "RESEARCH_STUDENT":
        return "STUDENT"
    return "FACULTY"


def _month_label(value):
    """``"5"``/``"May"`` → ``"May"`` so a stored number still reads well."""
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit() and int(text) in MONTH_NAMES:
        return MONTH_NAMES[int(text)]
    return text


def _proposal_duration(proposal):
    """A human schedule: dates if recorded, else the imported date/venue, else
    the planned month and year.
    """
    if proposal.start_date and proposal.end_date:
        start = proposal.start_date.strftime("%B %d, %Y")
        end = proposal.end_date.strftime("%B %d, %Y")
        return start if start == end else f"{start} – {end}"
    if proposal.start_date:
        return proposal.start_date.strftime("%B %d, %Y")

    date_venue = (proposal.date_venue or "").strip()
    if date_venue:
        # Legacy imports store the published schedule here.
        return date_venue[:150]

    parts = [_month_label(proposal.estimated_month), str(proposal.estimated_year or "")]
    return " ".join(part for part in parts if part)[:150]


def _proposal_objectives(proposal):
    """The proposal's objective text, one line per objective."""
    lines = []
    general = (proposal.general_objective or proposal.objectives_general or "").strip()
    if general:
        lines.append(general)

    specific_text = (proposal.objectives_specific or "").strip()
    if specific_text:
        lines.append(specific_text)

    lines.extend(
        (objective.objective or "").strip()
        for objective in proposal.specific_objectives.all()
        if (objective.objective or "").strip()
    )
    return "\n".join(lines)


def _proposal_year(proposal):
    if proposal.estimated_year:
        return proposal.estimated_year
    if proposal.year:
        return proposal.year
    if proposal.start_date:
        return proposal.start_date.year
    return proposal.last_saved_at.year if proposal.last_saved_at else None


def _cover_image_url(proposal):
    """The first visible documentation photo, used as the card's picture."""
    for photo in proposal.documentation_photos.all():
        if photo.is_visible and photo.image:
            return photo.image.url
    return ""


def _document_available(proposal):
    """Whether the entry has a file the directory can hand out."""
    if proposal.is_legacy and proposal.legacy_proposal_file:
        return True
    return any(
        document.document_type == "SIGNED_PROPOSAL" and document.file
        for document in proposal.final_documents.all()
    )


def _proposal_entry(proposal):
    extension_type, research_basis = EXTENSION_TYPE_MAP.get(
        proposal.extension_type, ("COMMUNITY_BASED", "OTHERS")
    )
    source = SOURCE_LEGACY if proposal.is_legacy else SOURCE_APPROVED
    led_by = _proposal_led_by(proposal)
    document_available = _document_available(proposal)
    resolved_campus, college, department = _proposal_org_units(proposal)
    raw_campus = (proposal.campus or resolved_campus or "").strip()
    campus_key = normalize_campus_key(raw_campus)
    college_key = scoped_org_key(campus_key, college)
    program_key = scoped_org_key(campus_key, department)
    faculty_credits = _proposal_faculty_credits(
        proposal, raw_campus, college, department
    )
    is_completed = bool(
        proposal.proposal_status == "COMPLETED"
        or proposal.status == "COMPLETED"
    )

    return {
        "key": proposal_document_key(proposal),
        "proposal_id": proposal.pk,
        "source": source,
        "source_label": SOURCE_LABELS[source],
        "is_completed": is_completed,
        "title": proposal.display_title,
        "campus": raw_campus,
        "campus_key": campus_key,
        "college": college,
        "college_key": college_key,
        "department": department,
        "program_key": program_key,
        "faculty_credits": faculty_credits,
        "faculty_keys": [credit["key"] for credit in faculty_credits],
        "year": _proposal_year(proposal),
        "extension_type": extension_type,
        "extension_type_label": EXTENSION_TYPE_LABELS[extension_type],
        "research_basis": research_basis,
        "research_basis_label": RESEARCH_BASIS_LABELS[research_basis],
        "led_by": led_by,
        "led_by_label": LED_BY_LABELS[led_by],
        "target_community": proposal.beneficiaries_who or "",
        "duration": _proposal_duration(proposal),
        "objectives": _proposal_objectives(proposal),
        "research_output": (proposal.research_title or "").strip(),
        "expected_deliverables": (
            (proposal.output_outcome or "").strip()
            or (proposal.moa_deliverables or "").strip()
        ),
        "student_participants": proposal.student_participants or 0,
        "faculty_participants": proposal.faculty_participants or 0,
        "research_staff_participants": proposal.research_staff_participants or 0,
        "beneficiaries": proposal.beneficiaries_count or 0,
        "cover_image_url": _cover_image_url(proposal),
        "document_label": (
            "View legacy upload" if source == SOURCE_LEGACY else "View approved proposal"
        )
        if document_available
        else "",
        "document_url": (
            reverse("program_document", kwargs={"key": proposal_document_key(proposal)})
            if document_available
            else ""
        ),
        "document_available": document_available,
    }


def build_program_entries():
    """Every approved and legacy proposal, newest year first."""
    from proposals.models import Proposal

    proposals = (
        Proposal.objects.filter(proposal_status__in=APPROVED_PROPOSAL_STATUSES)
        .select_related("created_by__profile")
        .prefetch_related(
            "proponents__user__profile",
            "specific_objectives",
            "final_documents",
            "documentation_photos",
        )
        .order_by("-last_saved_at")
    )

    entries = [_proposal_entry(proposal) for proposal in proposals]

    source_rank = {SOURCE_APPROVED: 0, SOURCE_LEGACY: 1}
    entries.sort(
        key=lambda entry: (
            -(entry["year"] or 0),
            source_rank.get(entry["source"], 9),
            (entry["title"] or "").lower(),
        )
    )
    return entries


def program_entry_stats(entries, total_campuses=None):
    """The totals row above the directory."""
    campus_keys = {
        entry.get("campus_key") or normalize_campus_key(entry.get("campus"))
        for entry in entries
        if entry.get("campus")
    }
    campus_keys.discard("")
    campus_count = len(campus_keys)
    if total_campuses is None:
        try:
            from accounts.models import Campus

            seeded_keys = {
                normalize_campus_key(name)
                for name in Campus.objects.values_list("name", flat=True)
            }
            seeded_keys.discard("")
            total_campuses = len(seeded_keys | campus_keys)
        except Exception:
            total_campuses = campus_count
    else:
        total_campuses = max(int(total_campuses), campus_count)

    return {
        "program_count": len(entries),
        "campus_count": campus_count,
        "total_campuses": total_campuses,
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

    Returns ``None`` when the key names nothing public. A proposal is only
    reachable once approved, so a draft's signed document cannot be fetched by
    guessing its id.
    """
    from proposals.models import Proposal

    key = (key or "").strip()
    if len(key) < 2 or key[0] != "p":
        return None

    proposal = (
        Proposal.objects.filter(pk=key[1:])
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
