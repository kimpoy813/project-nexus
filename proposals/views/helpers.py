"""
Small formatting and lookup helpers used across the proposal views.
"""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from accounts.models import Signatory

from docx.shared import Pt
import re
from ..models import MOANotification
from ..models import Proposal


def _format_numbered_list_paragraph(paragraph):
    """
    Force consistent numbering alignment (hanging indent) for all list items.
    """
    pf = paragraph.paragraph_format
    pf.left_indent = Pt(36)          # 0.5 inch
    pf.first_line_indent = Pt(-18)   # hanging by 0.25 inch
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)


def _to_int(value, default=0):
    value = str(value or "").strip()
    return int(value) if value.isdigit() else default


def _to_roman(n: int) -> str:
    vals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def _strip_phase_prefix(text: str) -> str:
    return re.sub(r"^Phase\s+[IVXLCDM]+\s+", "", (text or "").strip(), flags=re.I).strip()


def _extract_last_name(full_name: str) -> str:
    s = (full_name or "").strip()
    if not s:
        return ""

    # Remove common prefixes and punctuation
    s = re.sub(r"^(DR\.|MR\.|MS\.|MRS\.|ENGR\.|ATTY\.)\s+", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"[,\.\(\)]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    parts = s.split(" ")
    if not parts:
        return ""

    # Last "word" is usually the last name
    return parts[-1].title()


def _get_signatory(position_title: str, *, campus: str = "", college: str = "", department: str = ""):
    campus = (campus or "").strip()
    college = (college or "").strip()
    department = (department or "").strip()

    return Signatory.objects.filter(
        position_title=position_title,
        campus=campus,
        college=college,
        department=department,
    ).first()


def _proponent_line(proposal: Proposal) -> str:
    props = list(proposal.proponents.all().order_by("id"))
    names = [(p.full_name or "").strip() for p in props]
    names = [n for n in names if n]

    if names:
        if len(names) == 1:
            return names[0]
        return f"{names[0]}, et.al."

    prof = getattr(proposal.created_by, "profile", None)
    return getattr(prof, "full_name", "") or proposal.created_by.get_username()


def _extract_points(summary_text: str):
    """
    Converts summary_text into clean numbered points.

    - Accepts lines like:
        Step 1 – Extension Type and Scope: Sample
        - Step 2 - Title: Sample
        1. Step 3 – Proponents: Sample; Comment
        • Sample
    - Removes bullet/number prefixes
    - Removes "Step X – <title>:" prefix entirely, leaving only the comment text
    """
    points = []
    for line in (summary_text or "").splitlines():
        s = (line or "").strip()
        if not s:
            continue

        # remove bullet / numbering prefixes
        s = re.sub(r"^[-•\*\u2022]\s*", "", s).strip()
        s = re.sub(r"^\d+[\.\)]\s*", "", s).strip()

        # remove "Step X – Title:" prefix (keep only the actual comment)
        s = re.sub(r"^Step\s+\d+\s*[-–—]\s*[^:]{0,200}:\s*", "", s, flags=re.I).strip()
        # fallback: "Step X: ..." or "Step X - ..."
        s = re.sub(r"^Step\s+\d+\s*[:\-–—]\s*", "", s, flags=re.I).strip()

        if s:
            points.append(s)

    # if staff wrote a single paragraph without line breaks, keep it as one point
    if not points and (summary_text or "").strip():
        points = [(summary_text or "").strip()]

    return points


def _apply_numbering(paragraph, *, num_id: int = 1, ilvl: int = 0):
    # Apply Word numbering using an existing numId in the template doc.
    p = paragraph._p
    pPr = p.get_or_add_pPr()

    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        numPr = OxmlElement("w:numPr")
        pPr.append(numPr)

    ilvl_el = numPr.find(qn("w:ilvl"))
    if ilvl_el is None:
        ilvl_el = OxmlElement("w:ilvl")
        numPr.append(ilvl_el)
    ilvl_el.set(qn("w:val"), str(ilvl))

    numId_el = numPr.find(qn("w:numId"))
    if numId_el is None:
        numId_el = OxmlElement("w:numId")
        numPr.append(numId_el)
    numId_el.set(qn("w:val"), str(num_id))


def _insert_paragraph_after(paragraph, text="", style=None):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style is not None:
        new_para.style = style
    if text:
        new_para.add_run(text)
    return new_para


def _notify_proponent(proposal, sent_by, notification_type, message):
    """Send an in-app MOA notification to every proponent on the proposal."""
    recipients = set()
    if proposal.created_by_id:
        recipients.add(proposal.created_by_id)
    for proponent in proposal.proponents.exclude(user__isnull=True).select_related("user"):
        if proponent.user_id:
            recipients.add(proponent.user_id)

    for uid in recipients:
        MOANotification.objects.create(
            proposal=proposal,
            recipient_id=uid,
            sent_by=sent_by,
            notification_type=notification_type,
            message=message,
        )


def _apply_moa_requirement_choice(request, proposal) -> None:
    """Persist the proponent's MOA requirement choice from wizard step 1.

    The MOA phase is optional for every extension type (not just
    research-based ones). The choice can only change while the MOA phase
    has not started yet.
    """
    from django.contrib import messages

    raw = (request.POST.get("requires_moa") or "").strip()
    if raw not in {"1", "0"}:
        return
    wants_moa = raw == "1"
    moa_not_started = proposal.moa_status in {
        Proposal.MOAStatus.NOT_STARTED,
        Proposal.MOAStatus.NOT_REQUIRED,
    }
    if wants_moa and not proposal.requires_moa and moa_not_started:
        proposal.requires_moa = True
        proposal.moa_status = Proposal.MOAStatus.NOT_STARTED
        proposal.save(update_fields=["requires_moa", "moa_status", "last_saved_at"])
    elif not wants_moa and proposal.requires_moa:
        if moa_not_started:
            proposal.mark_moa_not_required()
        else:
            messages.warning(
                request,
                "The MOA requirement can no longer be changed because the MOA phase has already started for this proposal.",
            )
