"""Undo for administrative deletions.

Deleting a row from an admin list is one click, so it needs a way back. Before
anything goes, ``remember()`` snapshots the row **and everything a database
cascade would take with it** — a campus's colleges and departments, a process's
steps, an activity's dates — into the user's session. ``restore()`` writes them
back with their original primary keys, so rows that pointed at them line up
again instead of becoming orphans.

Why the session rather than a "recycle bin" table:

* the snapshot is per user and dies with the session or after
  ``UNDO_LIFETIME``, which is exactly the window in which "undo" means
  something;
* no new model, no migration, and no second source of truth that could drift
  from the real tables;
* nothing to clean up in a background job.

The cost is that undo does not survive signing out, so it is a safety net for a
mis-click, not a retention policy. Deletions whose blast radius cannot be
captured this way — a file removed from object storage, an account, a proposal
that has accumulated review history — keep their confirmation prompt and are
never routed through here.

Django's own serializer does the encoding, which is what keeps this small: it
already knows how to represent dates, decimals, images (by storage path),
foreign keys (by id) and many-to-many relations. ``MAX_ROWS`` stops one
careless delete from stuffing a megabyte of JSON into a session row.
"""

from __future__ import annotations

import json
import time
from uuid import uuid4

from django.apps import apps
from django.core import serializers
from django.db import models, transaction

#: Where the pending snapshots live in the session.
UNDO_SESSION_KEY = "nx_undo"

#: How long an undo stays available, in seconds. Long enough to notice the row
#: is gone and read the message; short enough that sessions stay small.
UNDO_LIFETIME = 900

#: How many deletions can be undone at once — the newest win.
UNDO_LIMIT = 5

#: A cascade bigger than this is deleted without an undo offer. The session is
#: not the place for a page-sized fixture, and a record that large is one the
#: office should not be deleting from a list screen at all.
MAX_ROWS = 500


def _cascades(field):
    """True when deleting the parent deletes this related row too.

    ``on_delete`` lives on the field's ``remote_field`` in modern Django; the
    direct attribute is only there on very old relations, so both are checked.
    """
    on_delete = getattr(field, "on_delete", None)
    if on_delete is None:
        on_delete = getattr(getattr(field, "remote_field", None), "on_delete", None)
    if on_delete is models.CASCADE:
        return True
    # Custom handlers and wrapped callables keep the name.
    return getattr(on_delete, "__name__", "") == "CASCADE"


def _related_rows(parent):
    """Every row a database cascade would delete along with ``parent``."""
    for relation in parent._meta.related_objects:
        if not _cascades(relation.field):
            # SET_NULL leaves the child behind, PROTECT refuses the delete and
            # DO_NOTHING orphans it; in none of those cases does putting the
            # world back need a snapshot.
            continue
        try:
            related = getattr(parent, relation.get_accessor_name())
        except Exception:  # noqa: BLE001 - an unset reverse relation is normal
            continue
        if relation.multiple:
            try:
                yield from related.all()
            except Exception:  # noqa: BLE001
                continue
        else:
            try:
                yield related
            except Exception:  # noqa: BLE001 - reverse one-to-one is unset
                continue


def cascade(objects):
    """``objects`` plus everything a delete would cascade to, parents first.

    Breadth-first on purpose: a parent has to exist before its children can be
    written back, and the serializer replays the list in that order.
    """
    collected = []
    seen = set()
    queue = list(objects)

    while queue:
        current = queue.pop(0)
        identity = (current._meta.label_lower, current.pk)
        if identity in seen:
            continue
        seen.add(identity)
        collected.append(current)
        queue.extend(_related_rows(current))

    return collected


def _stamped_fields(obj):
    """Fields the database stamps on insert, so the snapshot's value is lost."""
    return [
        field.attname
        for field in obj._meta.local_concrete_fields
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    ]


def _snapshot(objects):
    """Serialize ``objects``; note which timestamp fields must be pinned back."""
    data = serializers.serialize("json", objects)
    stamped = {}
    for obj in objects:
        names = _stamped_fields(obj)
        if names:
            stamped.setdefault(obj._meta.label_lower, names)
    return data, stamped


