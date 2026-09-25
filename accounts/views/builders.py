"""
No-code builders: document templates, proposal templates, wizard steps, role capabilities.
"""
from collections import OrderedDict
import json
import logging
from urllib.parse import quote

from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction
from django.http import FileResponse
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from details.models import DocumentTemplate
from details.models import DynamicFormField
from details.models import DynamicFormTemplate
from details.models import ProposalWizardStepConfig
from details.models import RoleCapability
from details.proponent_fields import PROPONENT_STEP_NO, ensure_proponent_repeater_form
from ..decorators import admin_required
from ..forms import CustomProposalTemplateForm
from ..forms import CustomProposalTemplateUploadForm
from ..forms import DocumentTemplateForm
from ..forms import ProposalTemplateEditForm
from ..forms import ProposalTemplateReplacementForm
from ..storage_diagnostics import describe_storage_exception
from ..storage_diagnostics import storage_failure_hint
from .helpers import _safe_int
from .reports import ACCOMPLISHMENT_REPORT_ROLES


logger = logging.getLogger(__name__)

# django-storages delegates remote failures to botocore.  The remaining error
# types cover an invalid storage setting and a local filesystem problem.
_DOCUMENT_TEMPLATE_STORAGE_ERRORS = (
    BotoCoreError,
    ClientError,
    OSError,
    SuspiciousFileOperation,
    ValueError,
)


def _template_storage_is_unavailable():
    """Return the deployment configuration problem, if there is one."""
    return getattr(settings, "MEDIA_STORAGE_CONFIGURATION_ERROR", "")


def _save_document_template(form, *, action, user):
    """Save a validated template without letting a storage outage become a 500.

    Returns ``(template, exception)``.  The exception (when there is one) is
    handed to the view so the administrator sees the provider's own error code
    instead of only "check the Supabase bucket, endpoint, and S3 access keys".
    """
    try:
        return form.save(), None
    except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
        logger.exception(
            "Could not %s document template for user_id=%s; check the configured file storage.",
            action,
            user.pk,
        )
        return None, exc


def _storage_failure_message(headline, exc):
    """Append the provider's reason and a fix hint to a user-facing message."""
    reason = describe_storage_exception(exc)
    if not reason:
        return headline
    return f"{headline} Storage error: {reason}. {storage_failure_hint(exc)}"


# Default "Fields for Step N" rows. Each key mirrors a hardcoded wizard input
# (see proposals.views.dynamic_fields.NATIVE_STEP_FIELDS): editing one of
# these rows relabels the built-in input, it does NOT add a second question.
DEFAULT_STEP_FIELDS = {
        1: [
            {"key": "extension_type", "label": "Extension Type", "type": "SELECT", "choices": "RESEARCH_FACULTY|Research-based (Faculty)\nRESEARCH_STUDENT|Research-based (Student)\nREQUEST_BASED|Request-based\nCOMMUNITY_BASED|Community-based", "placeholder": "Choose extension type"},
            {"key": "scope_type", "label": "Scope", "type": "SELECT", "choices": "PROGRAM|Program\nPROJECT|Project\nACTIVITY|Activity", "placeholder": "Choose scope"},
            {"key": "research_title", "label": "Research Title", "type": "TEXT", "placeholder": "Enter research title if applicable", "required": False, "depends_on_key": "extension_type", "depends_on_value": "RESEARCH_FACULTY,RESEARCH_STUDENT"},
        ],
        2: [
            {"key": "title", "label": "Title of the Program / Project / Activity", "type": "TEXT", "placeholder": "Enter official title"},
        ],
        4: [
            {"key": "implementing_agency", "label": "Implementing Agency / Unit", "type": "TEXT", "placeholder": "Enter implementing agency"},
        ],
        5: [
            {"key": "beneficiaries_count", "label": "Beneficiary Count", "type": "NUMBER", "placeholder": "Estimated count of beneficiaries"},
            {"key": "beneficiaries_who", "label": "Target Group / Beneficiaries Description", "type": "TEXT", "placeholder": "Describe who they are"},
        ],
        7: [
            {"key": "technology_title", "label": "Title of Technology", "type": "TEXT", "placeholder": "Enter the title of the technology, or N/A"},
            {"key": "utility_model_registration_number", "label": "Utility Model Registration Number", "type": "TEXT", "placeholder": "Enter the registration number, or N/A"},
            {"key": "utility_model_description", "label": "Utility Model Description", "type": "TEXTAREA", "placeholder": "Describe the utility model, or N/A"},
        ],
        8: [
            {"key": "budgetary_requirement", "label": "Budgetary Requirement", "type": "TEXTAREA", "placeholder": "Describe budget details"},
        ],
        11: [
            {"key": "extension_venue", "label": "Extension Venue / Site", "type": "TEXT", "placeholder": "Enter venue"},
            {"key": "estimated_month", "label": "Estimated Month", "type": "SELECT", "choices": "January|January\nFebruary|February\nMarch|March\nApril|April\nMay|May\nJune|June\nJuly|July\nAugust|August\nSeptember|September\nOctober|October\nNovember|November\nDecember|December", "placeholder": "Choose month"},
            {"key": "estimated_year", "label": "Estimated Year", "type": "NUMBER", "placeholder": "e.g., 2026"},
        ],
        12: [
            {"key": "rationale_background", "label": "Rationale / Background", "type": "TEXTAREA", "placeholder": "Provide rationale background"},
        ],
        13: [
            {"key": "significance", "label": "Significance", "type": "TEXTAREA", "placeholder": "Describe significance"},
        ],
        14: [
            {"key": "general_objective", "label": "General Objective", "type": "TEXTAREA", "placeholder": "Enter general objective"},
        ],
        17: [
            {
                "key": "work_plan_file",
                "label": "Work Plan File",
                "type": "FILE",
                "help_text": "Upload the completed editable Excel work plan workbook.",
            },
            {
                "key": "gantt_chart_file",
                "label": "Gantt Chart File",
                "type": "FILE",
                "help_text": "Upload the completed editable Excel Gantt chart workbook.",
            },
        ],
        18: [
            {
                "key": "funding_file",
                "label": "Funding Strategy",
                "type": "FILE",
                "help_text": "Upload the completed editable Excel funding workbook.",
            },
        ],
}


