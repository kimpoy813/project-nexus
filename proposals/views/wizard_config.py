"""
The wizard's step list: seeding, navigation, and the per-step field forms.

Everything that used to read "which steps exist" from a hardcoded 19-item
list now goes through here. The admin's ``ProposalWizardStepConfig`` rows are
the single source of truth; on a fresh database they are created from the
built-in layout in ``details.wizard_defaults`` the first time anything asks.
"""

from django.db import transaction
from django.utils.text import slugify

from details.models import DynamicFormField, DynamicFormTemplate, ProposalWizardStepConfig
from details.proponent_fields import ensure_proponent_repeater_form
from details.wizard_defaults import DEFAULT_WIZARD_STEPS

from .sections import get_section


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _unique_form_slug(name, existing=None):
    base = slugify(name)[:200] or "wizard-step-fields"
    candidate = base
    suffix = 2
    qs = DynamicFormTemplate.objects.all()
    if existing is not None:
        qs = qs.exclude(pk=existing.pk)
    while qs.filter(slug=candidate).exists():
        candidate = f"{base[:190]}-{suffix}"
        suffix += 1
    return candidate


def step_form_name(step_config):
    return f"Fields for Step {step_config.step_no}: {step_config.title}"


def step_form(step_config, *, create=True):
    """The admin-built field form attached to a step (one per step).

    The Proponents section is special-cased: its form is a repeatable group
    that stores rows on the proposal, and it comes pre-filled with the
    office's default columns.
    """
    section = get_section(step_config.section_key)
    if section is not None and section.is_proponents:
        form = ensure_proponent_repeater_form(step_config.step_no, create=create)
        if form is not None:
            return form

    form = (
        DynamicFormTemplate.objects.filter(
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step_config.step_no,
        )
        .order_by("id")
        .first()
    )
    if form is not None or not create:
        return form

    name = step_form_name(step_config)
    return DynamicFormTemplate.objects.create(
        name=name,
        slug=_unique_form_slug(name),
        applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
        proposal_wizard_step=step_config.step_no,
        is_active=True,
        blocks_proposal_submission=True,
    )


def seed_section_fields(step_config, form=None, *, merge=False):
    """Give a step's form the section's default editable fields.

    By default only fills a form that has **no** fields, so an admin's own
    layout is never overwritten. With ``merge=True`` (used when the admin
    assigns a section to a step that already has fields) the section's
    defaults are added alongside the existing ones, skipping any key that is
    already present. Safe to call repeatedly.
    """
    section = get_section(step_config.section_key)
    if section is None or not section.default_fields:
        return []
    form = form or step_form(step_config)
    if form is None:
        return []
    existing_keys = set(form.fields.values_list("field_key", flat=True))
    if existing_keys and not merge:
        return []
    next_order = (form.fields.order_by("-order").values_list("order", flat=True).first() or 0) + 1
    created = []
    for spec in section.default_fields:
        if spec["field_key"] in existing_keys:
            continue
        created.append(
            DynamicFormField.objects.create(
                form=form,
                label=spec["label"],
                field_key=spec["field_key"],
                field_type=spec.get("field_type", "TEXT"),
                required=spec.get("required", True),
                placeholder=spec.get("placeholder", ""),
                help_text=spec.get("help_text", ""),
                choices_text=spec.get("choices_text", ""),
                depends_on_key=spec.get("depends_on_key", ""),
                depends_on_value=spec.get("depends_on_value", ""),
                order=next_order,
            )
        )
        next_order += 1
    return created


@transaction.atomic
def assign_section(step_config, new_key):
    """Point a step at a different section, swapping its native fields.

    A section's *native* fields (``title``, ``budgetary_requirement``, ...)
    exist on the step's form only so the admin can edit their labels; their
    values live on the Proposal. When the section leaves the step those rows
    would otherwise linger as ordinary required inputs nobody can fill, so
    they are removed here and the new section's defaults are seeded (into an
    otherwise empty form only - an admin's own extra fields are kept).

    Moving the Proponents section also moves its repeatable group: the old
    step's form goes back to a plain field set, and the new step's form is
    converted (or created) as the proponent repeater.
    """
    old_section = get_section(step_config.section_key)
    new_section = get_section(new_key)
    new_key = new_section.key if new_section else ""
    if (step_config.section_key or "") == new_key:
        return step_config

    form = step_form(step_config, create=False)
    if form is not None:
        if old_section is not None and old_section.native_keys:
            form.fields.filter(field_key__in=list(old_section.native_keys)).delete()
        if old_section is not None and old_section.is_proponents and form.is_proponent_repeater:
            # The roster no longer lives here; drop the proponent columns and
            # leave a plain field set the admin can reuse.
            form.fields.filter(maps_to__gt="").delete()
            form.is_repeater = False
            form.row_store = DynamicFormTemplate.RowStore.GENERIC
            form.save(update_fields=["is_repeater", "row_store", "updated_at"])

    step_config.section_key = new_key
    step_config.save(update_fields=["section_key", "updated_at"])

    if new_section is not None:
        seed_section_fields(step_config, step_form(step_config), merge=True)
    return step_config


@transaction.atomic
def ensure_wizard_steps():
    """Create the built-in step list on an empty table. Returns the configs.

    Idempotent: once any row exists the admin owns the table and nothing is
    added, removed, or renamed here.
    """
    if not ProposalWizardStepConfig.objects.exists():
        ProposalWizardStepConfig.objects.bulk_create(
            [
                ProposalWizardStepConfig(
                    step_no=no,
                    section_key=section_key,
                    title=title,
                    description=desc,
                    is_visible=True,
                    is_required=True,
                )
                for no, section_key, title, desc in DEFAULT_WIZARD_STEPS
            ]
        )
        for config in ProposalWizardStepConfig.objects.all():
            if get_section(config.section_key) and get_section(config.section_key).default_fields:
                seed_section_fields(config)
    return list(ProposalWizardStepConfig.objects.all().order_by("step_no"))


def step_config_map():
    """``{step_no: config}`` for every step, seeding the defaults if needed."""
    return {config.step_no: config for config in ensure_wizard_steps()}


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def visible_step_numbers():
    numbers = list(
        ProposalWizardStepConfig.objects.filter(is_visible=True)
        .order_by("step_no")
        .values_list("step_no", flat=True)
    )
    if numbers:
        return numbers
    if not ProposalWizardStepConfig.objects.exists():
        return [no for no, *_rest in DEFAULT_WIZARD_STEPS]
    return [1]


def required_step_numbers():
    return list(
        ProposalWizardStepConfig.objects.filter(is_visible=True, is_required=True)
        .order_by("step_no")
        .values_list("step_no", flat=True)
    )


def last_step_number():
    numbers = visible_step_numbers()
    return numbers[-1] if numbers else 1


def normalize_step(step):
    """Clamp ``step`` onto a visible step (the next one up, else the last)."""
    visible = visible_step_numbers()
    if step in visible:
        return step
    for no in visible:
        if no > step:
            return no
    return visible[-1]


def next_step(step):
    for no in visible_step_numbers():
        if no > step:
            return no
    return None


def previous_step(step):
    for no in reversed(visible_step_numbers()):
        if no < step:
            return no
    return None


def step_summaries():
    """``[{"no", "title", "desc", "section"}]`` for public/overview pages."""
    return [
        {"no": c.step_no, "title": c.title, "desc": c.description, "section": c.section_key}
        for c in ensure_wizard_steps()
        if c.is_visible
    ]


def step_title_map():
    return {c.step_no: c.title for c in ensure_wizard_steps()}
