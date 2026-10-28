"""
Remove redundant built-in step fields piled onto Step 19 (Research Abstract Upload).

When ``details/0023_split_wizard_into_flows`` first ran in production, its
step-form renumbering walked ``RESEARCH_RENUMBER`` in ascending order
(``7 -> 8 -> 9 -> ... -> 17 -> 18 -> 20``), cascading every
``DynamicFormTemplate`` from old steps 7-17 onto Research Abstract Upload
(step 20 in the split, mapped to 18 by ``0026`` and shifted to 19 by ``0027``).

Those forms carry the built-in mirror fields for Steps 8, 11, 12, 13, and 14
(Budgetary Requirement, Extension Venue / Estimated Month / Estimated Year,
Rationale / Background, Significance, General Objective). Because
``NATIVE_STEP_FIELDS`` only hides a mirror field on its own home step, every
one of those displaced fields rendered a second time on Step 19 (Research
Abstract Upload) and blocked proposal submission.

This migration moves each displaced step form back to its home step when that
step has no form of its own (or deletes duplicate/emptied remnants), removes
any Step-19 shadow answers recorded against built-in mirror fields, strips any
other foreign built-in mirror fields from Step 19, and backfills missing
default mirror forms on databases that already use seeded step forms.
"""

import re

from django.db import migrations


RESEARCH_ABSTRACT_STEP_NO = 19

SEEDED_SLUG_RE = re.compile(r"^(?:step-(\d+)-fields|fields-for-step-(\d+)(?:-|$))")
SEEDED_NAME_RE = re.compile(r"^Fields for Step (\d+)(.*)$")

NATIVE_KEYS_BY_STEP = {
    1: {"extension_type", "scope_type", "research_title"},
    2: {"title"},
    4: {"implementing_agency"},
    5: {"beneficiaries_count", "beneficiaries_who", "who_beneficiaries"},
    7: {
        "technology_title",
        "utility_model_registration_number",
        "utility_model_description",
    },
    8: {"budgetary_requirement"},
    11: {"extension_venue", "estimated_month", "estimated_year"},
    12: {"rationale_background"},
    13: {"significance"},
    14: {"general_objective"},
    17: {"work_plan_file", "gantt_chart_file"},
    18: {"funding_file"},
    20: {"certificate_of_completion_file"},
}

FOREIGN_NATIVE_KEYS = set().union(*NATIVE_KEYS_BY_STEP.values())