def _seed_step_fields(form_obj, step_no):
    """Seed built-in mirror rows without overwriting office-built fields.

    For steps 17 and 18 the native file upload mirrors are also appended to an
    existing form, if missing, so admins can relabel built-in uploads even on
    installations where the step form was customized before these mirrors were
    introduced.
    """
    existing_fields = form_obj.fields.exists()
    if existing_fields and step_no not in {17, 18}:
        return

    next_order = (form_obj.fields.order_by("-order").values_list("order", flat=True).first() or 0)
    for f in DEFAULT_STEP_FIELDS.get(step_no, []):
        _field, created = DynamicFormField.objects.get_or_create(
            form=form_obj,
            field_key=f["key"],
            defaults={
                "label": f["label"],
                "field_type": f["type"],
                "choices_text": f.get("choices", ""),
                "placeholder": f.get("placeholder", ""),
                "help_text": f.get("help_text", ""),
                "required": f.get("required", True),
                "depends_on_key": f.get("depends_on_key", ""),
                "depends_on_value": f.get("depends_on_value", ""),
                "order": next_order + 1,
            },
        )
        if created:
            next_order += 1


def _seed_default_fields():
    for step_no in DEFAULT_STEP_FIELDS:
        form_name = f"Fields for Step {step_no}"
        form_obj, created = DynamicFormTemplate.objects.get_or_create(
            proposal_wizard_step=step_no,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            defaults={
                "name": form_name,
                "slug": f"step-{step_no}-fields",
                "is_active": True,
                "blocks_proposal_submission": True,
            }
        )
        _seed_step_fields(form_obj, step_no)


def _sync_default_wizard_step_configs():
    if ProposalWizardStepConfig.objects.exists():
        return

    from proposals.views.constants import INITIAL_STEP_LABELS
    to_create = []
    for item in INITIAL_STEP_LABELS:
        to_create.append(
            ProposalWizardStepConfig(
                step_no=item["no"],
                title=item["title"],
                description=item["desc"],
                is_visible=True,
                is_required=True,
                display_order=item["no"],
            )
        )
    if to_create:
        ProposalWizardStepConfig.objects.bulk_create(to_create)

    _seed_default_fields()


def _sync_default_role_capabilities():
    default_enabled = {
        (RoleCapability.Role.FACULTY, RoleCapability.Capability.CREATE_PROPOSAL),
        (RoleCapability.Role.EVALUATOR, RoleCapability.Capability.CREATE_PROPOSAL),
        (RoleCapability.Role.EVALUATOR, RoleCapability.Capability.REVIEW_PROPOSAL),
        (RoleCapability.Role.DEPARTMENT_COORDINATOR, RoleCapability.Capability.CREATE_PROPOSAL),
        (RoleCapability.Role.DEPARTMENT_COORDINATOR, RoleCapability.Capability.REVIEW_PROPOSAL),
        (RoleCapability.Role.DEPARTMENT_COORDINATOR, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT),
        (RoleCapability.Role.CAMPUS_COORDINATOR, RoleCapability.Capability.CREATE_PROPOSAL),
        (RoleCapability.Role.CAMPUS_COORDINATOR, RoleCapability.Capability.REVIEW_PROPOSAL),
        (RoleCapability.Role.CAMPUS_COORDINATOR, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT),
        (RoleCapability.Role.STAFF, RoleCapability.Capability.MANAGE_MOA),
        (RoleCapability.Role.STAFF, RoleCapability.Capability.MANAGE_IMPLEMENTATION),
        (RoleCapability.Role.DIRECTOR, RoleCapability.Capability.CREATE_PROPOSAL),
        (RoleCapability.Role.DIRECTOR, RoleCapability.Capability.REVIEW_PROPOSAL),
        (RoleCapability.Role.DIRECTOR, RoleCapability.Capability.MANAGE_MOA),
        (RoleCapability.Role.DIRECTOR, RoleCapability.Capability.MANAGE_IMPLEMENTATION),
        (RoleCapability.Role.DIRECTOR, RoleCapability.Capability.VIEW_ANALYTICS),
    }
    for role, _label in RoleCapability.Role.choices:
        for capability, _cap_label in RoleCapability.Capability.choices:
            RoleCapability.objects.get_or_create(
                role=role,
                capability=capability,
                defaults={"enabled": (role, capability) in default_enabled},
            )


