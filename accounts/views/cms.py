"""
Admin-editable public pages, Home sections, thrust cards, and workflow phases.

Pages are composed by dragging no-code builders ("content sources") onto them.
The catalogue of sources lives in ``details.content_sources``; this module
turns that catalogue into a palette, binds a dropped source to a section, and
keeps both the section order and each source's own item order draggable.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Min
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from details.content_sources import (
    DATA_LAYOUT_KEYS,
    all_content_sources,
    get_content_source,
    orderable_source,
    resolve_order_model,
)
from details.models import Activity
from details.models import ActivityDate
from details.models import ExtensionProcess
from details.models import HomeSectionHeading
from details.models import HomeThrust
from details.models import PageContentLog
from details.models import PageSection
from details.models import Personnel
from details.models import ProcessStep
from details.models import SitePage
from details.models import SustainableDevelopmentGoal
from details.models import Target
from details.models import WorkflowPhase
from details.models import resolve_section_data
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from ..decorators import admin_required
from ..forms import PageSectionForm

PAGE_PUBLIC_URL_NAMES = {
    "home": "details_page",
    "services": "services_home",
    "reports": "reports_page",
    "achievements": "achievements_page",
}


def _palette(page):
    """The draggable no-code builders offered for this page.

    Every registered content source is offered on every page — a builder is
    not owned by one page, it is a body of data any page may display. Sources
    already placed are marked so the palette can show that, rather than
    hiding them (a source can legitimately appear twice, e.g. two Activities
    blocks with different limits).
    """
    placed = set(page.sections.values_list("layout", flat=True))
    return [
        {"source": source, "in_use": source.key in placed}
        for source in all_content_sources()
    ]


def _log_content_change(request, page_slug, action, summary, before=None, after=None,
                        section_id=None, target_label=""):
    """Record an admin content edit for the audit trail."""
    PageContentLog.objects.create(
        action=action,
        page_slug=page_slug,
        section_id=section_id,
        target_label=target_label,
        summary=summary[:255],
        before=before or {},
        after=after or {},
        changed_by=request.user,
    )


def _to_positive_int(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _thrust_editor_context():
    """Cards + colour picker for the inline Extension Thrust editor."""
    return {
        "home_thrusts": list(HomeThrust.objects.all().order_by("order", "id")),
        "home_thrust_color_choices": HomeThrust.COLOR_CHOICES,
    }


def _home_inline_data_context():
    """Items for every nested source editor shown in the page editor.

    One context serves all the editors because a page can hold any mix of
    sources; the template only renders the partial each section asks for.
    """
    from details.models import DocumentTemplate, DynamicFormTemplate

    try:
        from accounts.campus_data import get_campus_choices as _get_campus_choices
        campus_choices = [c[0] for c in _get_campus_choices()]
    except Exception:
        campus_choices = []
    personnel = list(Personnel.objects.all().order_by("name"))
    activities = list(
        Activity.objects.prefetch_related("dates")
        .annotate(first_date=Min("dates__date"))
        .order_by("-first_date", "-id")
    )
    processes = list(
        ExtensionProcess.objects.prefetch_related("steps").order_by("order", "id")
    )
    targets = list(Target.objects.all().order_by("-year", "campus", "metric"))
    try:
        years = sorted({t.year for t in targets}, reverse=True) or [2026]
    except Exception:
        years = [2026]
    return {
        "home_personnel": personnel,
        "home_activities": activities,
        "home_processes": processes,
        "home_targets": targets,
        "home_target_years": years,
        "home_campus_choices": campus_choices,
        "home_metric_choices": Target.METRIC_CHOICES,
        "inline_sdgs": list(SustainableDevelopmentGoal.objects.all().order_by("order", "code")),
        "inline_document_templates": list(
            DocumentTemplate.objects.all().order_by("category", "title")
        ),
        "inline_dynamic_forms": list(
            DynamicFormTemplate.objects.prefetch_related("fields").order_by("applies_to", "name")
        ),
    }


def _home_inline_redirect(request):
    """Bounce back to the editor the admin was on, or the Home page editor."""
    candidate = (request.POST.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(candidate)
    return redirect("page_content_edit", slug="home")


def _section_from_params(page, params):
    """Build an unsaved section from editor inputs, for the live preview."""
    layout = params.get("layout") or PageSection.Layout.RICH_TEXT
    if layout not in dict(PageSection.Layout.choices):
        layout = PageSection.Layout.RICH_TEXT

    return PageSection(
        page=page,
        heading=(params.get("heading") or "").strip(),
        subheading=(params.get("subheading") or "").strip(),
        body=params.get("body") or "",
        layout=layout,
        anchor=slugify(params.get("anchor") or "")[:60],
        image=None,
        is_visible=params.get("is_visible") != "off",
        limit_count=_to_positive_int(params.get("limit_count")),
        target_year=_to_positive_int(params.get("target_year")),
        cta_label=(params.get("cta_label") or "").strip(),
        cta_url=(params.get("cta_url") or "").strip(),
    )


@login_required
@admin_required
def page_content_list(request):
    """Overview of every admin-editable public page."""
    pages = []
    for slug, _label in SitePage.Slug.choices:
        page = SitePage.get_for(slug)
        pages.append({
            "page": page,
            "section_count": page.sections.count(),
            "visible_count": page.sections.filter(is_visible=True).count(),
            "public_url_name": PAGE_PUBLIC_URL_NAMES.get(slug),
        })

    recent_logs = list(PageContentLog.objects.select_related("changed_by")[:10])

    return render(request, "dashboard/admin/page_content_list.html", {
        "pages": pages,
        "recent_logs": recent_logs,
    })


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def page_content_edit(request, slug):
    """Edit a page's hero/SEO fields and manage its content sections."""
    if slug not in dict(SitePage.Slug.choices):
        raise Http404("Unknown page.")

    page = SitePage.get_for(slug)

    if request.method == "POST":
        before = page.state()
        page.title = (request.POST.get("title") or "").strip() or page.title
        page.hero_eyebrow = (request.POST.get("hero_eyebrow") or "").strip()
        page.hero_heading = (request.POST.get("hero_heading") or "").strip()
        page.hero_subheading = (request.POST.get("hero_subheading") or "").strip()
        page.meta_title = (request.POST.get("meta_title") or "").strip()
        page.meta_description = (request.POST.get("meta_description") or "").strip()
        page.is_published = request.POST.get("is_published") == "on"
        page.updated_by = request.user
        page.save()

        after = page.state()
        _log_content_change(
            request,
            page.slug,
            PageContentLog.Action.UPDATE_PAGE,
            f'Updated "{page.title}" page header',
            before=before,
            after=after,
            target_label=page.title,
        )
        messages.success(request, f'"{page.title}" page updated successfully.')
        return redirect("page_content_edit", slug=page.slug)

    public_url_name = PAGE_PUBLIC_URL_NAMES.get(slug)
    context = {
        "page": page,
        "sections": page.sections.all(),
        "palette": _palette(page),
        "public_url_name": public_url_name,
        "layout_choices": PageSection.Layout.choices,
        "page_logs": list(
            PageContentLog.objects.filter(page_slug=page.slug)
            .select_related("changed_by")[:8]
        ),
    }
    # Every source's nested editor is available on every page, so a section
    # can be edited wherever it was dropped.
    context.update(_thrust_editor_context())
    context.update(_home_inline_data_context())

    return render(request, "dashboard/admin/page_content_edit.html", context)


