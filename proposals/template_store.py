"""
Resolution of the office document templates.

Every downloadable document in the proposal flow — the Form 1 DOCX (program
and project), the Form 2 Training Design, the clearance summary, and the
work plan / Gantt chart / line-item-budget spreadsheets — starts life as a
binary template shipped in ``proposals/template_files/``.

Administrators can replace any of those files without a code deploy: a
``ProposalTemplateOverride`` row (uploaded on the admin dashboard's
"Proposal Templates" screen or in Django admin) takes precedence over the
bundled copy. ``open_template`` is the single place that decides which copy
is live, so every generator and download view resolves templates the same
way. When no override exists — or the stored file cannot be read — the
bundled file is served instead, so a bad upload can never break downloads.
"""

from __future__ import annotations

import logging
import zipfile
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Dict, Tuple

logger = logging.getLogger(__name__)

#: The bundled templates directory lives next to the ``proposals`` package
#: root, no matter which module resolves a template.
BUNDLED_TEMPLATE_DIR = Path(__file__).resolve().parent / "template_files"

#: Registry of every template the system generates or downloads.
#:
#: ``key`` is the bundled filename and the stable identity of a slot; the
#: ``ProposalTemplateOverride.key`` column stores it verbatim so a row maps
#: one-to-one onto the file it replaces. Value: ``(label, extension)``.
TEMPLATE_FILES: Dict[str, Tuple[str, str]] = {
    "form1_program_template.docx": ("Form 1 — Extension Program Proposal", "docx"),
    "form1_project_template.docx": ("Form 1 — Extension Project Proposal", "docx"),
    "form2_training_design_template.docx": ("Form 2 — Training Design", "docx"),
    "clear_summary_template.docx": ("Clearance Summary", "docx"),
    "program_work_plan_template.xlsx": ("Program Work Plan", "xlsx"),
    "project_work_plan_template.xlsx": ("Project Work Plan", "xlsx"),
    "program_gantt_chart_template.xlsx": ("Program Gantt Chart", "xlsx"),
    "project_gantt_chart_template.xlsx": ("Project Gantt Chart", "xlsx"),
    "program_funding_template.xlsx": ("Program Line-Item Budget", "xlsx"),
    "project_funding_template.xlsx": ("Project Line-Item Budget", "xlsx"),
}

#: Choices for the ``ProposalTemplateOverride.key`` column.
TEMPLATE_KEY_CHOICES = [(key, label) for key, (label, _ext) in TEMPLATE_FILES.items()]


class TemplateNotFound(Exception):
    """Raised when neither an admin override nor a bundled copy is available."""

    def __init__(self, key):
        self.key = key
        super().__init__(f"Template '{key}' is missing.")


def bundled_path(key: str) -> Path:
    """The on-disk copy that ships with the code."""
    return BUNDLED_TEMPLATE_DIR / key


def expected_extension(key: str) -> str:
    """The file extension a replacement for ``key`` must carry."""
    try:
        return TEMPLATE_FILES[key][1]
    except KeyError:
        return ""


def is_valid_replacement(key: str, filename: str, content: bytes | None = None) -> bool:
    """Check an upload before it becomes an override.

    The filename must end with the slot's extension, and (when the bytes are
    available) the payload must be a zip archive — DOCX and XLSX both are —
    so a renamed PDF can never masquerade as an Office template.
    """
    extension = expected_extension(key)
    if not extension or not filename.lower().endswith(f".{extension}"):
        return False
    if content is not None:
        try:
            return zipfile.is_zipfile(BytesIO(content))
        except Exception:
            return False
    return True


def open_template(key: str) -> Tuple[BinaryIO, str, bool]:
    """Open the live template for ``key``.

    Returns ``(stream, filename, is_override)`` where ``stream`` is a freshly
    opened binary stream positioned at the start. The admin override wins
    when present and readable; otherwise the bundled file is used. Raises
    ``TemplateNotFound`` only when no usable copy exists at all, and
    ``ValueError`` for an unknown key.
    """
    if key not in TEMPLATE_FILES:
        raise ValueError(f"Unknown template key: {key!r}")

    # Import here: ``proposals.models`` imports this module for the key
    # choices, so a module-level import would be circular.
    from .models import ProposalTemplateOverride

    override = (
        ProposalTemplateOverride.objects.filter(key=key)
        .exclude(file="")
        .order_by("-updated_at")
        .first()
    )
    if override is not None:
        try:
            with override.file.open("rb") as stored:
                data = stored.read()
            return BytesIO(data), Path(override.file.name).name, True
        except Exception:
            logger.exception(
                "Could not read stored override for template %s; falling back "
                "to the bundled copy.",
                key,
            )

    path = bundled_path(key)
    if not path.exists():
        raise TemplateNotFound(key)
    return path.open("rb"), path.name, False


def template_slot_summaries():
    """One descriptor per slot for the admin "Proposal Templates" screen.

    Each entry pairs the slot's static metadata with its current override
    (when one is uploaded) so the screen can show which copy is live.
    """
    from .models import ProposalTemplateOverride

    overrides = {override.key: override for override in ProposalTemplateOverride.objects.all()}

    rows = []
    for key, (label, extension) in TEMPLATE_FILES.items():
        override = overrides.get(key)
        rows.append(
            {
                "key": key,
                "label": label,
                "extension": extension,
                "override": override,
                "bundled_exists": bundled_path(key).exists(),
            }
        )
    return rows