@login_required
@admin_required
def document_templates_list(request):
    templates_qs = DocumentTemplate.objects.all().order_by("category", "title")
    return render(
        request,
        "dashboard/admin/document_templates_list.html",
        {
            "templates_qs": templates_qs,
            "category_choices": DocumentTemplate.Category.choices,
        },
    )


def _document_template_form_context(*, mode, form, template_obj=None):
    return {
        "mode": mode,
        "form": form,
        "template_obj": template_obj,
        "storage_configuration_error": _template_storage_is_unavailable(),
        # Non-fatal advice (for example a missing SUPABASE_STORAGE_PUBLIC_URL),
        # shown in the form so it can be fixed before files go live.
        "storage_configuration_warnings": getattr(
            settings, "SUPABASE_STORAGE_CONFIGURATION_WARNINGS", ()
        ),
    }


@login_required
@admin_required
def document_template_create(request):
    form = DocumentTemplateForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        storage_error = _template_storage_is_unavailable()
        if storage_error:
            logger.error("Document template upload blocked: %s", storage_error)
            messages.error(request, "The template was not uploaded. File storage needs to be configured first.")
        else:
            template, storage_exc = _save_document_template(form, action="create", user=request.user)
            if template:
                messages.success(request, f'Template "{template.title}" uploaded successfully.')
                return redirect("document_templates_list")
            messages.error(
                request,
                _storage_failure_message(
                    "The template could not be uploaded to file storage. Check the Supabase "
                    "bucket, endpoint, and S3 access keys, then try again.",
                    storage_exc,
                ),
            )
    elif request.method == "POST":
        messages.error(request, "Please correct the errors below and try again.")

    return render(
        request,
        "dashboard/admin/document_template_form.html",
        _document_template_form_context(mode="create", form=form),
    )


@login_required
@admin_required
def document_template_edit(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk)
    form = DocumentTemplateForm(request.POST or None, request.FILES or None, instance=template)

    if request.method == "POST" and form.is_valid():
        # Editing text/status does not require the file backend; only block a
        # replacement upload while the remote storage configuration is invalid.
        if request.FILES.get("file") and _template_storage_is_unavailable():
            storage_error = _template_storage_is_unavailable()
            logger.error("Document template replacement blocked: %s", storage_error)
            messages.error(request, "The replacement file was not uploaded. File storage needs to be configured first.")
            # ModelForm validation assigned the selected file to this instance.
            # Restore it so the "Current file" link remains the stored file.
            template.refresh_from_db()
        else:
            saved_template, storage_exc = _save_document_template(form, action="update", user=request.user)
            if saved_template:
                messages.success(request, f'Template "{saved_template.title}" updated successfully.')
                return redirect("document_templates_list")
            messages.error(
                request,
                _storage_failure_message(
                    "The template could not be saved to file storage. Check the Supabase bucket, "
                    "endpoint, and S3 access keys, then try again.",
                    storage_exc,
                ),
            )
            # As above, do not render a link to an upload that did not save.
            template.refresh_from_db()
    elif request.method == "POST":
        messages.error(request, "Please correct the errors below and try again.")

    return render(
        request,
        "dashboard/admin/document_template_form.html",
        _document_template_form_context(mode="edit", form=form, template_obj=template),
    )


@login_required
@admin_required
@require_POST
def document_template_delete(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk)
    title = template.title
    template.delete()
    messages.success(request, f'Template "{title}" deleted successfully.')
    return redirect("document_templates_list")


# ---------------------------------------------------------------------------
# Proposal document templates (the files in proposals/template_files)
# ---------------------------------------------------------------------------


def _proposal_template_slot_rows():
    """Slot descriptors plus their current override, for the admin screen."""
    from proposals.template_store import template_slot_summaries

    return template_slot_summaries()


def _proposal_template_label(key):
    from proposals.template_store import TEMPLATE_FILES

    return TEMPLATE_FILES.get(key, (key, ""))[0]


def _proposal_template_storage_context(**extra):
    """Storage state shared by every screen on this page.

    The office uploads straight to remote object storage, so the screens say
    out loud when that storage is not configured instead of failing on save.
    """
    context = {
        "storage_configuration_error": _template_storage_is_unavailable(),
        "storage_configuration_warnings": getattr(
            settings, "SUPABASE_STORAGE_CONFIGURATION_WARNINGS", ()
        ),
    }
    context.update(extra)
    return context


def _unique_custom_template_key(candidate):
    """A key that is free, derived from ``candidate``.

    Two files titled "MOA Renewal Form" cannot share one identity, so the
    second one is filed as ``moa-renewal-form-2.docx``.
    """
    from proposals.models import CustomProposalTemplate

    stem, dot, extension = candidate.rpartition(".")
    stem = stem or candidate
    if not dot:
        extension = ""

    key = f"{stem}.{extension}" if extension else stem
    index = 2
    while CustomProposalTemplate.objects.filter(key=key).exists():
        suffix = f".{extension}" if extension else ""
        key = f"{stem}-{index}{suffix}"
        index += 1
    return key


