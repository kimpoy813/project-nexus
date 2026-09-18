"""
Repeatable groups (repeaters) inside the proposal wizard.

An admin can turn any admin-built form into a *repeatable group*: the fields
are printed once per row and the proponent adds as many rows as they need.
Step 3 (Proponents) uses the ``PROPONENT`` row store, where each row is a real
``ProposalProponent`` record - the same records the generated documents, the
review screens, and the dashboards already read.

This module owns the browser <-> database contract for those rows:

* input names (``repeater_<form>_row_<index>_field_<field>`` and friends),
* turning saved data into the ``repeater_rows`` the template renders,
* reading a submitted step back into proponent rows / ``DynamicFormRow`` rows,
* the required-field and min/max checks shared by step completion, the
  "Save & Next" path, and final submission.

Only *mapped* proponent fields are special: a field whose ``maps_to`` is blank
is kept as an extra detail of that proponent (``ProposalProponent.extra_fields``)
so the admin can add anything else they need without a database change.
"""

from details.models import DynamicFormField, DynamicFormResponse, DynamicFormRow

from ..models import ProposalProponent
from .dynamic_fields import (
    DEPENDENCY_PARENT_NOT_FOUND,
    dependency_is_satisfied,
    dynamic_parent_values_from_post,
    dynamic_parent_values_from_saved,
)
from .helpers import _to_int


#: Shown in the builder and the wizard: rows cannot hold file uploads.
FILE_FIELDS_UNSUPPORTED = (
    "File upload fields are not supported inside a repeatable group. "
    "Add them as normal fields on the step instead."
)


# ---------------------------------------------------------------------------
# Input names - the single source of truth for the template and the view
# ---------------------------------------------------------------------------

def _row_field_input(form, index, field):
    return f"repeater_{form.id}_row_{index}_field_{field.id}"


def _row_id_input(form, index):
    return f"repeater_{form.id}_row_id_{index}"


def _row_count_input(form):
    return f"repeater_{form.id}_rows"


def _remove_input(form):
    return f"repeater_{form.id}_remove"


def _move_input(form):
    return f"repeater_{form.id}_move"


def _add_row_input(form):
    return f"repeater_{form.id}_add_row"


