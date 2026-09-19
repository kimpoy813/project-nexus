"""
Admin screens for the two configurable wizards.

These are the screens that make the wizards the office's to shape: rename a
step, rewrite its instructions, hide it, decide whether submission waits for
it, move it up or down the list, point it at a different built-in part, and
attach the office's own form templates to it.

Both wizards share the same five screens (manager, create, edit, move, delete)
because both are :class:`~proposals.views.step_flow.StepFlow` objects over a
step table; only the model, the part registry, and the ``applies_to`` value of
the forms they can hold differ. That difference is carried by ``WizardBuilder``
so the two sets of screens cannot drift apart.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST
from details.models import DynamicFormTemplate
from details.models import MOAWizardStepConfig
from details.models import ProposalWizardStepConfig
from details.proponent_fields import ensure_proponent_repeater_form
from proposals.views.moa_sections import SECTIONS as MOA_SECTIONS
from proposals.views.step_sections import SECTIONS as PROPOSAL_SECTIONS
from proposals.views.wizard_flows import moa_flow
from proposals.views.wizard_flows import proposal_flow

from ..decorators import admin_required
from .builders import _builder_context
from .builders import _save_dynamic_form_fields
from .builders import _save_repeater_settings
from .builders import _unique_dynamic_form_slug
from .helpers import _safe_int


logger = logging.getLogger(__name__)


class WizardBuilder:
    """One wizard's admin screens, parameterised by its model and registry."""

    def __init__(self, *, key, flow, sections, applies_to, url_prefix, template_prefix, label):
        self.key = key
        self.flow = flow
        self.sections = sections
        self.applies_to = applies_to
        self.url_prefix = url_prefix
        self.template_prefix = template_prefix
        self.label = label

    # -- helpers ---------------------------------------------------------

    def manager_url(self):
        return f"{self.url_prefix}_steps_manager"

    def edit_url(self):
        return f"{self.url_prefix}_step_edit"

    def create_url(self):
        return f"{self.url_prefix}_step_create"

    def delete_url(self):
        return f"{self.url_prefix}_step_delete"

    def move_url(self):
        return f"{self.url_prefix}_step_move"

    def section_choices(self):
        return [("", "Office-built forms only (no built-in part)")] + [
            (key, section.label) for key, section in self.sections.items()
        ]

    def section_label(self, key):
        section = self.sections.get(key or "")
        return section.label if section else "Office-built forms"

    def attachable_forms(self):
        """Forms the office can attach to a step of this wizard."""
        return DynamicFormTemplate.objects.filter(
            applies_to=self.applies_to
        ).prefetch_related("fields").order_by("name")

    def step_form_name(self, step_no, title):
        if self.key == "moa":
            return f"Fields for MOA Step {step_no}: {title}"
        return f"Fields for Step {step_no}: {title}"

    def own_form(self, step_no, title):
        """The step's own inline-built form, created on first edit.

        Found through the step row first and through the legacy
        ``proposal_wizard_step`` pin second, because forms built before steps
        became reorderable are pinned by number. A newly created form gets
        both, so every reader resolves it the same way.
        """
        relation = "attached_moa_steps" if self.key == "moa" else "attached_proposal_steps"
        form_obj = (
            DynamicFormTemplate.objects.filter(
                applies_to=self.applies_to, **{f"{relation}__step_no": step_no}
            )
            .order_by("id")
            .first()
        )
        if form_obj is None and self.key != "moa":
            form_obj = (
                DynamicFormTemplate.objects.filter(
                    applies_to=self.applies_to, proposal_wizard_step=step_no
                )
                .order_by("id")
                .first()
            )
            if form_obj is not None:
                self.attach_forms(form_obj, [step_no])
        if form_obj is not None:
            return form_obj

        form_obj = DynamicFormTemplate.objects.create(
            name=self.step_form_name(step_no, title),
            slug=_unique_dynamic_form_slug(self.step_form_name(step_no, title)),
            applies_to=self.applies_to,
            proposal_wizard_step=step_no if self.key != "moa" else None,
            is_active=True,
            blocks_proposal_submission=True,
        )
        self.attach_forms(form_obj, [step_no])
        return form_obj

    def attach_forms(self, form_obj, step_nos):
        if self.key == "moa":
            form_obj.attached_moa_steps.set(
                MOAWizardStepConfig.objects.filter(step_no__in=step_nos)
            )
        else:
            form_obj.attached_proposal_steps.set(
                ProposalWizardStepConfig.objects.filter(step_no__in=step_nos)
            )

    def save_attachments(self, step_config, post_data, own_form=None):
        """Apply the "attach existing forms" picker.

        Only runs when the picker was actually submitted: an all-unchecked
        picker and a form that never rendered one look identical in the POST,
        and the difference is whether the step keeps its forms.
        """
        if post_data.get("attachment_picker") != "1":
            return

        picked = {
            _safe_int(value, 0)
            for value in post_data.getlist("attached_form_ids")
            if _safe_int(value, 0)
        }
        if own_form is not None:
            picked.add(own_form.id)

        for form_obj in self.attachable_forms():
            if form_obj.id in picked:
                if self.key == "moa":
                    form_obj.attached_moa_steps.add(step_config)
                else:
                    form_obj.attached_proposal_steps.add(step_config)
                    # Keep the legacy step-number pin in step, so forms saved
                    # before this screen existed still resolve the same way.
                    if form_obj.proposal_wizard_step in (None, step_config.step_no):
                        form_obj.proposal_wizard_step = step_config.step_no
                        form_obj.save(update_fields=["proposal_wizard_step", "updated_at"])
            else:
                if self.key == "moa":
                    form_obj.attached_moa_steps.remove(step_config)
                else:
                    form_obj.attached_proposal_steps.remove(step_config)

    def read_common_fields(self, step_config, post_data):
        step_config.title = (post_data.get("title") or step_config.title).strip()[:160]
        step_config.description = (post_data.get("description") or "").strip()[:255]
        step_config.instructions = (post_data.get("instructions") or "").strip()
        step_config.is_visible = post_data.get("is_visible") == "on"
        step_config.is_required = post_data.get("is_required") == "on"

        # A step's part and position are only changed when the screen that
        # edits them was the one submitted; a partial POST must not silently
        # turn a built-in step into an empty one.
        previous_key = step_config.section_key
        if "section_key" in post_data:
            requested_key = (post_data.get("section_key") or "").strip()
            step_config.section_key = requested_key if requested_key in self.sections else ""

        if "order" in post_data:
            order = _safe_int(post_data.get("order"), 0) or 0
            if order > 0:
                step_config.order = order

        return previous_key

    def manager_context(self):
        self.flow.ensure_defaults()
        steps = self.flow.ordered()
        attached_counts = {}
        for form_obj in self.attachable_forms():
            step_nos = (
                form_obj.attached_moa_steps.values_list("step_no", flat=True)
                if self.key == "moa"
                else form_obj.attached_proposal_steps.values_list("step_no", flat=True)
            )
            for step_no in step_nos:
                attached_counts[step_no] = attached_counts.get(step_no, 0) + 1

        for step in steps:
            step.part_label = self.section_label(step.section_key)
            step.attached_form_count = attached_counts.get(step.step_no, 0)

        return {
            "steps": steps,
            "wizard_label": self.label,
            "manager_url": self.manager_url(),
            "create_url": self.create_url(),
            "edit_url": self.edit_url(),
            "delete_url": self.delete_url(),
            "move_url": self.move_url(),
        }

    def editor_context(self, step_config):
        form_obj = self.own_form(step_config.step_no, step_config.title)
        attached_ids = set(
            form_obj.attached_moa_steps.values_list("id", flat=True)
            if self.key == "moa"
            else form_obj.attached_proposal_steps.values_list("id", flat=True)
        )
        for other in self.attachable_forms():
            other_ids = (
                other.attached_moa_steps.values_list("step_no", flat=True)
                if self.key == "moa"
                else other.attached_proposal_steps.values_list("step_no", flat=True)
            )
            other.is_attached_here = step_config.step_no in other_ids

        if self.key == "proposal" and step_config.section_key == "proponents":
            # Show the office's default proponent group instead of an empty
            # builder. Seeding only fills a form with no fields, so an admin's
            # own layout is never overwritten.
            seeded = ensure_proponent_repeater_form(step_config.step_no)
            if seeded is not None:
                form_obj = seeded

        context = _builder_context(
            form_obj,
            step_config=step_config,
            wizard_label=self.label,
            wizard_key=self.key,
            manager_url=self.manager_url(),
            section_choices=self.section_choices(),
            attachable_forms=list(self.attachable_forms()),
            positions=[(row.order or row.step_no, row.step_no) for row in self.flow.ordered()],
        )
        context["attached_form_ids"] = attached_ids
        return context