def _custom_template_title(filename):
    """A readable default title taken from an uploaded filename."""
    from pathlib import Path as _Path

    stem = _Path(filename or "").stem
    return stem.replace("_", " ").replace("-", " ").strip() or "Untitled template"


def _file_download_response_from_stream(stream, filename):
    """Serve an open stream as a named download with the right content type."""
    from proposals.template_store import content_type_for

    response = FileResponse(stream, content_type=content_type_for(filename))
    response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
    return response


@login_required
@admin_required
def proposal_templates_list(request):
    """Manage the templates the system generates proposal documents from."""
    from proposals.models import CustomProposalTemplate
    from proposals.models import ProposalTemplateOverride
    from proposals.template_store import CUSTOM_TEMPLATE_EXTENSIONS, TEMPLATE_FILES

    return render(
        request,
        "dashboard/admin/proposal_templates_list.html",
        _proposal_template_storage_context(
            rows=_proposal_template_slot_rows(),
            custom_templates=CustomProposalTemplate.objects.all().order_by("title"),
            replacement_form=ProposalTemplateReplacementForm(),
            add_form=CustomProposalTemplateUploadForm(),
            slot_count=len(TEMPLATE_FILES),
            override_count=ProposalTemplateOverride.objects.count(),
            custom_template_count=CustomProposalTemplate.objects.count(),
            accepted_extensions=CUSTOM_TEMPLATE_EXTENSIONS,
        ),
    )


@login_required
@admin_required
@require_POST
def proposal_template_replace(request):
    """Upload a replacement file for one template slot."""
    from proposals.models import ProposalTemplateOverride

    form = ProposalTemplateReplacementForm(request.POST, request.FILES)
    if not form.is_valid():
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
        return redirect("proposal_templates_list")

    key = form.cleaned_data["key"]
    label = _proposal_template_label(key)

    storage_error = _template_storage_is_unavailable()
    if storage_error:
        logger.error("Proposal template replacement blocked: %s", storage_error)
        messages.error(
            request,
            "The template was not replaced. File storage needs to be configured first.",
        )
        return redirect("proposal_templates_list")

    try:
        override, created = ProposalTemplateOverride.objects.update_or_create(
            key=key,
            defaults={
                "file": form.cleaned_data["file"],
                "notes": form.cleaned_data["notes"],
                "uploaded_by": request.user,
            },
        )
    except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
        logger.exception(
            "Could not store proposal template replacement for %s (user_id=%s).",
            key,
            request.user.pk,
        )
        messages.error(
            request,
            _storage_failure_message(
                f'The replacement for "{label}" could not be saved to file storage. '
                "Check the Supabase bucket, endpoint, and S3 access keys, then try again.",
                exc,
            ),
        )
        return redirect("proposal_templates_list")

    verb = "replaced" if not created else "uploaded"
    messages.success(request, f'Template "{label}" {verb} successfully.')
    return redirect("proposal_templates_list")


@login_required
@admin_required
@require_POST
def proposal_template_reset(request):
    """Drop the admin override so the bundled template is used again."""
    from proposals.models import ProposalTemplateOverride
    from proposals.template_store import TEMPLATE_FILES

    key = (request.POST.get("key") or "").strip()
    if key not in TEMPLATE_FILES:
        messages.error(request, "Unknown template slot.")
        return redirect("proposal_templates_list")

    override = ProposalTemplateOverride.objects.filter(key=key).first()
    if override:
        label = _proposal_template_label(key)
        override.delete()
        messages.success(
            request,
            f'Template "{label}" was reset to the default file shipped with the system.',
        )
    else:
        messages.info(request, "This template is already using the default file.")

    return redirect("proposal_templates_list")


@login_required
@admin_required
def proposal_template_download(request, key):
    """Hand back the live copy of a built-in template.

    The office edits these files in Word/Excel before re-uploading them, so
    the default that ships with the code has to be downloadable too — not
    only a replacement an administrator has already uploaded.
    """
    from proposals.template_store import TEMPLATE_FILES
    from proposals.template_store import TemplateNotFound
    from proposals.template_store import open_template

    if key not in TEMPLATE_FILES:
        raise Http404("Unknown template slot.")

    label = _proposal_template_label(key)
    try:
        stream, filename, _is_override = open_template(key)
    except TemplateNotFound:
        messages.error(request, f'There is no file stored for "{label}" yet.')
        return redirect("proposal_templates_list")

    return _file_download_response_from_stream(stream, filename)


