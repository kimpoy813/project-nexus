"""
No-code builders: document templates, dynamic forms, wizard steps, role capabilities.
"""
from collections import OrderedDict
import logging

from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
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
from ..decorators import admin_required
from ..forms import DocumentTemplateForm
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


def _seed_default_fields():
    from details.models import DynamicFormTemplate, DynamicFormField
    
    default_fields_map = {
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
            {"key": "budgetary_requirement", "label": "Budgetary Requirement", "type": "TEXTAREA", "placeholder": "Describe budget details"},
        ],
        10: [
            {"key": "extension_venue", "label": "Extension Venue / Site", "type": "TEXT", "placeholder": "Enter venue"},
            {"key": "estimated_month", "label": "Estimated Month", "type": "SELECT", "choices": "January|January\nFebruary|February\nMarch|March\nApril|April\nMay|May\nJune|June\nJuly|July\nAugust|August\nSeptember|September\nOctober|October\nNovember|November\nDecember|December", "placeholder": "Choose month"},
            {"key": "estimated_year", "label": "Estimated Year", "type": "NUMBER", "placeholder": "e.g., 2026"},
        ],
        11: [
            {"key": "rationale_background", "label": "Rationale / Background", "type": "TEXTAREA", "placeholder": "Provide rationale background"},
        ],
        12: [
            {"key": "significance", "label": "Significance", "type": "TEXTAREA", "placeholder": "Describe significance"},
        ],
        13: [
            {"key": "general_objective", "label": "General Objective", "type": "TEXTAREA", "placeholder": "Enter general objective"},
        ],
    }

    for step_no, fields in default_fields_map.items():
        form_name = f"Fields for Step {step_no}"
        form_obj, _ = DynamicFormTemplate.objects.get_or_create(
            proposal_wizard_step=step_no,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            defaults={
                "name": form_name,
                "slug": f"step-{step_no}-fields",
                "is_active": True,
                "blocks_proposal_submission": True,
            }
        )
        
        for idx, f in enumerate(fields):
            DynamicFormField.objects.get_or_create(
                form=form_obj,
                field_key=f["key"],
                defaults={
                    "label": f["label"],
                    "field_type": f["type"],
                    "choices_text": f.get("choices", ""),
                    "placeholder": f.get("placeholder", ""),
                    "required": f.get("required", True),
                    "depends_on_key": f.get("depends_on_key", ""),
                    "depends_on_value": f.get("depends_on_value", ""),
                    "order": idx + 1,
                }
            )


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


@login_required
@admin_required
def dynamic_forms_list(request):
    forms_qs = DynamicFormTemplate.objects.prefetch_related("fields").order_by("applies_to", "name")
    return render(
        request,
        "dashboard/admin/dynamic_forms_list.html",
        {
            "forms_qs": forms_qs,
            "applies_to_choices": DynamicFormTemplate.AppliesTo.choices,
        },
    )


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

    max_len = max(
        len(field_ids), len(labels), len(keys), len(types),
        len(placeholders), len(help_texts), len(choices_list),
        len(depends_on_keys), len(depends_on_values), 0,
    )

    def at(values, index, default=""):
        return values[index] if index < len(values) else default

    kept_ids = []
    allowed_types = {choice[0] for choice in DynamicFormField.FieldType.choices}

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
        obj.required = (field_id and field_id in required_indexes) or (not field_id and f"new_{idx}" in required_indexes)
        obj.placeholder = (at(placeholders, idx) or "").strip()
        obj.help_text = (at(help_texts, idx) or "").strip()
        obj.choices_text = (at(choices_list, idx) or "").strip()
        obj.depends_on_key = (at(depends_on_keys, idx) or "").strip()
        obj.depends_on_value = (at(depends_on_values, idx) or "").strip()
        obj.order = idx + 1
        obj.save()
        kept_ids.append(obj.id)

    DynamicFormField.objects.filter(form=form_obj).exclude(id__in=kept_ids).delete()


