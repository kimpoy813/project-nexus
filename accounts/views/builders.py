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
    """Give each part-backed step a starting form, without touching an edited one."""
    from details.models import DynamicFormTemplate, DynamicFormField
    
    default_fields_map = {
        "extension_type": [
            {"key": "extension_type", "label": "Extension Type", "type": "SELECT", "choices": "RESEARCH_FACULTY|Research-based (Faculty)\nRESEARCH_STUDENT|Research-based (Student)\nREQUEST_BASED|Request-based\nCOMMUNITY_BASED|Community-based", "placeholder": "Choose extension type"},
            {"key": "scope_type", "label": "Scope", "type": "SELECT", "choices": "PROGRAM|Program\nPROJECT|Project\nACTIVITY|Activity", "placeholder": "Choose scope"},
            {"key": "research_title", "label": "Research Title", "type": "TEXT", "placeholder": "Enter research title if applicable", "required": False, "depends_on_key": "extension_type", "depends_on_value": "RESEARCH_FACULTY,RESEARCH_STUDENT"},
        ],
        "title": [
            {"key": "title", "label": "Title of the Program / Project / Activity", "type": "TEXT", "placeholder": "Enter official title"},
        ],
        "implementing_agency": [
            {"key": "implementing_agency", "label": "Implementing Agency / Unit", "type": "TEXT", "placeholder": "Enter implementing agency"},
        ],
        "beneficiaries": [
            {"key": "beneficiaries_count", "label": "Beneficiary Count", "type": "NUMBER", "placeholder": "Estimated count of beneficiaries"},
            {"key": "beneficiaries_who", "label": "Target Group / Beneficiaries Description", "type": "TEXT", "placeholder": "Describe who they are"},
        ],
        "budgetary_requirement": [
            {"key": "budgetary_requirement", "label": "Budgetary Requirement", "type": "TEXTAREA", "placeholder": "Describe budget details"},
        ],
        "schedule_venue": [
            {"key": "extension_venue", "label": "Extension Venue / Site", "type": "TEXT", "placeholder": "Enter venue"},
            {"key": "estimated_month", "label": "Estimated Month", "type": "SELECT", "choices": "January|January\nFebruary|February\nMarch|March\nApril|April\nMay|May\nJune|June\nJuly|July\nAugust|August\nSeptember|September\nOctober|October\nNovember|November\nDecember|December", "placeholder": "Choose month"},
            {"key": "estimated_year", "label": "Estimated Year", "type": "NUMBER", "placeholder": "e.g., 2026"},
        ],
        "rationale_background": [
            {"key": "rationale_background", "label": "Rationale / Background", "type": "TEXTAREA", "placeholder": "Provide rationale background"},
        ],
        "significance": [
            {"key": "significance", "label": "Significance", "type": "TEXTAREA", "placeholder": "Describe significance"},
        ],
        "objectives": [
            {"key": "general_objective", "label": "General Objective", "type": "TEXTAREA", "placeholder": "Enter general objective"},
        ],
    }

    # Keyed by built-in *part*, not by step number: the office decides which
    # step shows a part, and two steps may show the same one.
    from proposals.views.wizard_flows import proposal_flow

    proposal_flow.ensure_defaults()

    for step_config in proposal_flow.ordered():
        fields = default_fields_map.get(step_config.section_key)
        if not fields:
            continue
        step_no = step_config.step_no
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

        # A form the office already built or edited on this step is left alone:
        # the defaults exist to give a fresh step a usable shape, not to add
        # surprise fields to a custom one (including a repeatable group).
        if not created and form_obj.fields.exists():
            continue

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
    """Make sure the wizard has its default steps and default proponent fields.

    The step rows themselves are the flow's business: it seeds what is missing
    without touching what an admin has renamed, hidden, moved, or re-pointed.
    """
    from proposals.views.wizard_flows import moa_flow, proposal_flow

    created = not ProposalWizardStepConfig.objects.exists()
    proposal_flow.ensure_defaults()
    moa_flow.ensure_defaults()

    if created:
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


def _save_repeater_settings(form_obj, post_data):
    """Read the "repeatable group" panel of the form builder.

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


def _builder_context(form_obj=None, **extra):
    """Template context shared by the wizard step editors and the form builder.

    All of these screens render the same field rows and the same "repeatable
    group" panel, so the choices they need are assembled in one place.
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
            _save_repeater_settings(form_obj, request.POST)
            _save_dynamic_form_fields(form_obj, request.POST)
            messages.success(request, f'Form "{name}" created successfully.')
            return redirect("dynamic_forms_list")

    return render(
        request,
        "dashboard/admin/dynamic_form_builder.html",
        _builder_context(
            mode="create",
            applies_to_choices=DynamicFormTemplate.AppliesTo.choices,
        ),
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
        _save_repeater_settings(form_obj, request.POST)
        _save_dynamic_form_fields(form_obj, request.POST)
        messages.success(request, f'Form "{form_obj.name}" updated successfully.')
        return redirect("dynamic_forms_list")

    return render(
        request,
        "dashboard/admin/dynamic_form_builder.html",
        _builder_context(
            form_obj,
            mode="edit",
            applies_to_choices=DynamicFormTemplate.AppliesTo.choices,
        ),
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