PROPOSAL_BUILDER = WizardBuilder(
    key="proposal",
    flow=proposal_flow,
    sections=PROPOSAL_SECTIONS,
    applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
    url_prefix="wizard",
    template_prefix="dashboard/admin/wizard_step",
    label="Proposal",
)

MOA_BUILDER = WizardBuilder(
    key="moa",
    flow=moa_flow,
    sections=MOA_SECTIONS,
    applies_to=DynamicFormTemplate.AppliesTo.MOA,
    url_prefix="moa_wizard",
    template_prefix="dashboard/admin/moa_wizard_step",
    label="MOA",
)

BUILDERS = {"proposal": PROPOSAL_BUILDER, "moa": MOA_BUILDER}


def _builder_for(wizard):
    builder = BUILDERS.get(wizard)
    if builder is None:
        raise ValueError(f"Unknown wizard: {wizard!r}")
    return builder


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
@admin_required
def wizard_steps_manager(request):
    return render(
        request,
        "dashboard/admin/wizard_steps_manager.html",
        PROPOSAL_BUILDER.manager_context(),
    )


@login_required
@admin_required
def moa_wizard_steps_manager(request):
    return render(
        request,
        "dashboard/admin/moa_wizard_steps_manager.html",
        MOA_BUILDER.manager_context(),
    )


