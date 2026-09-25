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

The same screen also lets the office *add* files that no code reads yet
(``CustomProposalTemplate``), so a new form or a changed format can be kept
in the system before the generator that uses it is written. The helpers
here cover both directions: which formats are acceptable, what content type
a download should carry, and the stable ``key`` a new file is filed under.
"""

from __future__ import annotations

import logging
import re
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

#: Content type a download of each supported format should carry. Office
#: formats have no reliable ``mimetypes`` entry on every platform, so the
#: answer is looked up here first.
CONTENT_TYPES: Dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "doc": "application/msword",
    "xls": "application/vnd.ms-excel",
    "pdf": "application/pdf",
    "csv": "text/csv",
    "txt": "text/plain",
    "zip": "application/zip",
}

#: Formats an administrator may add as a *new* template file. A built-in slot
#: keeps validating against its own registered extension instead, because the
#: generator behind it reads exactly one format.
CUSTOM_TEMPLATE_EXTENSIONS: Tuple[str, ...] = (
    "docx",
    "xlsx",
    "doc",
    "xls",
    "pptx",
    "pdf",
    "csv",
)

#: The OOXML formats are zip archives, but a generic ZIP signature is not
#: enough to tell an editable workbook from a renamed Word document. Require
#: the package parts each built-in slot needs before accepting a replacement.
_OOXML_REQUIRED_PARTS = {
    "docx": {"[Content_Types].xml", "_rels/.rels", "word/document.xml"},
    "xlsx": {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"},
}
_ZIP_EXTENSIONS = {"docx", "xlsx", "pptx"}
_OLE_EXTENSIONS = {"doc", "xls"}
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0"


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
    available) the payload must contain the package parts for that exact
    Office format. DOCX and XLSX are both ZIP archives, so checking only the
    ZIP signature would allow a renamed Word document to replace a workbook.
    """
    extension = expected_extension(key)
    if not extension or not filename.lower().endswith(f".{extension}"):
        return False
    if content is not None:
        try:
            with zipfile.ZipFile(BytesIO(content)) as package:
                names = set(package.namelist())
            required_parts = _OOXML_REQUIRED_PARTS.get(extension)
            if required_parts:
                if not required_parts.issubset(names):
                    return False
                if extension == "xlsx" and not any(
                    name.startswith("xl/worksheets/") and name.endswith(".xml")
                    for name in names
                ):
                    return False
                return True
            return zipfile.is_zipfile(BytesIO(content))
        except (OSError, zipfile.BadZipFile, ValueError):
            return False
    return True


def file_extension(filename: str) -> str:
    """The lower-case extension of ``filename``, without the dot."""
    return Path(filename or "").suffix.lower().lstrip(".")


def content_type_for(filename: str) -> str:
    """The download content type for ``filename``.

    Falls back to a generic binary stream, so an unexpected extension is
    still downloadable rather than served as something the browser tries to
    render.
    """
    import mimetypes

    extension = file_extension(filename)
    if extension in CONTENT_TYPES:
        return CONTENT_TYPES[extension]
    return mimetypes.guess_type(filename or "")[0] or "application/octet-stream"


def custom_file_problem(filename: str, content: bytes | None = None) -> str:
    """Why ``filename`` cannot be added as a new template, or ``""`` if it can.

    Built-in slots are validated by :func:`is_valid_replacement` against the
    one format their generator reads. A file the office adds itself is only
    held to the format list on this screen, plus a signature check so a
    renamed file cannot be stored as an Office document.
    """
    extension = file_extension(filename)
    if not extension:
        return "The file needs a name ending in its format, for example budget.xlsx."
    if extension not in CUSTOM_TEMPLATE_EXTENSIONS:
        allowed = ", ".join(f".{ext}" for ext in CUSTOM_TEMPLATE_EXTENSIONS)
        return f".{extension} files are not accepted here. Use one of: {allowed}."

    if content is None:
        return ""

    if extension in _ZIP_EXTENSIONS:
        try:
            if not zipfile.is_zipfile(BytesIO(content)):
                return f"The file is not a valid .{extension} document."
        except Exception:
            return f"The file is not a valid .{extension} document."
    elif extension in _OLE_EXTENSIONS:
        if not content.startswith(_OLE_SIGNATURE):
            return f"The file is not a valid .{extension} document."
    elif extension == "pdf" and not content.lstrip()[:4] == b"%PDF":
        return "The file is not a valid .pdf document."
    elif not content.strip():
        return "The file is empty."

    return ""


def custom_key_for(title: str, filename: str) -> str:
    """The stable identity an added template is filed under.

    The key is a slug of the title plus the file's extension, so later code
    can ask for ``"moa_renewal_form.docx"`` the same way it asks for a
    bundled slot. A title with no usable characters falls back to the
    uploaded filename.
    """
    from django.utils.text import slugify

    extension = file_extension(filename)
    stem = slugify(title or "") or slugify(Path(filename or "template").stem) or "template"
    return f"{stem}.{extension}" if extension else stem


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
    (when one is uploaded) so the screen can show which copy is live, name
    the file a download will hand back, and only offer the download when
    there is something to serve.
    """
    from .models import ProposalTemplateOverride

    overrides = {override.key: override for override in ProposalTemplateOverride.objects.all()}

    rows = []
    for key, (label, extension) in TEMPLATE_FILES.items():
        override = overrides.get(key)
        bundled = bundled_path(key)
        bundled_exists = bundled.exists()

        if override is not None and override.file:
            live_filename = Path(override.file.name).name
            size = override.file.size
        elif bundled_exists:
            live_filename = bundled.name
            try:
                size = bundled.stat().st_size
            except OSError:
                size = 0
        else:
            live_filename = ""
            size = 0

        rows.append(
            {
                "key": key,
                "label": label,
                "extension": extension,
                "override": override,
                "bundled_exists": bundled_exists,
                "live_filename": live_filename,
                "size": size,
                "downloadable": bool(live_filename),
            }
        )
    return rows
