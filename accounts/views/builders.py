"""
No-code builders: document templates, dynamic forms, wizard steps, role capabilities.
"""
from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from .helpers import _safe_int
from .reports import ACCOMPLISHMENT_REPORT_ROLES


def _sync_default_wizard_step_configs():
    # Import here to avoid circular import at module load time.
    from proposals.views import STEP_LABELS

    existing = {item.step_no: item for item in ProposalWizardStepConfig.objects.all()}
    to_create = []
    for item in STEP_LABELS:
        if item["no"] not in existing:
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


@login_required
@admin_required
def document_template_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        category = (request.POST.get("category") or DocumentTemplate.Category.OTHER).strip()
        description = (request.POST.get("description") or "").strip()
        version_label = (request.POST.get("version_label") or "").strip()
        is_active = request.POST.get("is_active") == "on"
        file = request.FILES.get("file")

        if not title or not file:
            messages.error(request, "Title and template file are required.")
        else:
            DocumentTemplate.objects.create(
                title=title,
                category=category,
                description=description,
                version_label=version_label,
                is_active=is_active,
                file=file,
            )
            messages.success(request, f'Template "{title}" uploaded successfully.')
            return redirect("document_templates_list")

    return render(
        request,
        "dashboard/admin/document_template_form.html",
        {
            "mode": "create",
            "category_choices": DocumentTemplate.Category.choices,
        },
    )


@login_required
@admin_required
def document_template_edit(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk)

    if request.method == "POST":
        template.title = (request.POST.get("title") or template.title).strip()
        template.category = (request.POST.get("category") or template.category).strip()
        template.description = (request.POST.get("description") or "").strip()
        template.version_label = (request.POST.get("version_label") or "").strip()
        template.is_active = request.POST.get("is_active") == "on"
        if request.FILES.get("file"):
            template.file = request.FILES["file"]
        template.save()
        messages.success(request, f'Template "{template.title}" updated successfully.')
        return redirect("document_templates_list")

    return render(
        request,
        "dashboard/admin/document_template_form.html",
        {
            "mode": "edit",
            "template_obj": template,
            "category_choices": DocumentTemplate.Category.choices,
        },
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

    max_len = max(
        len(field_ids), len(labels), len(keys), len(types),
        len(placeholders), len(help_texts), len(choices_list), 0,
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

    if request.method == "POST":
        step_config.title = (request.POST.get("title") or step_config.title).strip()
        step_config.description = (request.POST.get("description") or "").strip()
        step_config.instructions = (request.POST.get("instructions") or "").strip()
        step_config.is_visible = request.POST.get("is_visible") == "on"
        step_config.is_required = request.POST.get("is_required") == "on"
        step_config.save()
        messages.success(request, f"Wizard Step {step_config.step_no} updated.")
        return redirect("wizard_steps_manager")

    return render(
        request,
        "dashboard/admin/wizard_step_form.html",
        {"step_config": step_config},
    )


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