@login_required
@admin_required
def proposal_template_edit(request, key):
    """Edit one built-in slot: swap its file and/or correct its note."""
    from proposals.models import ProposalTemplateOverride
    from proposals.template_store import TEMPLATE_FILES

    if key not in TEMPLATE_FILES:
        raise Http404("Unknown template slot.")

    label = _proposal_template_label(key)
    override = ProposalTemplateOverride.objects.filter(key=key).first()
    form = ProposalTemplateEditForm(
        request.POST or None,
        request.FILES or None,
        slot_key=key,
        has_override=override is not None,
        initial={"notes": override.notes if override else ""},
    )

    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data.get("file")
        notes = form.cleaned_data["notes"]

        storage_error = _template_storage_is_unavailable()
        if upload and storage_error:
            logger.error("Proposal template edit blocked: %s", storage_error)
            messages.error(
                request,
                "The file was not saved. File storage needs to be configured first.",
            )
        else:
            try:
                if override is None:
                    override = ProposalTemplateOverride.objects.create(
                        key=key,
                        file=upload,
                        notes=notes,
                        uploaded_by=request.user,
                    )
                else:
                    override.notes = notes
                    override.uploaded_by = request.user
                    if upload:
                        override.file = upload
                    override.save()
            except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
                logger.exception(
                    "Could not save proposal template %s (user_id=%s).", key, request.user.pk
                )
                messages.error(
                    request,
                    _storage_failure_message(
                        f'The changes to "{label}" could not be saved to file storage. '
                        "Check the Supabase bucket, endpoint, and S3 access keys, then try again.",
                        exc,
                    ),
                )
            else:
                messages.success(request, f'Template "{label}" updated successfully.')
                return redirect("proposal_templates_list")

    elif request.method == "POST":
        messages.error(request, "Please correct the errors below and try again.")

    return render(
        request,
        "dashboard/admin/proposal_template_form.html",
        _proposal_template_storage_context(
            form=form,
            slot_key=key,
            label=label,
            expected_extension=TEMPLATE_FILES[key][1],
            override=override,
            row=next(
                (row for row in _proposal_template_slot_rows() if row["key"] == key), None
            ),
        ),
    )


@login_required
@admin_required
@require_POST
def proposal_custom_template_add(request):
    """Store new template files the office will use as the process changes."""
    from proposals.models import CustomProposalTemplate
    from proposals.template_store import custom_key_for

    form = CustomProposalTemplateUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
        return redirect("proposal_templates_list")

    storage_error = _template_storage_is_unavailable()
    if storage_error:
        logger.error("Custom proposal template upload blocked: %s", storage_error)
        messages.error(
            request,
            "Nothing was added. File storage needs to be configured first.",
        )
        return redirect("proposal_templates_list")

    notes = form.cleaned_data["notes"]
    saved = 0
    failed = 0
    for upload in form.cleaned_data["files"]:
        title = _custom_template_title(upload.name)
        key = _unique_custom_template_key(custom_key_for(title, upload.name))
        try:
            CustomProposalTemplate.objects.create(
                title=title,
                key=key,
                file=upload,
                notes=notes,
                uploaded_by=request.user,
            )
        except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
            logger.exception(
                "Could not store custom proposal template %s (user_id=%s).",
                key,
                request.user.pk,
            )
            failed += 1
            messages.error(
                request,
                _storage_failure_message(
                    f'"{upload.name}" could not be saved to file storage. '
                    "Check the Supabase bucket, endpoint, and S3 access keys, then try again.",
                    exc,
                ),
            )
        else:
            saved += 1

    if saved == 1:
        messages.success(request, "Template file added successfully.")
    elif saved > 1:
        messages.success(request, f"{saved} template files added successfully.")
    if failed and saved:
        messages.warning(request, f"{failed} file(s) could not be added.")

    return redirect("proposal_templates_list")


@login_required
@admin_required
def proposal_custom_template_edit(request, pk):
    """Rename, re-note, replace, or retire an added template file."""
    from proposals.models import CustomProposalTemplate

    template = get_object_or_404(CustomProposalTemplate, pk=pk)
    form = CustomProposalTemplateForm(request.POST or None, request.FILES or None, instance=template)

    if request.method == "POST" and form.is_valid():
        if request.FILES.get("file") and _template_storage_is_unavailable():
            storage_error = _template_storage_is_unavailable()
            logger.error("Custom proposal template replacement blocked: %s", storage_error)
            messages.error(
                request,
                "The replacement file was not uploaded. File storage needs to be configured first.",
            )
            template.refresh_from_db()
        else:
            try:
                saved_template = form.save()
            except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
                logger.exception(
                    "Could not save custom proposal template pk=%s (user_id=%s).",
                    template.pk,
                    request.user.pk,
                )
                messages.error(
                    request,
                    _storage_failure_message(
                        "The template could not be saved to file storage. Check the Supabase "
                        "bucket, endpoint, and S3 access keys, then try again.",
                        exc,
                    ),
                )
                template.refresh_from_db()
            else:
                saved_template.uploaded_by = request.user
                saved_template.save(update_fields=["uploaded_by"])
                messages.success(request, f'Template "{saved_template.title}" updated successfully.')
                return redirect("proposal_templates_list")
    elif request.method == "POST":
        messages.error(request, "Please correct the errors below and try again.")

    return render(
        request,
        "dashboard/admin/proposal_custom_template_form.html",
        _proposal_template_storage_context(form=form, template_obj=template),
    )