@login_required
@admin_required
@require_POST
def page_section_add_source(request, slug):
    """Bind a no-code builder to a new section — the drop half of drag-and-drop.

    The palette posts a source key and the position it was dropped at. The
    section stores only the binding (which source, which options); the items
    themselves stay in the builder's own table, so dropping the same source on
    two pages publishes one body of data twice rather than copying it.
    """
    if slug not in dict(SitePage.Slug.choices):
        raise Http404("Unknown page.")

    page = SitePage.get_for(slug)
    source = get_content_source((request.POST.get("source") or "").strip())
    if source is None:
        messages.error(request, "That content source is not available.")
        return redirect("page_content_edit", slug=page.slug)

    section = PageSection(
        page=page,
        heading=source.label,
        layout=source.key,
        anchor=slugify(source.label)[:60],
        is_visible=True,
        order=0,  # model appends it to the end
    )
    section.save()

    # Honour where it was dropped, when the palette said.
    position = _to_positive_int(request.POST.get("position"))
    if position:
        siblings = [s for s in page.sections.order_by("order", "id") if s.pk != section.pk]
        siblings.insert(min(position - 1, len(siblings)), section)
        _renumber(siblings)

    _log_content_change(
        request,
        page.slug,
        PageContentLog.Action.ADD_SECTION,
        f'Added "{source.label}" section from the block palette',
        after=section.state(),
        section_id=section.pk,
        target_label=section.heading,
    )
    messages.success(
        request,
        f'"{source.label}" added. It shows the same data as the {source.label} builder.',
    )
    return redirect("page_content_edit", slug=page.slug)