def _step_edit(request, step_no, builder, template):
    builder.flow.ensure_defaults()
    step_config = get_object_or_404(builder.flow.model, step_no=step_no)

    if request.method == "POST":
        previous_key = builder.read_common_fields(step_config, request.POST)
        step_config.save()

        form_obj = builder.own_form(step_config.step_no, step_config.title)
        form_obj.name = builder.step_form_name(step_config.step_no, step_config.title)
        form_obj.save(update_fields=["name", "updated_at"])

        _save_repeater_settings(form_obj, request.POST)
        _save_dynamic_form_fields(form_obj, request.POST)
        builder.save_attachments(step_config, request.POST, own_form=form_obj)

        if previous_key and previous_key != step_config.section_key:
            messages.warning(
                request,
                f"Step {step_config.step_no} now shows "
                f"\"{builder.section_label(step_config.section_key)}\". Data saved by the "
                "previous part is still stored on the proposal, but is no longer "
                "editable from this step.",
            )
        messages.success(
            request, f"{builder.label} wizard step {step_config.step_no} and its fields updated."
        )
        return redirect(builder.manager_url())

    return render(request, template, builder.editor_context(step_config))


@login_required
@admin_required
def wizard_step_edit(request, step_no):
    return _step_edit(
        request,
        step_no,
        PROPOSAL_BUILDER,
        "dashboard/admin/wizard_step_form.html",
    )


@login_required
@admin_required
def moa_wizard_step_edit(request, step_no):
    return _step_edit(
        request,
        step_no,
        MOA_BUILDER,
        "dashboard/admin/moa_wizard_step_form.html",
    )


