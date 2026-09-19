"""
Ordered, admin-owned wizard steps — the piece both wizards share.

A wizard is no longer "steps 1..N of a fixed list". It is a table of
:class:`~details.models.BaseWizardStepConfig` rows the office edits, plus a
registry of built-in parts those rows may point at. This module is the only
place that reads that table, so ordering, visibility, requiredness, and
"which part renders here" resolve the same way everywhere: the wizard view,
the sidebar stepper, the progress bar, the submission gate, and the admin
screens.

Two flows are built at the bottom of the file — ``proposal_flow`` and
``moa_flow`` — because the two wizards have different models and different
registries but identical navigation rules.
"""

from django.db.models import Max


class StepFlow:
    """Navigation and seeding rules for one admin-editable wizard."""

    def __init__(self, *, model, defaults, sections, fallback_template, label):
        self.model = model
        #: Seed rows: ``{"step_no", "section_key", "title", "description"}``.
        self.defaults = defaults
        #: ``{section_key: section}`` registry for this wizard's built-in parts.
        self.sections = sections
        #: Rendered when a step has no built-in part (office-built forms only).
        self.fallback_template = fallback_template
        self.label = label

    # -- seeding ----------------------------------------------------------

    def ensure_defaults(self):
        """Create any missing default rows and give unordered rows a position.

        Safe to call on every request: it never renames, reorders, hides, or
        re-points a step the office has already touched. Rows keep
        ``order == 0`` only until this runs once, so the backfill is a no-op
        afterwards.
        """
        existing = {row.step_no: row for row in self.model.objects.all()}

        to_create = []
        for index, spec in enumerate(self.defaults, start=1):
            if spec["step_no"] in existing:
                continue
            to_create.append(
                self.model(
                    step_no=spec["step_no"],
                    order=index,
                    section_key=spec.get("section_key", ""),
                    title=spec["title"],
                    description=spec.get("description", ""),
                    is_visible=True,
                    is_required=True,
                )
            )
        if to_create:
            self.model.objects.bulk_create(to_create)
            existing = {row.step_no: row for row in self.model.objects.all()}

        unordered = [row for row in existing.values() if not row.order]
        if unordered:
            for row in unordered:
                row.order = row.step_no
            self.model.objects.bulk_update(unordered, ["order"])

        return existing

    def next_step_no(self):
        """First free step number for a new row."""
        highest = self.model.objects.aggregate(highest=Max("step_no"))["highest"] or 0
        return highest + 1

    def next_order(self):
        highest = self.model.objects.aggregate(highest=Max("order"))["highest"] or 0
        return highest + 1

    # -- reading ----------------------------------------------------------

    def ordered(self):
        """Every step, in the order the office put them in."""
        rows = list(self.model.objects.all())
        rows.sort(key=lambda row: (row.order or row.step_no, row.step_no))
        return rows

    def visible(self):
        return [row for row in self.ordered() if row.is_visible]

    def visible_step_nos(self):
        return [row.step_no for row in self.visible()] or [self.first_step_no()]

    def required_step_nos(self):
        return [row.step_no for row in self.visible() if row.is_required]

    def first_step_no(self):
        rows = self.ordered()
        return rows[0].step_no if rows else 1

    def config_map(self):
        return {row.step_no: row for row in self.ordered()}

    def get(self, step_no):
        return self.model.objects.filter(step_no=step_no).first()

    def default_section_key(self, step_no):
        """Part a fresh install puts on ``step_no``, before any row exists."""
        for spec in self.defaults:
            if spec["step_no"] == step_no:
                return spec.get("section_key", "")
        return ""

    def section(self, step_no):
        """The built-in part on this step, or ``None`` for a custom step.

        A step with no row at all (an unseeded database, or a helper called
        outside the view) falls back to the default part for that number, so
        the wizard still behaves like the shipped one.
        """
        config = self.get(step_no)
        key = config.section_key if config is not None else self.default_section_key(step_no)
        return self.sections.get(key or "")

    def template_for(self, step_no):
        """Template that renders this step.

        A step with a built-in part renders that part's template; a step with
        none renders the generic shell driven by the office's own forms.
        """
        section = self.section(step_no)
        if section is not None:
            return section.template
        return self.fallback_template

    def normalize(self, step_no):
        """Snap a requested step onto a step that actually shows."""
        visible = self.visible_step_nos()
        if step_no in visible:
            return step_no
        for number in visible:
            if number > step_no:
                return number
        return visible[-1]

    def step_after(self, step_no):
        """The next visible step, by *position* — not the next higher number.

        The numbers can run 1, 2, 11, 10, 3 once the office starts moving
        things around, so "the step after 11" has to come from the ordered
        list. A number that is not showing (a stale link, a hidden step)
        snaps forward to the next one the wizard would show.
        """
        visible = self.visible_step_nos()
        if step_no not in visible:
            return self.normalize(step_no)
        index = visible.index(step_no)
        return visible[index + 1] if index + 1 < len(visible) else None

    def step_before(self, step_no):
        """The previous visible step, by position. See :meth:`step_after`."""
        visible = self.visible_step_nos()
        if step_no not in visible:
            earlier = [number for number in visible if number < step_no]
            return earlier[-1] if earlier else None
        index = visible.index(step_no)
        return visible[index - 1] if index > 0 else None

    def total_visible(self):
        return len(self.visible()) or 1

    def position(self, step_no):
        """1-based position of ``step_no`` among the visible steps."""
        for index, number in enumerate(self.visible_step_nos(), start=1):
            if number == step_no:
                return index
        return 1

    def step_labels(self):
        """``[{"no", "title", "desc"}]`` for every step, visible or not."""
        return [
            {"no": row.step_no, "title": row.title, "desc": row.description}
            for row in self.ordered()
        ]

    def build_steps(self, current_step, *, state_for):
        """Sidebar/stepper entries, ordered and annotated with a state."""
        steps = []
        for index, row in enumerate(self.visible(), start=1):
            steps.append({
                "no": row.step_no,
                "position": index,
                "title": row.title,
                "desc": row.description,
                "is_required": row.is_required,
                "section_key": row.section_key,
                "state": state_for(row, current_step),
            })
        return steps

    # -- writing ----------------------------------------------------------

    def move(self, step_no, direction):
        """Swap a step with its neighbour. Returns True when it moved.

        Only ``order`` changes, so anything stored against ``step_no`` — saved
        progress, reviewer comments, editor presence, attached forms — keeps
        pointing at the same step.
        """
        rows = self.ordered()
        index = next((i for i, row in enumerate(rows) if row.step_no == step_no), None)
        if index is None:
            return False

        target = index + 1 if direction == "down" else index - 1
        if target < 0 or target >= len(rows):
            return False

        first, second = rows[index], rows[target]
        first.order, second.order = (second.order or second.step_no), (first.order or first.step_no)
        if first.order == second.order:
            # Ties (both unseeded) would make the swap a no-op: break the tie
            # by their step numbers so the move is still visible.
            first.order, second.order = sorted(
                [first.step_no, second.step_no], reverse=(direction == "up")
            )
        self.model.objects.bulk_update([first, second], ["order"])
        return True