def _renumber(sections):
    """Write 1..n into ``order`` for an already-sorted list of sections."""
    for position, item in enumerate(sections, start=1):
        if item.order != position:
            item.order = position
            item.save(update_fields=["order"])


@login_required
@admin_required
@require_POST
def page_sections_reorder(request, slug):
    """Persist a dragged section order for one page.

    The payload is every section id of the page, once, in the new order —
    the same contract the wizard step manager uses, so a stale tab cannot
    reorder a page it no longer matches.
    """
    if slug not in dict(SitePage.Slug.choices):
        raise Http404("Unknown page.")

    page = SitePage.get_for(slug)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        section_ids = [int(value) for value in payload.get("section_ids", [])]
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    existing = list(page.sections.order_by("order", "id").values_list("id", flat=True))
    if not section_ids or sorted(section_ids) != sorted(existing):
        return JsonResponse(
            {"ok": False, "error": "Send every section of this page, once, in the new order."},
            status=400,
        )

    with transaction.atomic():
        for index, section_id in enumerate(section_ids, start=1):
            PageSection.objects.filter(pk=section_id, page=page).update(order=index)

    _log_content_change(
        request,
        page.slug,
        PageContentLog.Action.MOVE_SECTION,
        f"Reordered the {page.title} page sections by drag and drop",
        after={"order": section_ids},
        target_label=page.title,
    )
    return JsonResponse({"ok": True})


