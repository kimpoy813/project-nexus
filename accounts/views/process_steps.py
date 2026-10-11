"""
Saving nested Extension Process steps.

Both process editors -- the standalone one under /admin/processes/ and the
inline one inside the Home page builder -- post the same shape of data, so the
structure is parsed and written in one place.

The posted rows describe an *outline*: they arrive in document order and each
row names its parent by reference. A reference is ``s<pk>`` for a step that
already exists and ``n<counter>`` for one the editor just added, which is how a
brand-new sub-step can point at a brand-new parent the server has not saved
yet. Rows without any reference at all (hand-written or legacy posts) still
work and are treated as a flat list.
"""

from django.db import transaction

from details.models import ProcessStep

REF_PREFIX_EXISTING = "s"


def _padded(values, size, fill=""):
    return list(values) + [fill] * (size - len(values))


def _parse_step_rows(post):
    """Turn a POST body into ordered row dictionaries.

    Returns a list of ``{"ref", "id", "description", "parent_ref"}`` in the
    order the editor showed them. Blank descriptions are dropped, and a row
    whose parent disappeared is re-hung on its nearest surviving ancestor so
    nesting is never silently flattened by one empty field.
    """
    refs = post.getlist("step_ref[]")
    ids = post.getlist("step_id[]")
    descriptions = post.getlist("step_description[]")
    parents = post.getlist("step_parent[]")

    size = max(len(refs), len(ids), len(descriptions), len(parents), 0)
    refs = _padded(refs, size)
    ids = _padded(ids, size)
    descriptions = _padded(descriptions, size)
    parents = _padded(parents, size)

    posted = []          # every row the editor drew, blank ones included
    by_ref = {}          # ref -> row, used to follow parent links
    kept = set()         # refs whose description survived

    for index in range(size):
        raw_ref = (refs[index] or "").strip()
        if not raw_ref:
            step_id = str(ids[index] or "").strip()
            raw_ref = (
                f"{REF_PREFIX_EXISTING}{step_id}" if step_id.isdigit() else f"auto-{index}"
            )

        ref = raw_ref
        suffix = 1
        while ref in by_ref:
            suffix += 1
            ref = f"{raw_ref}-{suffix}"

        description = (descriptions[index] or "").strip()
        row = {
            "ref": ref,
            "id": str(ids[index] or "").strip(),
            "description": description,
            "parent_ref": (parents[index] or "").strip(),
        }
        by_ref[ref] = row
        posted.append(row)
        if description:
            kept.add(ref)

    def surviving_ancestor(parent_ref):
        """Nearest posted ancestor that was kept, or "" for top level."""
        seen = set()
        candidate = parent_ref
        while candidate and candidate not in seen:
            seen.add(candidate)
            if candidate in kept:
                return candidate
            candidate = by_ref.get(candidate, {}).get("parent_ref", "")
        return ""

    rows = []
    for row in posted:
        if row["ref"] not in kept:
            continue
        row["parent_ref"] = surviving_ancestor(row["parent_ref"])
        rows.append(row)

    return rows


def _document_order(rows):
    """Depth-first walk of the posted rows, so parents precede their children."""
    children = {}
    for row in rows:
        children.setdefault(row["parent_ref"] or "", []).append(row)

    ordered = []
    visited = set()

    def walk(parent_ref):
        for row in children.get(parent_ref, []):
            if row["ref"] in visited:
                continue
            visited.add(row["ref"])
            ordered.append(row)
            walk(row["ref"])

    walk("")
    # A cycle can only come from a hand-crafted post; surface the row rather
    # than losing it.
    for row in rows:
        if row["ref"] not in visited:
            row["parent_ref"] = ""
            ordered.append(row)
    return ordered


@transaction.atomic
def _sync_process_steps(process, post):
    """Replace a process's steps with the posted outline.

    Existing steps are updated in place, new ones are created parents-first,
    and anything the editor no longer lists is deleted (its sub-steps go with
    it). The stored ``order`` is the depth-first document order, which is what
    the public block and both editors read back.
    """
    rows = _parse_step_rows(post)
    ordered = _document_order(rows)

    existing = {str(step.id): step for step in process.steps.all()}
    saved = {}

    # First pass: rows that already have a step, then new rows whose parent
    # needs no creating.
    pending = []
    for row in ordered:
        step = existing.get(row["id"]) if row["id"] else None
        if step is not None:
            if step.description != row["description"]:
                step.description = row["description"]
                step.save(update_fields=["description"])
            saved[row["ref"]] = step
        else:
            pending.append(row)

    # Later passes: create the rest once the step they sit under exists.
    while pending:
        deferred = []
        progressed = False
        for row in pending:
            parent_ref = row["parent_ref"]
            if parent_ref and parent_ref not in saved:
                deferred.append(row)
                continue
            step = ProcessStep.objects.create(
                process=process,
                description=row["description"],
                parent=saved.get(parent_ref) if parent_ref else None,
            )
            saved[row["ref"]] = step
            progressed = True
        if not progressed:
            # Only reachable with a reference cycle: keep the text by parking
            # the leftovers at the top level.
            for row in deferred:
                saved[row["ref"]] = ProcessStep.objects.create(
                    process=process, description=row["description"]
                )
            break
        pending = deferred

    keep_ids = {step.pk for step in saved.values()}
    # Detach the survivors before deleting anything: a step is removed with
    # CASCADE, and a kept sub-step still pointing at a deleted parent would go
    # with it. The loop below rewrites every parent link anyway.
    ProcessStep.objects.filter(process=process, pk__in=keep_ids).exclude(
        parent__isnull=True
    ).update(parent=None)
    process.steps.exclude(pk__in=keep_ids).delete()

    # Parent links and document order are written last, once every step the
    # outline mentions has a row of its own.
    for index, row in enumerate(ordered, start=1):
        step = saved[row["ref"]]
        step.parent = saved.get(row["parent_ref"]) if row["parent_ref"] else None
        step.order = index
        step.save(update_fields=["parent", "order"])

    return process