def _restore(data, stamped):
    """Write a snapshot back. Returns the number of rows restored."""
    entries = json.loads(data)
    restored = 0

    with transaction.atomic():
        for entry in entries:
            for deserialized in serializers.deserialize("json", json.dumps([entry])):
                deserialized.save()
                restored += 1

        # The rows exist again; put the insertion timestamps back where the
        # snapshot had them, so "last updated" does not claim the undo was an
        # edit made today.
        for entry in entries:
            names = stamped.get(entry.get("model", ""), [])
            if not names:
                continue
            model = _model_for_label(entry.get("model", ""))
            if model is None:
                continue
            updates = {}
            fields = entry.get("fields") or {}
            for name in names:
                if name not in fields:
                    continue
                try:
                    field = model._meta.get_field(name)
                    updates[name] = field.to_python(fields[name])
                except Exception:  # noqa: BLE001 - a bad timestamp is cosmetic
                    continue
            if updates:
                model._base_manager.filter(pk=entry.get("pk")).update(**updates)

    return restored


def _model_for_label(label):
    try:
        return apps.get_model(label)
    except (LookupError, ValueError):
        return None


def _session(target):
    """The session to read, given a request or a session object directly."""
    return getattr(target, "session", target)


def _load(target):
    stored = _session(target).get(UNDO_SESSION_KEY) or []
    return [entry for entry in stored if isinstance(entry, dict)]


def _prune(entries, *, now=None):
    """Drop expired entries. Returns ``(kept, changed)``."""
    if not entries:
        return [], False
    now = time.time() if now is None else now
    kept = [entry for entry in entries if now - entry.get("created", 0) < UNDO_LIFETIME]
    changed = len(kept) != len(entries)
    if len(kept) > UNDO_LIMIT:
        kept = kept[-UNDO_LIMIT:]
        changed = True
    return kept, changed


def _store(target, entries):
    session = _session(target)
    if entries:
        session[UNDO_SESSION_KEY] = entries
    else:
        session.pop(UNDO_SESSION_KEY, None)
    session.modified = True


def remember(request, obj, label, *related):
    """Snapshot ``obj`` (and its cascade) so the caller may now delete it.

    Returns the undo token, or ``None`` when no undo is offered — an oversized
    cascade, a model the serializer cannot handle, or a session that cannot
    hold it. Callers must treat ``None`` as "this one is final" and keep the
    user informed accordingly.
    """
    objects = cascade([obj, *related])

    if len(objects) > MAX_ROWS:
        return None

    try:
        data, stamped = _snapshot(objects)
    except Exception:  # noqa: BLE001 - never block a delete on the undo net
        return None

    entries, _ = _prune(_load(request))
    token = uuid4().hex
    entries.append(
        {
            "token": token,
            "label": str(label),
            "model": obj._meta.label_lower,
            "pk": obj.pk,
            "count": len(objects),
            "created": time.time(),
            "data": data,
            "stamped": stamped,
        }
    )
    _store(request, entries[-UNDO_LIMIT:])
    return token


def undo_hint(token):
    """What to add to the success message. Empty when no undo was offered."""
    return " You can undo this below." if token else ""


def pending(request):
    """The deletions this session can still undo, newest last."""
    entries, changed = _prune(_load(request))
    if changed:
        _store(request, entries)
    return [
        {
            "token": entry["token"],
            "label": entry.get("label", ""),
            "count": entry.get("count", 1),
            "seconds_left": max(0, int(UNDO_LIFETIME - (time.time() - entry.get("created", 0)))),
        }
        for entry in entries
    ]


def take(request, token):
    """Remove and return one entry without restoring it.

    Expired entries are pruned first: a token that is past its deadline must
    not restore anything even if the client kept the form on screen.
    """
    entries, changed = _prune(_load(request))
    if changed:
        _store(request, entries)
    for index, entry in enumerate(entries):
        if entry.get("token") == token:
            removed = entries.pop(index)
            _store(request, entries)
            return removed
    return None


def restore(request, token):
    """Put a deleted record back. Returns ``(label, rows)`` or ``None``."""
    entry = take(request, token)
    if entry is None:
        return None
    try:
        rows = _restore(entry.get("data", "[]"), entry.get("stamped") or {})
    except Exception:  # noqa: BLE001
        # The snapshot is unusable; say so rather than pretending it worked.
        return None
    return entry.get("label", ""), rows


def dismiss(request, token):
    """Forget one pending undo without restoring it."""
    return take(request, token) is not None