@login_required
@admin_required
@require_POST
def content_source_reorder(request, source_key):
    """Persist a dragged item order *inside* a source (thrusts, goals, ...).

    Reordering belongs to the source, not to the page: a goal moved here moves
    on every page that publishes the SDG block, because there is one list.
    Only sources that declare an ``order_model`` accept this.
    """
    source = orderable_source(source_key)
    if source is None:
        return JsonResponse({"ok": False, "error": "This block cannot be reordered."}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        item_ids = [int(value) for value in payload.get("item_ids", [])]
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    model = resolve_order_model(source)
    existing = list(model.objects.values_list("id", flat=True))
    if not item_ids or sorted(item_ids) != sorted(existing):
        return JsonResponse(
            {"ok": False, "error": "Send every item, once, in the new order."},
            status=400,
        )

    with transaction.atomic():
        for index, item_id in enumerate(item_ids, start=1):
            model.objects.filter(pk=item_id).update(order=index)

    return JsonResponse({"ok": True})


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def page_section_create(request, slug):
    if slug not in dict(SitePage.Slug.choices):
        raise Http404("Unknown page.")

    page = SitePage.get_for(slug)

    if request.method == "POST":
        form = PageSectionForm(request.POST, request.FILES)
        if form.is_valid():
            section = form.save(commit=False)
            section.page = page
            section.order = 0  # model assigns the next order on save
            section.save()
            _log_content_change(
                request,
                page.slug,
                PageContentLog.Action.ADD_SECTION,
                f'Added "{section.heading or "untitled"}" section ({section.get_layout_display()})',
                after=section.state(),
                section_id=section.pk,
                target_label=section.heading,
            )
            messages.success(request, "Section added successfully.")
            return redirect("page_content_edit", slug=page.slug)
    else:
        form = PageSectionForm()

    # Live preview from whatever the admin has typed so far (GET params on a
    # fresh form, POSTed values when validation failed).
    params = request.POST if request.method == "POST" else request.GET
    preview_section = _section_from_params(page, params)
    preview_data = (
        resolve_section_data(preview_section) if preview_section.is_data_layout else None
    )

    context = {
        "page": page,
        "form": form,
        "is_create": True,
        "preview_section": preview_section,
        "preview_data": preview_data,
        "data_layout_keys": list(DATA_LAYOUT_KEYS),
    }
    context.update(_thrust_editor_context())
    context.update(_home_inline_data_context())
    return render(request, "dashboard/admin/page_section_form.html", context)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def page_section_edit(request, pk):
    section = get_object_or_404(PageSection.objects.select_related("page"), pk=pk)

    if request.method == "POST":
        before = section.state()
        form = PageSectionForm(request.POST, request.FILES, instance=section)
        if form.is_valid():
            section = form.save(commit=False)
            if request.POST.get("remove_image") == "on":
                section.image = None
            section.save()
            after = section.state()
            _log_content_change(
                request,
                section.page.slug,
                PageContentLog.Action.EDIT_SECTION,
                f'Edited "{section.heading or "untitled"}" section ({section.get_layout_display()})',
                before=before,
                after=after,
                section_id=section.pk,
                target_label=section.heading,
            )
            messages.success(request, "Section updated successfully.")
            return redirect("page_content_edit", slug=section.page.slug)
    else:
        form = PageSectionForm(instance=section)

    preview_data = resolve_section_data(section) if section.is_data_layout else None

    context = {
        "page": section.page,
        "section": section,
        "form": form,
        "is_create": False,
        "preview_section": section,
        "preview_data": preview_data,
        "data_layout_keys": list(DATA_LAYOUT_KEYS),
    }
    context.update(_thrust_editor_context())
    context.update(_home_inline_data_context())
    return render(request, "dashboard/admin/page_section_form.html", context)


@login_required
@admin_required
@require_POST
def page_section_delete(request, pk):
    section = get_object_or_404(PageSection.objects.select_related("page"), pk=pk)
    page_slug = section.page.slug
    before = section.state()
    section.delete()
    _log_content_change(
        request,
        page_slug,
        PageContentLog.Action.DELETE_SECTION,
        f'Deleted "{section.heading or "untitled"}" section ({section.get_layout_display()})',
        before=before,
        section_id=section.pk,
        target_label=section.heading,
    )
    messages.success(request, "Section deleted.")
    return redirect("page_content_edit", slug=page_slug)


@login_required
@admin_required
@require_POST
def page_section_move(request, pk):
    """Move a section one place up or down.

    Drag-and-drop is the normal way to reorder (see ``page_sections_reorder``);
    this endpoint is what the drag handle's Arrow-key shortcuts post to, so the
    same reordering works without a pointer and without JavaScript.
    """
    section = get_object_or_404(PageSection.objects.select_related("page"), pk=pk)
    direction = request.POST.get("direction")

    siblings = list(PageSection.objects.filter(page=section.page).order_by("order", "id"))
    index = next((i for i, s in enumerate(siblings) if s.pk == section.pk), None)

    if index is not None:
        target = None
        if direction == "up" and index > 0:
            target = index - 1
        elif direction == "down" and index < len(siblings) - 1:
            target = index + 1

        if target is not None:
            before_position = index + 1
            siblings.insert(target, siblings.pop(index))
            _renumber(siblings)
            section.refresh_from_db()

            _log_content_change(
                request,
                section.page.slug,
                PageContentLog.Action.MOVE_SECTION,
                f'Moved "{section.heading or "untitled"}" {direction} '
                f"(position {before_position} \u2192 {section.order})",
                section_id=section.pk,
                target_label=section.heading,
            )

    return redirect("page_content_edit", slug=section.page.slug)


# ==============================================================
# SDG GOALS - the source behind the SDG block
# ==============================================================


@login_required
@admin_required
def sdg_goals_manager(request):
    """Standalone builder for the SDG cards."""
    return render(request, "dashboard/admin/sdg_goals_list.html", {
        "goals": SustainableDevelopmentGoal.objects.all().order_by("order", "code"),
    })


@login_required
@admin_required
@require_POST
def sdg_goal_create(request):
    code = (request.POST.get("code") or "").strip()
    title = (request.POST.get("title") or "").strip()
    if not code or not title:
        messages.error(request, "A goal needs both a code and a title.")
        return _home_inline_redirect(request)
    if SustainableDevelopmentGoal.objects.filter(code=code).exists():
        messages.error(request, f"SDG {code} already exists.")
        return _home_inline_redirect(request)
    SustainableDevelopmentGoal.objects.create(
        code=code,
        title=title,
        summary=(request.POST.get("summary") or "").strip(),
        image=request.FILES.get("image"),
        is_visible=request.POST.get("is_visible") == "on",
        order=0,
    )
    messages.success(request, f'SDG {code} "{title}" added.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def sdg_goal_update(request, pk):
    goal = get_object_or_404(SustainableDevelopmentGoal, pk=pk)
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "A goal title is required.")
        return _home_inline_redirect(request)
    goal.title = title
    goal.summary = (request.POST.get("summary") or "").strip()
    goal.is_visible = request.POST.get("is_visible") == "on"
    if request.FILES.get("image"):
        goal.image = request.FILES["image"]
    elif request.POST.get("remove_image") == "on":
        goal.image = None
    goal.save()
    messages.success(request, f"SDG {goal.code} updated.")
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def sdg_goal_delete(request, pk):
    goal = get_object_or_404(SustainableDevelopmentGoal, pk=pk)
    label = f"SDG {goal.code}"
    goal.delete()
    messages.success(request, f"{label} deleted.")
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_sections_manager(request):
    """Manage the Extension Thrust cards shown on the Home page."""
    thrusts = HomeThrust.objects.all()

    return render(request, "dashboard/admin/home_thrusts_list.html", {
        "thrusts": thrusts,
    })


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_thrust_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "A title is required.")
        else:
            HomeThrust.objects.create(
                title=title,
                description=(request.POST.get("description") or "").strip(),
                color_class=_valid_thrust_color(request.POST.get("color_class")),
                is_visible=request.POST.get("is_visible") == "on",
                order=0,  # model assigns the next order
            )
            messages.success(request, f'Thrust "{title}" added successfully.')
            return redirect("home_sections_manager")

    return render(request, "dashboard/admin/home_thrust_form.html", {
        "color_choices": HomeThrust.COLOR_CHOICES,
        "is_create": True,
    })


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_thrust_edit(request, pk):
    thrust = get_object_or_404(HomeThrust, pk=pk)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "A title is required.")
        else:
            thrust.title = title
            thrust.description = (request.POST.get("description") or "").strip()
            thrust.color_class = _valid_thrust_color(request.POST.get("color_class"))
            thrust.is_visible = request.POST.get("is_visible") == "on"
            thrust.save()
            messages.success(request, "Thrust updated successfully.")
            return redirect("home_sections_manager")

    return render(request, "dashboard/admin/home_thrust_form.html", {
        "thrust": thrust,
        "color_choices": HomeThrust.COLOR_CHOICES,
        "is_create": False,
    })