@login_required
@admin_required
def proposal_custom_template_download(request, pk):
    """Hand back an added template file."""
    from proposals.models import CustomProposalTemplate

    template = get_object_or_404(CustomProposalTemplate, pk=pk)
    if not template.file:
        raise Http404("This template has no file stored.")

    try:
        # Opened through the storage backend, not a disk path: Supabase's S3
        # storage has no ``.path``, unlike local development.
        return _file_download_response_from_stream(
            template.file.open("rb"), template.filename or template.title
        )
    except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
        logger.exception("Could not read custom proposal template pk=%s.", template.pk)
        messages.error(
            request,
            _storage_failure_message(
                f'"{template.title}" could not be read from file storage.', exc
            ),
        )
        return redirect("proposal_templates_list")


@login_required
@admin_required
@require_POST
def proposal_custom_template_delete(request, pk):
    """Remove an added template file for good."""
    from proposals.models import CustomProposalTemplate

    template = get_object_or_404(CustomProposalTemplate, pk=pk)
    title = template.title
    try:
        template.delete()
    except _DOCUMENT_TEMPLATE_STORAGE_ERRORS as exc:
        logger.exception("Could not delete custom proposal template pk=%s.", template.pk)
        messages.error(
            request,
            _storage_failure_message(f'"{title}" could not be deleted from file storage.', exc),
        )
        return redirect("proposal_templates_list")

    messages.success(request, f'Template "{title}" deleted successfully.')
    return redirect("proposal_templates_list")


def _unique_dynamic_form_slug(name, existing=None):
    base = slugify(name) or "form"
    candidate = base
    i = 2
    qs = DynamicFormTemplate.objects.all()
    if existing:
        qs = qs.exclude(pk=existing.pk)
    while qs.filter(slug=candidate).exists():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


def _save_repeater_settings(form_obj, post_data):
    """Read the "repeatable group" panel of the wizard step editor.

    Kept separate from the field rows because it describes the *group*, not its
    fields. ``maps_to`` only means something for a proponent-storing group, so
    switching the group to free-standing rows clears any stale mapping rather
    than leaving fields pointing at a record that no longer receives them.
    """
    form_obj.is_repeater = post_data.get("is_repeater") == "on"
    form_obj.repeater_label = (post_data.get("repeater_label") or "").strip()[:80]

    minimum = _safe_int(post_data.get("repeater_min_rows"), 0) or 0
    maximum = _safe_int(post_data.get("repeater_max_rows"), 0) or 0
    minimum = max(0, minimum)
    maximum = max(0, maximum)
    if maximum and minimum > maximum:
        # A window that cannot be satisfied is a typo, not a request: keep the
        # cap the admin typed and pull the floor down to it.
        minimum = maximum
    form_obj.repeater_min_rows = minimum
    form_obj.repeater_max_rows = maximum

    allowed_stores = {choice[0] for choice in DynamicFormTemplate.RowStore.choices}
    row_store = (post_data.get("row_store") or "").strip()
    form_obj.row_store = row_store if row_store in allowed_stores else DynamicFormTemplate.RowStore.GENERIC

    if not form_obj.is_repeater or form_obj.row_store != DynamicFormTemplate.RowStore.PROPONENT:
        form_obj.fields.update(maps_to="")

    form_obj.save()


def _save_dynamic_form_fields(form_obj, post_data):
    field_ids = post_data.getlist("field_id[]")
    labels = post_data.getlist("field_label[]")
    keys = post_data.getlist("field_key[]")
    types = post_data.getlist("field_type[]")
    required_indexes = set(post_data.getlist("field_required[]"))
    placeholders = post_data.getlist("field_placeholder[]")
    help_texts = post_data.getlist("field_help_text[]")
    choices_list = post_data.getlist("field_choices[]")
    depends_on_keys = post_data.getlist("field_depends_on_key[]")
    depends_on_values = post_data.getlist("field_depends_on_value[]")
    maps_to_values = post_data.getlist("field_maps_to[]")

    max_len = max(
        len(field_ids), len(labels), len(keys), len(types),
        len(placeholders), len(help_texts), len(choices_list),
        len(depends_on_keys), len(depends_on_values), len(maps_to_values), 0,
    )

    def at(values, index, default=""):
        return values[index] if index < len(values) else default

    kept_ids = []
    allowed_types = {choice[0] for choice in DynamicFormField.FieldType.choices}
    allowed_maps = {choice[0] for choice in DynamicFormField.MapsTo.choices}
    # Only a proponent-storing group has record columns to map onto, and each
    # column can only come from one field (the first field asking for it wins).
    maps_enabled = form_obj.is_repeater and form_obj.row_store == DynamicFormTemplate.RowStore.PROPONENT
    taken_maps = set()

    for idx in range(max_len):
        label = (at(labels, idx) or "").strip()
        if not label:
            continue

        raw_key = (at(keys, idx) or label).strip()
        field_key = slugify(raw_key).replace("-", "_") or f"field_{idx + 1}"
        field_type = (at(types, idx) or DynamicFormField.FieldType.TEXT).strip()
        if field_type not in allowed_types:
            field_type = DynamicFormField.FieldType.TEXT

        field_id = (at(field_ids, idx) or "").strip()
        obj = None
        if field_id:
            obj = DynamicFormField.objects.filter(form=form_obj, id=field_id).first()
        if obj is None:
            obj = DynamicFormField(form=form_obj)

        original_key = field_key
        suffix = 2
        while DynamicFormField.objects.filter(form=form_obj, field_key=field_key).exclude(pk=obj.pk).exists():
            field_key = f"{original_key}_{suffix}"
            suffix += 1

        obj.label = label
        obj.field_key = field_key
        obj.field_type = field_type
        # Saved rows carry their field id; rows built in the browser ("new")
        # have none yet, so their required switch is matched by marker.
        obj.required = bool(field_id and field_id in required_indexes) or (
            not field_id and ("new" in required_indexes or f"new_{idx}" in required_indexes)
        )
        obj.placeholder = (at(placeholders, idx) or "").strip()
        obj.help_text = (at(help_texts, idx) or "").strip()
        obj.choices_text = (at(choices_list, idx) or "").strip()
        obj.depends_on_key = (at(depends_on_keys, idx) or "").strip()
        obj.depends_on_value = (at(depends_on_values, idx) or "").strip()

        maps_to = (at(maps_to_values, idx) or "").strip()
        if not maps_enabled or maps_to not in allowed_maps or maps_to in taken_maps:
            maps_to = ""
        if maps_to:
            taken_maps.add(maps_to)
        obj.maps_to = maps_to

        obj.order = idx + 1
        obj.save()
        kept_ids.append(obj.id)

    DynamicFormField.objects.filter(form=form_obj).exclude(id__in=kept_ids).delete()


