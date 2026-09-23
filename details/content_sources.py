"""
The content-source registry: one catalogue of every no-code builder that a
public page can display.

Why this exists
---------------
A "content source" is a body of admin-managed data that already has its own
builder screen — Extension Thrust cards, Personnel, Activities, Processes,
Targets, the SDGs, and the Template Library. Before this module
each of those was described in four unrelated places:

  1. ``PageSection.Layout``            - the stored layout code
  2. ``resolve_section_data``          - an if/elif chain of querysets
  3. ``details/_page_section.html``    - an if/elif chain of markup
  4. ``accounts.views.cms``            - hardcoded per-page "linked data" dicts

Adding a builder meant editing all four, and forgetting one produced exactly
the failure this registry was written to end: a section that exists, holds
data, and renders nothing.

Now each source is declared once, here, and everything else reads from it:

  * the **block palette** in the page editor (drag a builder onto a page)
  * the **public renderer** (``block_template``)
  * the **nested editor** shown inside that section (``editor_template``)
  * the **query** that feeds the block (``resolve``)
  * the **"manage" link** to the standalone builder (``manager_url_name``)
  * the **drag-to-reorder** endpoint (``order_model``)

The registry keys are the ``PageSection.Layout`` values, so a section's layout
*is* the name of the source bound to it. Dropping a builder onto a page
creates a section with that layout; the data follows automatically, and lives
in exactly one place — the builder's own table.

Imports of ``details.models`` are deliberately deferred into the resolvers:
``models`` imports this module to derive its data layouts, so a module-level
import would be circular.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple


@dataclass(frozen=True)
class ContentSource:
    """One draggable no-code builder that a page section can display."""

    #: Matches the ``PageSection.Layout`` value that binds a section to it.
    key: str
    #: Name shown in the block palette and the section badge.
    label: str
    #: One line explaining what the block puts on the page.
    description: str
    #: Template rendering the block on a public page.
    block_template: str
    #: Callable ``(section) -> dict`` returning the block's context.
    resolve: Callable
    #: Standalone builder screen for this data, if it has one.
    manager_url_name: str = ""
    #: Nested CRUD partial shown inside the section in the page editor.
    editor_template: str = ""
    #: ``"app_label.ModelName"`` when the items carry an ``order`` column and
    #: can therefore be dragged into sequence inside their section.
    order_model: str = ""
    #: ``PageSection`` option fields that apply to this source, so the section
    #: form can show only the settings that mean something here.
    options: Tuple[str, ...] = field(default_factory=tuple)
    #: Heroicon-style path data for the palette tile.
    icon_path: str = ""

    @property
    def is_orderable(self):
        return bool(self.order_model)

    @property
    def has_editor(self):
        return bool(self.editor_template)


# ==============================================================
# RESOLVERS — the query behind each block
#
# Every resolver returns the context its block template renders. They are the
# single definition of "what this source shows", shared by the public pages,
# the admin preview, and the nested editors.
# ==============================================================


def _resolve_thrust(section):
    from .models import HomeThrust

    return {"thrusts": HomeThrust.objects.filter(is_visible=True)}


def _resolve_sdg(section):
    from .models import SustainableDevelopmentGoal

    return {"goals": SustainableDevelopmentGoal.objects.filter(is_visible=True)}


def _resolve_activities(section):
    from django.db.models import Max, Min

    from .models import Activity

    qs = (
        Activity.objects.prefetch_related("dates")
        .annotate(first_date=Min("dates__date"), last_date=Max("dates__date"))
        .order_by("-last_date", "-id")
    )
    if section.limit_count:
        qs = qs[: int(section.limit_count)]
    return {"activities": qs}


def _resolve_targets(section):
    from django.db.models import Sum
    from django.utils import timezone

    from .models import Target

    year = section.target_year or (
        Target.objects.order_by("-year").values_list("year", flat=True).first()
        or timezone.now().year
    )
    rows = Target.objects.filter(year=year).order_by("campus", "metric")

    def _progress(target):
        if not target.planned_total:
            return None
        return round(100 * target.actual_total / target.planned_total)

    by_campus = OrderedDict()
    for row in rows:
        by_campus.setdefault(row.campus, []).append({
            "label": row.get_metric_display(),
            "planned": row.planned_total,
            "actual": row.actual_total,
            "progress": _progress(row),
        })

    overall = {}
    for key, label in Target.METRIC_CHOICES:
        sums = rows.filter(metric=key).aggregate(
            planned=Sum("planned_total"), actual=Sum("actual_total")
        )
        planned = sums["planned"] or 0
        actual = sums["actual"] or 0
        overall[key] = {
            "label": label,
            "planned": planned,
            "actual": actual,
            "progress": round(100 * actual / planned) if planned else None,
        }

    return {"year": year, "by_campus": by_campus, "overall": overall}


def _resolve_processes(section):
    from .models import ExtensionProcess

    return {
        "processes": ExtensionProcess.objects.all()
        .prefetch_related("steps")
        .order_by("order", "id"),
    }


def _resolve_templates(section):
    from .models import DocumentTemplate

    return {
        "templates": DocumentTemplate.objects.filter(is_active=True).order_by(
            "category", "title"
        ),
    }


def _resolve_personnel(section):
    from .models import Personnel

    qs = Personnel.objects.all().order_by("pk")
    if section.limit_count:
        qs = qs[: int(section.limit_count)]
    return {"personnel": qs}


# ==============================================================
# THE REGISTRY
# ==============================================================

_SOURCES = (
    ContentSource(
        key="THRUST",
        label="Extension Thrust cards",
        description="The thrust cards maintained in the Extension Thrust builder.",
        block_template="details/blocks/thrust.html",
        resolve=_resolve_thrust,
        manager_url_name="home_sections_manager",
        editor_template="dashboard/admin/_home_inline_thrusts.html",
        order_model="details.HomeThrust",
        icon_path="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
    ),
    ContentSource(
        key="PROCESSES",
        label="Extension Processes",
        description="Every process and its numbered steps, from the Process Builder.",
        block_template="details/blocks/processes.html",
        resolve=_resolve_processes,
        manager_url_name="processes_list",
        editor_template="dashboard/admin/_home_inline_processes.html",
        order_model="details.ExtensionProcess",
        icon_path="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01",
    ),
    ContentSource(
        key="TARGETS",
        label="Extension Targets",
        description="Planned vs. actual figures for a year, by campus.",
        block_template="details/blocks/targets.html",
        resolve=_resolve_targets,
        manager_url_name="targets_list",
        editor_template="dashboard/admin/_home_inline_targets.html",
        options=("target_year",),
        icon_path="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    ),
    ContentSource(
        key="PERSONNEL",
        label="Extension Personnel",
        description="Photos, names, and positions of the extension team.",
        block_template="details/blocks/personnel.html",
        resolve=_resolve_personnel,
        manager_url_name="personnel_list",
        editor_template="dashboard/admin/_home_inline_personnel.html",
        options=("limit_count",),
        icon_path="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
    ),
    ContentSource(
        key="SDG",
        label="Sustainable Development Goals",
        description="The SDG cards, each with its own artwork and label.",
        block_template="details/blocks/sdg.html",
        resolve=_resolve_sdg,
        manager_url_name="sdg_goals_manager",
        editor_template="dashboard/admin/_inline_sdgs.html",
        order_model="details.SustainableDevelopmentGoal",
        icon_path="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    ),
    ContentSource(
        key="ACTIVITIES",
        label="Extension Activities",
        description="Activity cards with their dates and cover images.",
        block_template="details/blocks/activities.html",
        resolve=_resolve_activities,
        manager_url_name="activities_list",
        editor_template="dashboard/admin/_home_inline_activities.html",
        options=("limit_count",),
        icon_path="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
    ),
    ContentSource(
        key="TEMPLATES",
        label="Template Library",
        description="Downloadable office templates published in the Template Library.",
        block_template="details/blocks/templates.html",
        resolve=_resolve_templates,
        manager_url_name="document_templates_list",
        editor_template="dashboard/admin/_inline_document_templates.html",
        icon_path="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2",
    ),
)

CONTENT_SOURCES = OrderedDict((source.key, source) for source in _SOURCES)

#: Layout codes backed by a registered source. ``PageSection.DATA_LAYOUTS``
#: is derived from this, so a source is never half-registered.
DATA_LAYOUT_KEYS = tuple(CONTENT_SOURCES)


def get_content_source(key):
    """The source bound to a layout code, or ``None`` for a text layout."""
    return CONTENT_SOURCES.get(key or "")


def all_content_sources():
    """Every registered source, in palette order."""
    return list(CONTENT_SOURCES.values())


def orderable_source(key):
    """A source whose items can be dragged into sequence, or ``None``."""
    source = get_content_source(key)
    return source if source and source.is_orderable else None


def resolve_order_model(source):
    """Return the Django model class whose rows ``source`` orders."""
    from django.apps import apps

    app_label, model_name = source.order_model.split(".", 1)
    return apps.get_model(app_label, model_name)