DEFAULT_MIRROR_FIELDS = {
    8: [
        {
            "key": "budgetary_requirement",
            "label": "Budgetary Requirement",
            "type": "TEXTAREA",
            "placeholder": "Describe budget details",
        },
    ],
    11: [
        {
            "key": "extension_venue",
            "label": "Extension Venue / Site",
            "type": "TEXT",
            "placeholder": "Enter venue",
        },
        {
            "key": "estimated_month",
            "label": "Estimated Month",
            "type": "SELECT",
            "choices": (
                "January|January\nFebruary|February\nMarch|March\nApril|April\n"
                "May|May\nJune|June\nJuly|July\nAugust|August\nSeptember|September\n"
                "October|October\nNovember|November\nDecember|December"
            ),
            "placeholder": "Choose month",
        },
        {
            "key": "estimated_year",
            "label": "Estimated Year",
            "type": "NUMBER",
            "placeholder": "e.g., 2026",
        },
    ],
    12: [
        {
            "key": "rationale_background",
            "label": "Rationale / Background",
            "type": "TEXTAREA",
            "placeholder": "Provide rationale background",
        },
    ],
    13: [
        {
            "key": "significance",
            "label": "Significance",
            "type": "TEXTAREA",
            "placeholder": "Describe significance",
        },
    ],
    14: [
        {
            "key": "general_objective",
            "label": "General Objective",
            "type": "TEXTAREA",
            "placeholder": "Enter general objective",
        },
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
    19: [
        {
            "key": "research_abstract_file",
            "label": "Research Abstract File",
            "type": "FILE",
            "help_text": "This file is required for research-based proposals.",
            "depends_on_key": "extension_type",
            "depends_on_value": "RESEARCH_FACULTY,RESEARCH_STUDENT",
        },
        {
            "key": "complete_research_file",
            "label": "Complete Research File",
            "type": "FILE",
            "help_text": "Upload the complete research so reviewers can check its content.",
            "depends_on_key": "extension_type",
            "depends_on_value": "RESEARCH_FACULTY,RESEARCH_STUDENT",
        },
    ],
    20: [
        {
            "key": "certificate_of_completion_file",
            "label": "Certificate of Completion File",
            "type": "FILE",
            "help_text": "This file is required for Research-based (Faculty) proposals.",
            "depends_on_key": "extension_type",
            "depends_on_value": "RESEARCH_FACULTY",
        },
    ],
}


def _delete_fields(apps, field_ids):
    if not field_ids:
        return
    apps.get_model("details", "DynamicFormAnswer").objects.filter(
        field_id__in=field_ids
    ).delete()
    apps.get_model("details", "DynamicFormField").objects.filter(
        id__in=field_ids
    ).delete()


def _delete_forms(apps, form_ids):
    if not form_ids:
        return
    apps.get_model("details", "DynamicFormAnswer").objects.filter(
        field__form_id__in=form_ids
    ).delete()
    apps.get_model("details", "DynamicFormRow").objects.filter(
        response__form_id__in=form_ids
    ).delete()
    apps.get_model("details", "DynamicFormResponse").objects.filter(
        form_id__in=form_ids
    ).delete()
    apps.get_model("details", "DynamicFormField").objects.filter(
        form_id__in=form_ids
    ).delete()
    apps.get_model("details", "DynamicFormTemplate").objects.filter(
        id__in=form_ids
    ).delete()


def _prune_empty_responses(apps, form_id):
    Response = apps.get_model("details", "DynamicFormResponse")
    Answer = apps.get_model("details", "DynamicFormAnswer")
    Row = apps.get_model("details", "DynamicFormRow")
    for response_id in list(
        Response.objects.filter(form_id=form_id).values_list("id", flat=True)
    ):
        if (
            not Answer.objects.filter(response_id=response_id).exists()
            and not Row.objects.filter(response_id=response_id).exists()
        ):
            Response.objects.filter(id=response_id).delete()


def _unique_slug(FormTemplate, base, exclude_id=None):
    candidate = base
    suffix = 2
    qs = FormTemplate.objects.all()
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    while qs.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _infer_target_step(form, field_keys):
    slug_match = SEEDED_SLUG_RE.match(form.slug or "")
    if slug_match:
        old_no = int(slug_match.group(1) or slug_match.group(2))
        if 7 <= old_no <= 17:
            return old_no, old_no + 1

    name_match = SEEDED_NAME_RE.match(form.name or "")
    if name_match:
        old_no = int(name_match.group(1))
        if 7 <= old_no <= 17:
            return old_no, old_no + 1

    if field_keys:
        matches = [
            step_no
            for step_no, keys in NATIVE_KEYS_BY_STEP.items()
            if field_keys <= keys
        ]
        if len(matches) == 1:
            return None, matches[0]

    return None, None


def _restored_name(current_name, old_no, target_step):
    match = SEEDED_NAME_RE.match(current_name or "")
    if not match:
        return current_name
    numbered = int(match.group(1))
    suffix = match.group(2) or ""
    if old_no is not None and numbered == old_no and (not suffix or suffix.startswith(":")):
        return f"Fields for Step {target_step}{suffix}"
    if numbered == RESEARCH_ABSTRACT_STEP_NO:
        return f"Fields for Step {target_step}"
    return current_name


def _backfill_missing_mirrors(apps):
    FormTemplate = apps.get_model("details", "DynamicFormTemplate")
    FormField = apps.get_model("details", "DynamicFormField")

    if not FormTemplate.objects.filter(
        applies_to="PROPOSAL", slug__startswith="step-"
    ).exists():
        return

    for step_no, specs in DEFAULT_MIRROR_FIELDS.items():
        form = (
            FormTemplate.objects.filter(
                applies_to="PROPOSAL", proposal_wizard_step=step_no
            )
            .order_by("id")
            .first()
        )
        if form is not None and step_no not in {17, 18, 19, 20}:
            continue
        if form is not None and form.is_repeater:
            continue
        if form is None:
            slug = _unique_slug(FormTemplate, f"step-{step_no}-fields")
            form = FormTemplate.objects.create(
                name=f"Fields for Step {step_no}",
                slug=slug,
                applies_to="PROPOSAL",
                proposal_wizard_step=step_no,
                is_active=True,
                blocks_proposal_submission=True,
            )
        next_order = (
            FormField.objects.filter(form_id=form.id)
            .order_by("-order")
            .values_list("order", flat=True)
            .first()
            or 0
        )
        for item in specs:
            existing = FormField.objects.filter(
                form_id=form.id, field_key=item["key"]
            ).first()
            if existing is not None:
                if (
                    step_no == 20
                    and item["key"] == "certificate_of_completion_file"
                    and existing.depends_on_value == "RESEARCH_FACULTY,RESEARCH_STUDENT"
                ):
                    existing.depends_on_key = "extension_type"
                    existing.depends_on_value = "RESEARCH_FACULTY"
                    existing.save(update_fields=["depends_on_key", "depends_on_value"])
                continue
            next_order += 1
            FormField.objects.create(
                form=form,
                field_key=item["key"],
                label=item["label"],
                field_type=item["type"],
                choices_text=item.get("choices", ""),
                placeholder=item.get("placeholder", ""),
                help_text=item.get("help_text", ""),
                required=item.get("required", True),
                depends_on_key=item.get("depends_on_key", ""),
                depends_on_value=item.get("depends_on_value", ""),
                order=next_order,
            )


def _update_step_descriptions(apps):
    StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
    StepConfig.objects.filter(
        step_no=19, description="Required for research-based proposals"
    ).update(
        description="Research abstract and complete research (required for research-based proposals)"
    )
    StepConfig.objects.filter(
        step_no=20, description="Required for research-based proposals"
    ).update(description="Required for Research-based (Faculty) proposals")


def clean_research_abstract_step(apps, schema_editor):
    FormTemplate = apps.get_model("details", "DynamicFormTemplate")
    FormField = apps.get_model("details", "DynamicFormField")
    Answer = apps.get_model("details", "DynamicFormAnswer")

    _update_step_descriptions(apps)

    step_forms = list(
        FormTemplate.objects.filter(
            applies_to="PROPOSAL",
            proposal_wizard_step=RESEARCH_ABSTRACT_STEP_NO,
        ).order_by("id")
    )

    for form in step_forms:
        fields = list(
            FormField.objects.filter(form_id=form.id).values("id", "field_key")
        )
        field_keys = {item["field_key"] for item in fields}
        old_no, target_step = _infer_target_step(form, field_keys)

        if target_step is not None:
            repurposed_for_step_19 = (form.name or "").startswith(
                f"Fields for Step {RESEARCH_ABSTRACT_STEP_NO}"
            ) and bool(field_keys - FOREIGN_NATIVE_KEYS)

            if repurposed_for_step_19:
                foreign_ids = [
                    item["id"]
                    for item in fields
                    if item["field_key"] in FOREIGN_NATIVE_KEYS
                ]
                _delete_fields(apps, foreign_ids)
                _prune_empty_responses(apps, form.id)
                if SEEDED_SLUG_RE.match(form.slug or ""):
                    form.slug = _unique_slug(
                        FormTemplate,
                        f"step-{RESEARCH_ABSTRACT_STEP_NO}-fields",
                        exclude_id=form.id,
                    )
                    form.save(update_fields=["slug"])
                continue

            if not fields and not form.is_repeater:
                _delete_forms(apps, [form.id])
                continue

            target_has_form = FormTemplate.objects.filter(
                applies_to="PROPOSAL", proposal_wizard_step=target_step
            ).exists()
            if target_has_form and field_keys <= FOREIGN_NATIVE_KEYS and not form.is_repeater:
                _delete_forms(apps, [form.id])
                continue

            target_native_keys = NATIVE_KEYS_BY_STEP.get(target_step, set())
            stray_foreign_ids = [
                item["id"]
                for item in fields
                if item["field_key"] in (FOREIGN_NATIVE_KEYS - target_native_keys)
            ]
            _delete_fields(apps, stray_foreign_ids)
            native_field_ids = [
                item["id"]
                for item in fields
                if item["field_key"] in target_native_keys
            ]
            if native_field_ids:
                Answer.objects.filter(field_id__in=native_field_ids).delete()
            _prune_empty_responses(apps, form.id)

            form.proposal_wizard_step = target_step
            form.name = _restored_name(form.name, old_no, target_step)
            form.save(update_fields=["proposal_wizard_step", "name"])
            continue

        foreign_ids = [
            item["id"] for item in fields if item["field_key"] in FOREIGN_NATIVE_KEYS
        ]
        if foreign_ids:
            _delete_fields(apps, foreign_ids)
            _prune_empty_responses(apps, form.id)
        if not form.is_repeater and not FormField.objects.filter(form_id=form.id).exists():
            _delete_forms(apps, [form.id])

    _backfill_missing_mirrors(apps)


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0053_convert_programs_into_legacy_proposals"),
    ]

    operations = [
        migrations.RunPython(clean_research_abstract_step, migrations.RunPython.noop),
    ]