@login_required
@admin_required
def wizard_steps_manager(request):
    _sync_default_wizard_step_configs()
    steps = ProposalWizardStepConfig.objects.all().order_by("display_order", "step_no")
    return render(request, "dashboard/admin/wizard_steps_manager.html", {"steps": steps})


@login_required
@admin_required
@require_POST
def wizard_steps_reorder(request):
    """Persist a dragged sequence of proposal wizard steps.

    ``step_no`` is identity; only ``display_order`` changes. The payload is
    the full list of step numbers in the new order.
    """
    _sync_default_wizard_step_configs()
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
        raw_ids = data.get("step_nos", [])
        step_nos = [int(value) for value in raw_ids]
    except (ValueError, TypeError, json.JSONDecodeError):
        logger.warning("Malformed wizard_steps_reorder payload.", exc_info=True)
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    existing = list(
        ProposalWizardStepConfig.objects.order_by("display_order", "step_no").values_list(
            "step_no", flat=True
        )
    )
    if not step_nos or set(step_nos) != set(existing) or len(step_nos) != len(existing):
        return JsonResponse(
            {"ok": False, "error": "Send every wizard step, once, in the new order."},
            status=400,
        )

    try:
        with transaction.atomic():
            for index, step_no in enumerate(step_nos, start=1):
                ProposalWizardStepConfig.objects.filter(step_no=step_no).update(
                    display_order=index
                )
        return JsonResponse({"ok": True})
    except Exception:
        logger.exception("Failed to reorder wizard steps.")
        return JsonResponse({"ok": False, "error": "Server error."}, status=500)


def _builder_context(form_obj=None, **extra):
    """Template context for the wizard step editor screens.

    The create and edit screens render the same field rows and the same
    "repeatable group" panel, so the choices they need are assembled here.
    """
    ctx = {
        "form_obj": form_obj,
        "field_type_choices": DynamicFormField.FieldType.choices,
        "repeater_store_choices": DynamicFormTemplate.RowStore.choices,
        "proponent_map_choices": DynamicFormField.MapsTo.choices,
    }
    ctx.update(extra)
    return ctx