def _renderable_fields(form):
    """Fields shown per row. File uploads are skipped (see the module docstring)."""
    return [
        field
        for field in form.fields.all()
        if field.field_type != DynamicFormField.FieldType.FILE
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _proponent_row_values(proponent, fields):
    values = {}
    extra = proponent.extra_fields or {}
    for field in fields:
        if field.maps_to:
            values[field.field_key] = getattr(proponent, field.maps_to, "") or ""
        else:
            values[field.field_key] = extra.get(field.field_key, "") or ""
    return values


def _generic_row_values(row, fields):
    data = row.data or {}
    return {field.field_key: data.get(field.field_key, "") or "" for field in fields}


def _blank_values(fields):
    return {field.field_key: "" for field in fields}


def _row_cells(fields, values):
    """Pairs of (field, value) the template can loop over.

    Django templates cannot look a value up by a *variable* dictionary key, so
    the lookup happens here once instead of through ``{% for k, v in ... %}``
    gymnastics in the markup.
    """
    return [{"field": field, "value": values.get(field.field_key, "")} for field in fields]


def _build_rows(proposal, form):
    """Rows for ``form``, as plain dicts the template can render.

    ``row_id`` is ``None`` for a row that has not been saved yet (a blank
    starter row, or one the proponent added in the browser).
    """
    fields = _renderable_fields(form)
    rows = []

    if form.row_store == form.RowStore.PROPONENT and form.is_repeater:
        for index, proponent in enumerate(proposal.proponents.all().select_related("user")):
            values = _proponent_row_values(proponent, fields)
            rows.append({
                "row_id": proponent.id,
                "values": values,
                "cells": _row_cells(fields, values),
                "title": proponent.full_name or f"{form.row_label} {index + 1}",
                "locked": proponent.user_id == proposal.created_by_id,
                "user_id": proponent.user_id,
            })
    else:
        response = DynamicFormResponse.objects.filter(form=form, proposal=proposal).first()
        if response is not None:
            for row in response.rows.all():
                values = _generic_row_values(row, fields)
                rows.append({
                    "row_id": row.id,
                    "values": values,
                    "cells": _row_cells(fields, values),
                    "title": f"{form.row_label} {len(rows) + 1}",
                    "locked": False,
                    "user_id": None,
                })

    # A repeater with nothing in it still shows the first blank row, and a
    # minimum row count is honoured so the required rows are always visible.
    minimum = max(form.repeater_min_rows or 0, 1 if not rows else 0)
    while len(rows) < minimum:
        values = _blank_values(fields)
        rows.append({
            "row_id": None,
            "values": values,
            "cells": _row_cells(fields, values),
            "title": f"{form.row_label} {len(rows) + 1}",
            "locked": False,
            "user_id": None,
        })

    for index, row in enumerate(rows):
        row["index"] = index
        row["number"] = index + 1

    return rows


def attach_repeater_rows(proposal, forms):
    """Expose ``repeater_rows`` / ``repeater_fields`` on each repeater form.

    ``repeater_template_cells`` backs the ``<template>`` the "+ Add" button
    clones. It is deliberately built from *blank* values rather than from the
    first saved row: cloning a filled-in row would hand the proponent a copy of
    an existing entry, and saving that row stores the same entry twice.
    """
    for form in forms:
        if not form.is_repeater:
            continue
        form.repeater_fields = _renderable_fields(form)
        form.repeater_rows = _build_rows(proposal, form)
        form.repeater_template_cells = _row_cells(
            form.repeater_fields, _blank_values(form.repeater_fields)
        )
    return forms


def proponent_repeater_form_for_step(step):
    """The active repeater that owns the proponent list on ``step``, if any.

    Only the first (lowest id) proponent-storing repeater on a step is used, so
    a stray duplicate form cannot render - or overwrite - the same rows twice.
    """
    from details.models import DynamicFormTemplate

    return (
        DynamicFormTemplate.objects.filter(
            is_active=True,
            is_repeater=True,
            row_store=DynamicFormTemplate.RowStore.PROPONENT,
            applies_to=DynamicFormTemplate.AppliesTo.PROPOSAL,
            proposal_wizard_step=step,
        )
        .order_by("id")
        .first()
    )


# ---------------------------------------------------------------------------
# Validation helpers (shared by save, step completion and submission)
# ---------------------------------------------------------------------------

def _posted_row_count(form, request):
    """Rows posted for ``form``.

    The hidden ``..._rows`` counter is authoritative; the highest submitted
    field index is used as a fallback so a form posted without JavaScript still
    saves every row it contained.
    """
    declared = _to_int(request.POST.get(_row_count_input(form))) or 0

    detected = -1
    for field in _renderable_fields(form):
        detected = max(detected, _highest_row_index(form, request, field.id))

    return max(declared, detected + 1, 0)


def _highest_row_index(form, request, field_id):
    prefix = f"repeater_{form.id}_row_"
    suffix = f"_field_{field_id}"
    highest = -1
    for key in request.POST.keys():
        if key.startswith(prefix) and key.endswith(suffix):
            middle = key[len(prefix):-len(suffix)]
            if middle.isdigit():
                highest = max(highest, int(middle))
    return highest


def _row_values(form, request, index, fields):
    return {
        field.field_key: (request.POST.get(_row_field_input(form, index, field)) or "").strip()
        for field in fields
    }


def _row_missing_labels(form, index, values, fields, fallback_parent_value):
    """Required-but-empty labels for one row, honouring in-row dependencies."""
    missing = []
    for field in fields:
        if not field.required:
            continue
        if field.depends_on_key:
            parent_value = values.get(field.depends_on_key, fallback_parent_value)
            if not dependency_is_satisfied(field, parent_value):
                continue
        if not (values.get(field.field_key) or "").strip():
            missing.append(f"{form.row_label} {index + 1} - {field.label}")
    return missing


def _row_has_content(values):
    return any((value or "").strip() for value in values.values())


def _min_rows_missing(form, row_count):
    minimum = form.repeater_min_rows or 0
    if row_count >= minimum:
        return []
    return [
        f"{form.name}: at least {minimum} {form.row_label.lower()} row(s) are required."
    ]


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def save_repeater_rows(proposal, form, request, user):
    """Persist one repeatable group from a POSTed step.

    Returns ``(missing, meta)`` where ``missing`` lists human-readable required
    problems and ``meta`` carries information the caller needs (currently
    ``explicit_role_ids``: proponent rows whose role the user set by hand, so
    the automatic role assignment does not overwrite them).
    """
    if not form.is_repeater:
        return [], {}

    removed_ids = _apply_row_commands(proposal, form, request)

    if form.row_store == form.RowStore.PROPONENT:
        return _save_proponent_rows(proposal, form, request, removed_ids)
    return _save_generic_rows(proposal, form, request, user, removed_ids)


def _apply_row_commands(proposal, form, request):
    """Handle the per-row remove / move submit buttons (before reading values).

    Returns the ids of the rows that were actually deleted. A removed row is
    still in the submitted page - the Remove button only flags it - so the save
    below has to know which row ids are gone, or it reads the flagged row's
    still-posted values back in as a brand new row and the entry comes straight
    back.
    """
    if form.row_store == form.RowStore.PROPONENT:
        return _apply_proponent_row_commands(proposal, form, request)
    return _apply_generic_row_commands(proposal, form, request)


def _apply_proponent_row_commands(proposal, form, request):
    removed_ids = set()

    remove_ids = _int_list(request.POST.getlist(_remove_input(form)))
    if remove_ids:
        removable = proposal.proponents.filter(id__in=remove_ids).exclude(
            user_id=proposal.created_by_id
        )
        removed_ids = set(removable.values_list("id", flat=True))
        if removed_ids:
            removable.delete()

    move = (request.POST.get(_move_input(form)) or "").strip()
    if move:
        row_id, _, direction = move.partition(":")
        _move_proponent_row(proposal, _to_int(row_id), direction)

    return removed_ids


def _move_proponent_row(proposal, row_id, direction):
    rows = list(proposal.proponents.all())
    index = next((i for i, row in enumerate(rows) if row.id == row_id), None)
    if index is None:
        return
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(rows):
        return

    # Normalise first: rows predating the sort_order column (or rows created in
    # the same request) would otherwise leave the swap ambiguous.
    for position, row in enumerate(rows, start=1):
        row.sort_order = position

    rows[index].sort_order, rows[target].sort_order = (
        rows[target].sort_order,
        rows[index].sort_order,
    )
    ProposalProponent.objects.bulk_update(rows, ["sort_order"])


def _apply_generic_row_commands(proposal, form, request):
    removed_ids = set()

    response = DynamicFormResponse.objects.filter(form=form, proposal=proposal).first()
    if response is None:
        return removed_ids

    remove_ids = _int_list(request.POST.getlist(_remove_input(form)))
    if remove_ids:
        removable = response.rows.filter(id__in=remove_ids)
        removed_ids = set(removable.values_list("id", flat=True))
        if removed_ids:
            removable.delete()

    move = (request.POST.get(_move_input(form)) or "").strip()
    if move:
        row_id, _, direction = move.partition(":")
        rows = list(response.rows.all())
        index = next((i for i, row in enumerate(rows) if row.id == _to_int(row_id)), None)
        if index is not None:
            target = index - 1 if direction == "up" else index + 1
            if 0 <= target < len(rows):
                rows[index].row_index, rows[target].row_index = (
                    rows[target].row_index,
                    rows[index].row_index,
                )
                DynamicFormRow.objects.bulk_update(rows, ["row_index"])

    return removed_ids


def _save_proponent_rows(proposal, form, request, removed_ids=()):
    fields = list(form.fields.all())
    editable_fields = _renderable_fields(form)
    row_count = _posted_row_count(form, request)
    post_parent_values = dynamic_parent_values_from_post([form], request)

    removed_ids = set(removed_ids or ())
    existing = {row.id: row for row in proposal.proponents.all()}
    missing = []
    explicit_role_ids = set()
    saved_count = len(existing)
    next_sort = max([row.sort_order or 0 for row in existing.values()], default=0)

    for index in range(row_count):
        row_id = _to_int(request.POST.get(_row_id_input(form, index)))
        if row_id in removed_ids:
            # Deleted by the Remove button a moment ago: its inputs are still
            # in the POST, but re-saving them would resurrect the entry.
            continue
        values = _row_values(form, request, index, editable_fields)
        proponent = existing.get(row_id)

        if proponent is None:
            if not _row_has_content(values):
                continue
            if form.max_rows is not None and saved_count >= form.max_rows:
                missing.append(
                    f"{form.name}: a maximum of {form.max_rows} {form.row_label.lower()} row(s) is allowed."
                )
                continue
            next_sort += 1
            proponent = ProposalProponent(
                proposal=proposal,
                full_name="",
                sort_order=next_sort,
            )
            saved_count += 1

        missing.extend(
            _row_missing_labels(
                form, index, values, editable_fields, _fallback_parent(post_parent_values)
            )
        )

        extra = dict(proponent.extra_fields or {})
        for field in fields:
            if field.field_type == DynamicFormField.FieldType.FILE:
                continue
            value = values.get(field.field_key, "")
            if field.maps_to:
                setattr(proponent, field.maps_to, value)
            elif field.field_key in extra or value:
                extra[field.field_key] = value
        proponent.extra_fields = extra

        if not (proponent.full_name or "").strip() and proponent.user_id:
            # A picked account always has a printable name, even when the admin
            # made the Name field optional.
            proponent.full_name = proponent.user.get_username()

        proponent.save()
        if row_id:
            _register_explicit_role(form, values, proponent, explicit_role_ids)

    missing.extend(_min_rows_missing(form, saved_count))
    return missing, {"explicit_role_ids": explicit_role_ids}


def _register_explicit_role(form, values, proponent, explicit_role_ids):
    """Remember a hand-typed role so automatic role assignment leaves it alone."""
    for field in form.fields.all():
        if field.maps_to != DynamicFormField.MapsTo.ROLE:
            continue
        if (values.get(field.field_key) or "").strip():
            explicit_role_ids.add(proponent.id)


def _save_generic_rows(proposal, form, request, user, removed_ids=()):
    fields = _renderable_fields(form)
    row_count = _posted_row_count(form, request)
    post_parent_values = dynamic_parent_values_from_post([form], request)

    removed_ids = set(removed_ids or ())
    response, _ = DynamicFormResponse.objects.get_or_create(
        form=form,
        proposal=proposal,
        defaults={"submitted_by": user if getattr(user, "is_authenticated", False) else None},
    )
    existing = {row.id: row for row in response.rows.all()}

    missing = []
    saved_count = len(existing)

    for index in range(row_count):
        row_id = _to_int(request.POST.get(_row_id_input(form, index)))
        if row_id in removed_ids:
            # See _save_proponent_rows: a removed row is still in the POST.
            continue
        values = _row_values(form, request, index, fields)
        row = existing.get(row_id)

        if row is None:
            if not _row_has_content(values):
                continue
            if form.max_rows is not None and saved_count >= form.max_rows:
                missing.append(
                    f"{form.name}: a maximum of {form.max_rows} {form.row_label.lower()} row(s) is allowed."
                )
                continue
            row = DynamicFormRow(response=response, row_index=saved_count + 1)
            saved_count += 1

        missing.extend(
            _row_missing_labels(form, index, values, fields, _fallback_parent(post_parent_values))
        )

        data = dict(row.data or {})
        for field in fields:
            data[field.field_key] = values.get(field.field_key, "")
        row.data = data
        row.row_index = index + 1
        row.save()

    missing.extend(_min_rows_missing(form, saved_count))
    return missing, {}


def _fallback_parent(parent_values):
    """Value used when a dependency's parent is not a field of the same row."""
    return parent_values if parent_values else DEPENDENCY_PARENT_NOT_FOUND


# ---------------------------------------------------------------------------
# Missing-requirement checks against *saved* data
# ---------------------------------------------------------------------------

def repeater_missing(proposal, form):
    """Required-problem labels for a repeater, read from saved data.

    Used by step completion and the submission gate, so a required row can
    never be skipped by never opening the step again.
    """
    if not form.is_repeater:
        return []

    fields = _renderable_fields(form)
    saved_parent_values = dynamic_parent_values_from_saved(proposal)
    missing = []

    if form.row_store == form.RowStore.PROPONENT:
        rows = list(proposal.proponents.all())
        for index, proponent in enumerate(rows):
            values = _proponent_row_values(proponent, fields)
            missing.extend(
                _row_missing_labels(form, index, values, fields, _fallback_parent(saved_parent_values))
            )
        count = len(rows)
    else:
        response = DynamicFormResponse.objects.filter(form=form, proposal=proposal).first()
        rows = list(response.rows.all()) if response else []
        for index, row in enumerate(rows):
            values = _generic_row_values(row, fields)
            missing.extend(
                _row_missing_labels(form, index, values, fields, _fallback_parent(saved_parent_values))
            )
        count = len(rows)

    missing.extend(_min_rows_missing(form, count))
    return missing


# ---------------------------------------------------------------------------
# Small parsing helpers
# ---------------------------------------------------------------------------

def _int_list(values):
    parsed = []
    for value in values or []:
        number = _to_int(value, None)
        if number is not None:
            parsed.append(number)
    return parsed