@login_required
@admin_required
@require_POST
def home_thrust_delete(request, pk):
    thrust = get_object_or_404(HomeThrust, pk=pk)
    title = thrust.title
    thrust.delete()
    messages.success(request, f'Thrust "{title}" deleted.')
    return redirect("home_sections_manager")


@login_required
@admin_required
@require_POST
def home_thrust_move(request, pk):
    """Swap a thrust card with its neighbour to reorder the grid."""
    thrust = get_object_or_404(HomeThrust, pk=pk)
    direction = request.POST.get("direction")

    siblings = list(HomeThrust.objects.order_by("order", "id"))
    index = next((i for i, t in enumerate(siblings) if t.pk == thrust.pk), None)

    if index is not None:
        swap_with = None
        if direction == "up" and index > 0:
            swap_with = siblings[index - 1]
        elif direction == "down" and index < len(siblings) - 1:
            swap_with = siblings[index + 1]

        if swap_with is not None:
            # Normalise ordering first so swaps are always well-defined.
            for position, item in enumerate(siblings, start=1):
                if item.order != position:
                    item.order = position
                    item.save(update_fields=["order"])
            thrust.refresh_from_db()
            swap_with.refresh_from_db()

            thrust.order, swap_with.order = swap_with.order, thrust.order
            thrust.save(update_fields=["order"])
            swap_with.save(update_fields=["order"])

    return redirect("home_sections_manager")


