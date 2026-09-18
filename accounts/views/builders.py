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
from details.wizard_defaults import PROPONENTS_SECTION_KEY
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
    """Seed each step's built-in section fields (no-op on forms with fields).

    Kept under its historical name; the logic lives in
    ``proposals.views.wizard_config`` next to the section registry.
    """
    from proposals.views.wizard_config import ensure_wizard_steps, seed_section_fields

    for config in ensure_wizard_steps():
        seed_section_fields(config)


def _sync_default_wizard_step_configs():
    """Create the built-in wizard on an empty table (admin owns it after)."""
    from proposals.views.wizard_config import ensure_wizard_steps

    ensure_wizard_steps()


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
def wizard_steps_manager(request):
    from proposals.views.sections import SECTIONS

    _sync_default_wizard_step_configs()
    steps = list(ProposalWizardStepConfig.objects.all().order_by("step_no"))

    field_counts = {}
    for form in DynamicFormTemplate.objects.filter(
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step__isnull=False,
    ).prefetch_related("fields"):
        field_counts[form.proposal_wizard_step] = field_counts.get(form.proposal_wizard_step, 0) + form.fields.count()

    used_sections = {s.section_key for s in steps if s.section_key}
    for step in steps:
        section = SECTIONS.get(step.section_key)
        step.section_label = section.label if section else ""
        step.field_count = field_counts.get(step.step_no, 0)

    unused_sections = [s for key, s in SECTIONS.items() if key not in used_sections]

    return render(
        request,
        "dashboard/admin/wizard_steps_manager.html",
        {
            "steps": steps,
            "unused_sections": unused_sections,
            "can_reorder": len(steps) > 1,
        },
    )


@login_required
@admin_required
@require_POST
def wizard_steps_reorder(request):
    """Move a step up or down, or renumber the whole wizard 1..N.

    Steps are keyed by number everywhere - saved progress, reviewer comments,
    attached field forms - so a move swaps numbers with the neighbour and
    updates the attached forms in the same transaction.
    """
    from django.db import transaction

    action = (request.POST.get("action") or "").strip()
    step_no = _safe_int(request.POST.get("step_no"), 0)

    steps = list(ProposalWizardStepConfig.objects.all().order_by("step_no"))
    index = next((i for i, s in enumerate(steps) if s.step_no == step_no), None)

    def _renumber(pairs):
        # pairs: [(config, new_step_no)]. Go through a temporary offset so the
        # unique constraint on step_no is never violated mid-way.
        offset = 100000
        with transaction.atomic():
            for config, new_no in pairs:
                _move_step(config, config.step_no + offset)
            for config, new_no in pairs:
                _move_step(config, new_no)

    if action in ("up", "down") and index is not None:
        swap_with = index - 1 if action == "up" else index + 1
        if 0 <= swap_with < len(steps):
            a, b = steps[index], steps[swap_with]
            _renumber([(a, b.step_no), (b, a.step_no)])
            messages.success(request, f"Moved “{a.title}” {action}.")
        else:
            messages.info(request, "That step is already at the end.")
    elif action == "compact":
        _renumber([(config, i) for i, config in enumerate(steps, start=1)])
        messages.success(request, "Steps renumbered 1 to %d." % len(steps))
    else:
        messages.error(request, "Nothing to reorder.")
    return redirect("wizard_steps_manager")


def _move_step(config, new_step_no):
    """Renumber a step together with the field forms attached to it."""
    old = config.step_no
    if old == new_step_no:
        return
    DynamicFormTemplate.objects.filter(
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step=old,
    ).update(proposal_wizard_step=new_step_no)
    config.step_no = new_step_no
    config.save(update_fields=["step_no"])


def _builder_context(form_obj=None, **extra):
    """Template context shared by the wizard step editor and the form builder.

    Both screens render the same field rows and the same "repeatable group"
    panel, so the choices they need are assembled in one place.
    """
    from proposals.views.sections import section_choices

    ctx = {
        "form_obj": form_obj,
        "field_type_choices": DynamicFormField.FieldType.choices,
        "repeater_store_choices": DynamicFormTemplate.RowStore.choices,
        "proponent_map_choices": DynamicFormField.MapsTo.choices,
        "section_choices": section_choices(),
        "proponents_section_key": PROPONENTS_SECTION_KEY,
    }
    ctx.update(extra)
    return ctx