@login_required
@admin_required
def wizard_step_edit(request, step_no):
    _sync_default_wizard_step_configs()
    step_config = get_object_or_404(ProposalWizardStepConfig, step_no=step_no)

    form_obj = (
        DynamicFormTemplate.objects.filter(
            proposal_wizard_step=step_no,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        )
        .order_by("id")
        .first()
    )
    if not form_obj:
        name = f"Fields for Step {step_no}: {step_config.title}"
        slug = _unique_dynamic_form_slug(name)
        form_obj = DynamicFormTemplate.objects.create(
            name=name,
            slug=slug,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step_no,
            is_active=True,
            blocks_proposal_submission=True,
        )

    # Show the built-in inputs of a hardcoded step as editable rows instead of
    # an empty builder, so the admin edits the *existing* fields rather than
    # adding a duplicate set. Seeding only fills a form with no fields, so an
    # admin's own layout is never overwritten.
    _seed_step_fields(form_obj, step_no)

    if step_no == PROPONENT_STEP_NO:
        # Show the office's default proponent fields instead of an empty
        # builder. Seeding only fills a form with no fields, so an admin's own
        # layout is never overwritten.
        seeded = ensure_proponent_repeater_form(step_no)
        if seeded is not None:
            form_obj = seeded

    if request.method == "POST":
        step_config.title = (request.POST.get("title") or step_config.title).strip()
        step_config.description = (request.POST.get("description") or "").strip()
        step_config.instructions = (request.POST.get("instructions") or "").strip()
        step_config.template_download_heading = (
            request.POST.get("template_download_heading", step_config.template_download_heading) or ""
        ).strip()
        step_config.template_download_instructions = (
            request.POST.get(
                "template_download_instructions",
                step_config.template_download_instructions,
            ) or ""
        ).strip()
        step_config.work_plan_download_label = (
            request.POST.get("work_plan_download_label", step_config.work_plan_download_label) or ""
        ).strip()
        step_config.gantt_chart_download_label = (
            request.POST.get(
                "gantt_chart_download_label",
                step_config.gantt_chart_download_label,
            ) or ""
        ).strip()
        step_config.funding_download_label = (
            request.POST.get("funding_download_label", step_config.funding_download_label) or ""
        ).strip()
        step_config.is_visible = request.POST.get("is_visible") == "on"
        step_config.is_required = request.POST.get("is_required") == "on"
        step_config.save()

        # Update the dynamic form template name just in case the title changed
        form_obj.name = f"Fields for Step {step_no}: {step_config.title}"
        form_obj.save(update_fields=["name"])

        _save_repeater_settings(form_obj, request.POST)
        _save_dynamic_form_fields(form_obj, request.POST)

        messages.success(request, f"Wizard Step {step_config.step_no} and its fields updated.")
        return redirect("wizard_steps_manager")

    return render(
        request,
        "dashboard/admin/wizard_step_form.html",
        _builder_context(
            form_obj,
            step_config=step_config,
        ),
    )


@login_required
@admin_required
def wizard_step_create(request):
    _sync_default_wizard_step_configs()

    max_step = ProposalWizardStepConfig.objects.order_by("-step_no").first()
    next_step_no = (max_step.step_no + 1) if max_step else 1

    if request.method == "POST":
        step_no = _safe_int(request.POST.get("step_no"), 0)
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        instructions = (request.POST.get("instructions") or "").strip()
        is_visible = request.POST.get("is_visible") == "on"
        is_required = request.POST.get("is_required") == "on"

        if step_no <= 0:
            messages.error(request, "Step number must be a positive integer.")
        elif ProposalWizardStepConfig.objects.filter(step_no=step_no).exists():
            messages.error(request, f"Step number {step_no} already exists.")
        elif not title:
            messages.error(request, "Title is required.")
        else:
            step_config = ProposalWizardStepConfig.objects.create(
                step_no=step_no,
                title=title,
                description=description,
                instructions=instructions,
                is_visible=is_visible,
                is_required=is_required,
            )

            # Create the dynamic form template for this step
            name = f"Fields for Step {step_no}: {title}"
            slug = _unique_dynamic_form_slug(name)
            form_obj = DynamicFormTemplate.objects.create(
                name=name,
                slug=slug,
                applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
                proposal_wizard_step=step_no,
                is_active=True,
                blocks_proposal_submission=True,
            )
            _save_repeater_settings(form_obj, request.POST)
            _save_dynamic_form_fields(form_obj, request.POST)

            messages.success(request, f"Wizard Step {step_no} and its fields created successfully.")
            return redirect("wizard_steps_manager")

    return render(
        request,
        "dashboard/admin/wizard_step_create_form.html",
        _builder_context(next_step_no=next_step_no),
    )


@login_required
@admin_required
@require_POST
def wizard_step_delete(request, step_no):
    step_config = get_object_or_404(ProposalWizardStepConfig, step_no=step_no)
    title = step_config.title
    step_config.delete()

    # Delete corresponding DynamicFormTemplate
    DynamicFormTemplate.objects.filter(
        proposal_wizard_step=step_no,
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
    ).delete()

    messages.success(request, f"Wizard Step {step_no} ({title}) and its associated fields deleted successfully.")
    return redirect("wizard_steps_manager")


@login_required
@admin_required
def role_capabilities_manager(request):
    _sync_default_role_capabilities()

    if request.method == "POST":
        enabled_ids = set(request.POST.getlist("enabled_capabilities"))
        for item in RoleCapability.objects.all():
            item.enabled = str(item.id) in enabled_ids
            item.notes = (request.POST.get(f"notes_{item.id}") or "").strip()
            item.save(update_fields=["enabled", "notes", "updated_at"])
        messages.success(request, "Role capability matrix updated.")
        return redirect("role_capabilities_manager")

    capabilities = RoleCapability.objects.all().order_by("role", "capability")
    grouped = []
    by_role = OrderedDict()
    for item in capabilities:
        # Accomplishment reports are restricted to Staff/Director in code, so
        # showing a toggle for other roles would be misleading.
        if (
            item.capability == RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT
            and item.role not in ACCOMPLISHMENT_REPORT_ROLES
        ):
            continue
        by_role.setdefault(item.role, []).append(item)
    for role, items in by_role.items():
        grouped.append({
            "role": role,
            "role_label": dict(RoleCapability.Role.choices).get(role, role),
            "items": items,
        })

    return render(
        request,
        "dashboard/admin/role_capabilities_manager.html",
        {"grouped_capabilities": grouped},
    )