# ==============================================================
# HOME INLINE EDITORS — every Linked-Data type editable inside the
# matching Content Sections block. Each handler mirrors its standalone
# manager and returns to `next` (or the Home page editor) on success.
# ==============================================================

def _valid_thrust_color(value):
    """Only allow colours from the model's allow-list."""
    allowed = {choice[0] for choice in HomeThrust.COLOR_CHOICES}
    return value if value in allowed else "text-green-600"


@login_required
@admin_required
@require_POST
def home_inline_thrust_create(request):
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "Thrust title is required.")
        return _home_inline_redirect(request)
    HomeThrust.objects.create(
        title=title,
        description=(request.POST.get("description") or "").strip(),
        color_class=_valid_thrust_color(request.POST.get("color_class")),
        is_visible=request.POST.get("is_visible") == "on",
        order=0,
    )
    messages.success(request, f'Thrust \"{title}\" added.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_thrust_update(request, pk):
    thrust = get_object_or_404(HomeThrust, pk=pk)
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "Thrust title is required.")
        return _home_inline_redirect(request)
    thrust.title = title
    thrust.description = (request.POST.get("description") or "").strip()
    thrust.color_class = _valid_thrust_color(request.POST.get("color_class"))
    thrust.is_visible = request.POST.get("is_visible") == "on"
    thrust.save()
    messages.success(request, "Thrust updated.")
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_thrust_delete(request, pk):
    thrust = get_object_or_404(HomeThrust, pk=pk)
    title = thrust.title
    thrust.delete()
    messages.success(request, f'Thrust \"{title}\" deleted.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_thrust_move(request, pk):
    # Reuse the same swap logic but bounce back to the Home editor.
    thrust = get_object_or_404(HomeThrust, pk=pk)
    direction = request.POST.get("direction")
    siblings = list(HomeThrust.objects.order_by("order", "id"))
    index = next((i for i, t in enumerate(siblings) if t.pk == thrust.pk), None)
    if index is not None:
        swap_with = None
        if direction == "up" and index > 0:
            swap_with = siblings[index - 1]
        elif direction == "down" and index < len(siblings) - 1:
            swap_with = siblings[index + 1]
        if swap_with is not None:
            for position, item in enumerate(siblings, start=1):
                if item.order != position:
                    item.order = position
                    item.save(update_fields=["order"])
            thrust.refresh_from_db()
            swap_with.refresh_from_db()
            thrust.order, swap_with.order = swap_with.order, thrust.order
            thrust.save(update_fields=["order"])
            swap_with.save(update_fields=["order"])
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_personnel_create(request):
    name = (request.POST.get("name") or "").strip()
    position = (request.POST.get("position") or "").strip()
    email = (request.POST.get("email") or "").strip()
    photo = request.FILES.get("photo")
    if not name or not position or not photo:
        messages.error(request, "Name, position and photo are required for personnel.")
        return _home_inline_redirect(request)
    Personnel.objects.create(name=name, position=position, email=email, photo=photo)
    messages.success(request, f'Personnel \"{name}\" added.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_personnel_update(request, pk):
    person = get_object_or_404(Personnel, pk=pk)
    name = (request.POST.get("name") or "").strip()
    position = (request.POST.get("position") or "").strip()
    email = (request.POST.get("email") or "").strip()
    if not name or not position:
        messages.error(request, "Name and position are required.")
        return _home_inline_redirect(request)
    person.name = name
    person.position = position
    person.email = email
    if request.FILES.get("photo"):
        person.photo = request.FILES["photo"]
    person.save()
    messages.success(request, f'\"{person.name}\" updated.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_personnel_delete(request, pk):
    person = get_object_or_404(Personnel, pk=pk)
    name = person.name
    person.delete()
    messages.success(request, f'\"{name}\" deleted.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_activity_create(request):
    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip()
    image = request.FILES.get("image")
    active = request.POST.get("active") == "on"
    dates = [d.strip() for d in request.POST.getlist("dates[]") if d.strip()]
    # Support single date field fallback
    single = (request.POST.get("date") or "").strip()
    if single and single not in dates:
        dates.append(single)
    if not title or not description or not dates:
        messages.error(request, "Title, description and at least one date are required for an activity.")
        return _home_inline_redirect(request)
    activity = Activity.objects.create(title=title, description=description, image=image, active=active)
    for d in dates:
        try:
            ActivityDate.objects.get_or_create(activity=activity, date=d)
        except Exception:
            continue
    messages.success(request, f'Activity \"{title}\" added.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_activity_update(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if not title or not description:
        messages.error(request, "Title and description are required.")
        return _home_inline_redirect(request)
    activity.title = title
    activity.description = description
    activity.active = request.POST.get("active") == "on"
    if request.FILES.get("image"):
        activity.image = request.FILES["image"]
    activity.save()
    # Replace dates
    ActivityDate.objects.filter(activity=activity).delete()
    dates = [d.strip() for d in request.POST.getlist("dates[]") if d.strip()]
    single = (request.POST.get("date") or "").strip()
    if single and single not in dates:
        dates.append(single)
    for d in dates:
        try:
            ActivityDate.objects.get_or_create(activity=activity, date=d)
        except Exception:
            continue
    messages.success(request, f'\"{activity.title}\" updated.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    title = activity.title
    activity.delete()
    messages.success(request, f'\"{title}\" deleted.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_process_create(request):
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "Process title is required.")
        return _home_inline_redirect(request)
    process = ExtensionProcess.objects.create(title=title)
    for desc in request.POST.getlist("step_description[]"):
        desc = (desc or "").strip()
        if desc:
            ProcessStep.objects.create(process=process, description=desc)
    # Support single step fallback
    single = (request.POST.get("step_description") or "").strip()
    if single and not request.POST.getlist("step_description[]"):
        ProcessStep.objects.create(process=process, description=single)
    messages.success(request, f'Process \"{title}\" added.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_process_update(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "Process title is required.")
        return _home_inline_redirect(request)
    process.title = title
    # Optional order override
    raw_order = (request.POST.get("order") or "").strip()
    if raw_order:
        try:
            process.order = int(raw_order)
        except ValueError:
            pass
    process.save()
    # Steps update - same logic as standalone process_edit
    step_ids = request.POST.getlist("step_id[]")
    step_descriptions = request.POST.getlist("step_description[]")
    step_orders = request.POST.getlist("step_order[]")
    if step_ids or step_descriptions:
        max_len = max(len(step_ids), len(step_descriptions), len(step_orders), 0)

        def pad(lst, size, fill=""):
            return lst + [fill] * (size - len(lst))

        step_ids = pad(step_ids, max_len)
        step_descriptions = pad(step_descriptions, max_len)
        step_orders = pad(step_orders, max_len, "0")
        valid_ids = [sid for sid in step_ids if sid]
        process.steps.exclude(id__in=valid_ids).delete()
        for i in range(max_len):
            step_id = step_ids[i].strip()
            desc = step_descriptions[i].strip()
            step_order = step_orders[i].strip() or "0"
            if not desc:
                continue
            if step_id:
                step = ProcessStep.objects.filter(id=step_id, process=process).first()
                if step:
                    step.description = desc
                    try:
                        step.order = int(step_order)
                    except ValueError:
                        pass
                    step.save()
            else:
                try:
                    order_val = int(step_order)
                except ValueError:
                    order_val = 0
                ProcessStep.objects.create(process=process, description=desc, order=order_val)
    messages.success(request, f'Process \"{process.title}\" updated.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_process_delete(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)
    title = process.title
    process.delete()
    messages.success(request, f'Process \"{title}\" deleted.')
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_target_create(request):
    year = (request.POST.get("year") or "").strip()
    campus = (request.POST.get("campus") or "").strip()
    metric = (request.POST.get("metric") or "").strip()
    if not year or not campus or not metric:
        messages.error(request, "Year, campus and metric are required for a target.")
        return _home_inline_redirect(request)
    try:
        year_int = int(year)
    except ValueError:
        messages.error(request, "Year must be a number.")
        return _home_inline_redirect(request)
    if Target.objects.filter(year=year_int, campus=campus, metric=metric).exists():
        messages.error(request, "Target already exists for this year, campus and metric.")
        return _home_inline_redirect(request)
    try:
        Target.objects.create(
            year=year_int,
            campus=campus,
            metric=metric,
            planned_q1=int(request.POST.get("planned_q1") or 0),
            planned_q2=int(request.POST.get("planned_q2") or 0),
            planned_q3=int(request.POST.get("planned_q3") or 0),
            planned_q4=int(request.POST.get("planned_q4") or 0),
            actual_q1=int(request.POST.get("actual_q1") or 0),
            actual_q2=int(request.POST.get("actual_q2") or 0),
            actual_q3=int(request.POST.get("actual_q3") or 0),
            actual_q4=int(request.POST.get("actual_q4") or 0),
        )
    except ValueError:
        messages.error(request, "Quarter values must be numbers.")
        return _home_inline_redirect(request)
    messages.success(request, f"Target for {campus} ({year_int}) created.")
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_target_update(request, pk):
    target = get_object_or_404(Target, pk=pk)
    try:
        target.planned_q1 = int(request.POST.get("planned_q1") or 0)
        target.planned_q2 = int(request.POST.get("planned_q2") or 0)
        target.planned_q3 = int(request.POST.get("planned_q3") or 0)
        target.planned_q4 = int(request.POST.get("planned_q4") or 0)
        target.actual_q1 = int(request.POST.get("actual_q1") or 0)
        target.actual_q2 = int(request.POST.get("actual_q2") or 0)
        target.actual_q3 = int(request.POST.get("actual_q3") or 0)
        target.actual_q4 = int(request.POST.get("actual_q4") or 0)
    except ValueError:
        messages.error(request, "Quarter values must be numbers.")
        return _home_inline_redirect(request)
    target.save()
    messages.success(request, "Target updated.")
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_POST
def home_inline_target_delete(request, pk):
    target = get_object_or_404(Target, pk=pk)
    label = f"{target.campus} - {target.get_metric_display()} ({target.year})"
    target.delete()
    messages.success(request, f"Target deleted: {label}")
    return _home_inline_redirect(request)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def workflow_phases_manager(request):
    phases = WorkflowPhase.objects.all()

    if request.method == "POST":
        for phase in phases:
            prefix = f"phase_{phase.id}"
            phase.label = (request.POST.get(f"{prefix}_label") or "").strip() or phase.label
            phase.summary = (request.POST.get(f"{prefix}_summary") or "").strip()
            phase.weight_label = (request.POST.get(f"{prefix}_weight_label") or "").strip()

            raw_percent = (request.POST.get(f"{prefix}_weight_percent") or "").strip()
            try:
                phase.weight_percent = max(0, min(100, int(raw_percent)))
            except (TypeError, ValueError):
                pass  # model save() also clamps; keep the previous value

            phase.is_visible = request.POST.get(f"{prefix}_is_visible") == "on"
            phase.save()

        messages.success(request, "Workflow phases updated successfully.")
        return redirect("workflow_phases_manager")

    return render(request, "dashboard/admin/workflow_phases_manager.html", {"phases": phases})


@login_required
@admin_required
def page_content_logs(request):
    """Audit trail of every content edit, filterable by page."""
    logs = PageContentLog.objects.select_related("changed_by")

    filter_slug = (request.GET.get("page") or "").strip()
    if filter_slug in dict(SitePage.Slug.choices):
        logs = logs.filter(page_slug=filter_slug)
    else:
        filter_slug = ""

    rows = []
    for log in logs[:100]:
        rows.append({
            "log": log,
            "before_json": json.dumps(log.before, indent=2, ensure_ascii=False) if log.before else None,
            "after_json": json.dumps(log.after, indent=2, ensure_ascii=False) if log.after else None,
        })

    return render(request, "dashboard/admin/page_content_logs.html", {
        "logs": rows,
        "filter_slug": filter_slug,
        "page_choices": SitePage.Slug.choices,
    })