def _section_taken_elsewhere(section_key, *, exclude_step_no=None):
    """Another step already carries ``section_key`` (each section is unique)."""
    if not section_key:
        return None
    qs = ProposalWizardStepConfig.objects.filter(section_key=section_key)
    if exclude_step_no is not None:
        qs = qs.exclude(step_no=exclude_step_no)
    return qs.first()


def _apply_section_change(step_config, new_key):
    """Validate and apply a section change. Returns an error message or None."""
    from proposals.views.sections import get_section
    from proposals.views.wizard_config import assign_section

    new_key = (new_key or "").strip()
    if new_key and get_section(new_key) is None:
        return "Unknown section."
    other = _section_taken_elsewhere(new_key, exclude_step_no=step_config.step_no)
    if other is not None:
        return f"“{get_section(new_key).label}” is already used by Step {other.step_no} ({other.title})."
    assign_section(step_config, new_key)
    return None


@login_required
@admin_required
def wizard_step_edit(request, step_no):
    from proposals.views.sections import get_section
    from proposals.views.wizard_config import seed_section_fields, step_form, step_form_name

    _sync_default_wizard_step_configs()
    step_config = get_object_or_404(ProposalWizardStepConfig, step_no=step_no)

    if request.method == "POST":
        error = _apply_section_change(step_config, request.POST.get("section_key"))
        if error:
            messages.error(request, error)
            return redirect("wizard_step_edit", step_no=step_no)

        step_config.title = (request.POST.get("title") or step_config.title).strip()
        step_config.description = (request.POST.get("description") or "").strip()
        step_config.instructions = (request.POST.get("instructions") or "").strip()
        step_config.is_visible = request.POST.get("is_visible") == "on"
        step_config.is_required = request.POST.get("is_required") == "on"
        step_config.save()

        form_obj = step_form(step_config)
        form_obj.name = step_form_name(step_config)
        form_obj.save(update_fields=["name"])

        _save_repeater_settings(form_obj, request.POST)
        _save_dynamic_form_fields(form_obj, request.POST)

        messages.success(request, f"Wizard Step {step_config.step_no} and its fields updated.")
        return redirect("wizard_steps_manager")

    # Show the section's default editable fields instead of an empty builder.
    # Seeding only fills a form with no fields, so an admin's own layout is
    # never overwritten.
    form_obj = step_form(step_config)
    seed_section_fields(step_config, form_obj)

    return render(
        request,
        "dashboard/admin/wizard_step_form.html",
        _builder_context(
            form_obj,
            step_config=step_config,
            section=get_section(step_config.section_key),
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

        from proposals.views.sections import get_section
        from proposals.views.wizard_config import seed_section_fields, step_form

        section_key = (request.POST.get("section_key") or "").strip()
        taken = _section_taken_elsewhere(section_key)

        if step_no <= 0:
            messages.error(request, "Step number must be a positive integer.")
        elif ProposalWizardStepConfig.objects.filter(step_no=step_no).exists():
            messages.error(request, f"Step number {step_no} already exists.")
        elif not title:
            messages.error(request, "Title is required.")
        elif section_key and get_section(section_key) is None:
            messages.error(request, "Unknown section.")
        elif taken is not None:
            messages.error(
                request,
                f"“{get_section(section_key).label}” is already used by Step {taken.step_no} ({taken.title}).",
            )
        else:
            step_config = ProposalWizardStepConfig.objects.create(
                step_no=step_no,
                section_key=section_key,
                title=title,
                description=description,
                instructions=instructions,
                is_visible=is_visible,
                is_required=is_required,
            )

            form_obj = step_form(step_config)
            _save_repeater_settings(form_obj, request.POST)
            _save_dynamic_form_fields(form_obj, request.POST)
            # A section's built-in fields, unless the admin already typed some.
            seed_section_fields(step_config, form_obj)

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