def _step_create(request, builder, template):
    builder.flow.ensure_defaults()
    next_step_no = builder.flow.next_step_no()

    if request.method == "POST":
        step_no = _safe_int(request.POST.get("step_no"), 0)
        title = (request.POST.get("title") or "").strip()
        requested_key = (request.POST.get("section_key") or "").strip()

        if step_no <= 0:
            messages.error(request, "Step number must be a positive integer.")
        elif builder.flow.model.objects.filter(step_no=step_no).exists():
            messages.error(request, f"Step number {step_no} already exists.")
        elif not title:
            messages.error(request, "Title is required.")
        elif requested_key and requested_key not in builder.sections:
            messages.error(request, "That is not one of this wizard's built-in parts.")
        else:
            step_config = builder.flow.model(
                step_no=step_no,
                order=_safe_int(request.POST.get("order"), 0) or builder.flow.next_order(),
                section_key=requested_key,
                title=title[:160],
                description=(request.POST.get("description") or "").strip()[:255],
                instructions=(request.POST.get("instructions") or "").strip(),
                is_visible=request.POST.get("is_visible") == "on",
                is_required=request.POST.get("is_required") == "on",
            )
            step_config.save()

            form_obj = builder.own_form(step_config.step_no, step_config.title)
            _save_repeater_settings(form_obj, request.POST)
            _save_dynamic_form_fields(form_obj, request.POST)
            builder.save_attachments(step_config, request.POST, own_form=form_obj)

            messages.success(
                request,
                f"{builder.label} wizard step {step_no} created. "
                "Add or attach the fields it needs, then reorder it into place.",
            )
            return redirect(builder.edit_url(), step_no=step_no)

    return render(
        request,
        template,
        _builder_context(
            next_step_no=next_step_no,
            wizard_label=builder.label,
            wizard_key=builder.key,
            manager_url=builder.manager_url(),
            section_choices=builder.section_choices(),
            attachable_forms=list(builder.attachable_forms()),
            next_order=builder.flow.next_order(),
        ),
    )


@login_required
@admin_required
def wizard_step_create(request):
    return _step_create(
        request, PROPOSAL_BUILDER, "dashboard/admin/wizard_step_create_form.html"
    )


@login_required
@admin_required
def moa_wizard_step_create(request):
    return _step_create(
        request, MOA_BUILDER, "dashboard/admin/moa_wizard_step_create_form.html"
    )


def _step_move(request, step_no, builder):
    direction = request.POST.get("direction", "down")
    if builder.flow.move(step_no, direction):
        messages.success(request, f"Step {step_no} moved.")
    else:
        messages.info(request, f"Step {step_no} is already at the {'bottom' if direction == 'down' else 'top'}.")
    return redirect(builder.manager_url())


@login_required
@admin_required
@require_POST
def wizard_step_move(request, step_no):
    return _step_move(request, step_no, PROPOSAL_BUILDER)


@login_required
@admin_required
@require_POST
def moa_wizard_step_move(request, step_no):
    return _step_move(request, step_no, MOA_BUILDER)


def _step_delete(request, step_no, builder):
    step_config = get_object_or_404(builder.flow.model, step_no=step_no)
    title = step_config.title

    # Detach rather than delete: an office form is reusable, and the answers
    # already given to it belong to proposals, not to the step. Only the
    # auto-created placeholder the step was born with is cleaned up, and only
    # when the office never put any fields in it.
    if builder.key == "moa":
        linked = DynamicFormTemplate.objects.filter(attached_moa_steps=step_config)
    else:
        linked = DynamicFormTemplate.objects.filter(
            Q(attached_proposal_steps=step_config) | Q(proposal_wizard_step=step_no)
        ).distinct()

    for form_obj in linked:
        if builder.key == "moa":
            form_obj.attached_moa_steps.remove(step_config)
            still_bound = form_obj.attached_moa_steps.exists()
        else:
            form_obj.attached_proposal_steps.remove(step_config)
            if form_obj.proposal_wizard_step == step_no:
                form_obj.proposal_wizard_step = None
                form_obj.save(update_fields=["proposal_wizard_step", "updated_at"])
            still_bound = form_obj.attached_proposal_steps.exists()

        if not still_bound and not form_obj.fields.exists():
            form_obj.delete()

    step_config.delete()

    messages.success(
        request,
        f"{builder.label} wizard step {step_no} ({title}) deleted. "
        "Forms attached to it were kept in the form library.",
    )
    return redirect(builder.manager_url())


@login_required
@admin_required
@require_POST
def wizard_step_delete(request, step_no):
    return _step_delete(request, step_no, PROPOSAL_BUILDER)


@login_required
@admin_required
@require_POST
def moa_wizard_step_delete(request, step_no):
    return _step_delete(request, step_no, MOA_BUILDER)