@login_required
@admin_required
def dynamic_form_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Form name is required.")
        else:
            form_obj = DynamicFormTemplate.objects.create(
                name=name,
                slug=_unique_dynamic_form_slug(name),
                applies_to=(request.POST.get("applies_to") or DynamicFormTemplate.AppliesTo.GENERAL).strip(),
                proposal_wizard_step=_safe_int(request.POST.get("proposal_wizard_step"), 0) or None,
                blocks_proposal_submission=request.POST.get("blocks_proposal_submission") == "on",
                description=(request.POST.get("description") or "").strip(),
                instructions=(request.POST.get("instructions") or "").strip(),
                is_active=request.POST.get("is_active") == "on",
            )
            _save_dynamic_form_fields(form_obj, request.POST)
            messages.success(request, f'Form "{name}" created successfully.')
            return redirect("dynamic_forms_list")

    return render(
        request,
        "dashboard/admin/dynamic_form_builder.html",
        {
            "mode": "create",
            "applies_to_choices": DynamicFormTemplate.AppliesTo.choices,
            "field_type_choices": DynamicFormField.FieldType.choices,
        },
    )


@login_required
@admin_required
def dynamic_form_edit(request, pk):
    form_obj = get_object_or_404(DynamicFormTemplate.objects.prefetch_related("fields"), pk=pk)

    if request.method == "POST":
        name = (request.POST.get("name") or form_obj.name).strip()
        form_obj.name = name
        form_obj.slug = _unique_dynamic_form_slug(name, existing=form_obj)
        form_obj.applies_to = (request.POST.get("applies_to") or form_obj.applies_to).strip()
        form_obj.proposal_wizard_step = _safe_int(request.POST.get("proposal_wizard_step"), 0) or None
        form_obj.blocks_proposal_submission = request.POST.get("blocks_proposal_submission") == "on"
        form_obj.description = (request.POST.get("description") or "").strip()
        form_obj.instructions = (request.POST.get("instructions") or "").strip()
        form_obj.is_active = request.POST.get("is_active") == "on"
        form_obj.save()
        _save_dynamic_form_fields(form_obj, request.POST)
        messages.success(request, f'Form "{form_obj.name}" updated successfully.')
        return redirect("dynamic_forms_list")

    return render(
        request,
        "dashboard/admin/dynamic_form_builder.html",
        {
            "mode": "edit",
            "form_obj": form_obj,
            "applies_to_choices": DynamicFormTemplate.AppliesTo.choices,
            "field_type_choices": DynamicFormField.FieldType.choices,
        },
    )


@login_required
@admin_required
@require_POST
def dynamic_form_delete(request, pk):
    form_obj = get_object_or_404(DynamicFormTemplate, pk=pk)
    name = form_obj.name
    form_obj.delete()
    messages.success(request, f'Form "{name}" deleted successfully.')
    return redirect("dynamic_forms_list")


@login_required
@admin_required
def wizard_steps_manager(request):
    _sync_default_wizard_step_configs()
    steps = ProposalWizardStepConfig.objects.all().order_by("step_no")
    return render(request, "dashboard/admin/wizard_steps_manager.html", {"steps": steps})


@login_required
@admin_required
def wizard_step_edit(request, step_no):
    _sync_default_wizard_step_configs()
    step_config = get_object_or_404(ProposalWizardStepConfig, step_no=step_no)

    form_obj = DynamicFormTemplate.objects.filter(
        proposal_wizard_step=step_no,
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
    ).first()
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

    if request.method == "POST":
        step_config.title = (request.POST.get("title") or step_config.title).strip()
        step_config.description = (request.POST.get("description") or "").strip()
        step_config.instructions = (request.POST.get("instructions") or "").strip()
        step_config.is_visible = request.POST.get("is_visible") == "on"
        step_config.is_required = request.POST.get("is_required") == "on"
        step_config.save()

        # Update the dynamic form template name just in case the title changed
        form_obj.name = f"Fields for Step {step_no}: {step_config.title}"
        form_obj.save(update_fields=["name"])

        _save_dynamic_form_fields(form_obj, request.POST)

        messages.success(request, f"Wizard Step {step_config.step_no} and its fields updated.")
        return redirect("wizard_steps_manager")

    return render(
        request,
        "dashboard/admin/wizard_step_form.html",
        {
            "step_config": step_config,
            "form_obj": form_obj,
            "field_type_choices": DynamicFormField.FieldType.choices,
        },
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
            _save_dynamic_form_fields(form_obj, request.POST)

            messages.success(request, f"Wizard Step {step_no} and its fields created successfully.")
            return redirect("wizard_steps_manager")

    return render(
        request,
        "dashboard/admin/wizard_step_create_form.html",
        {
            "next_step_no": next_step_no,
            "field_type_choices": DynamicFormField.FieldType.choices,
        },
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
