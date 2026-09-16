"""
Admin-editable public pages, Home sections, thrust cards, and workflow phases.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from details.models import HomeSectionHeading
from details.models import HomeThrust
from details.models import PageSection
from details.models import SitePage
from details.models import WorkflowPhase
from ..decorators import admin_required
from ..forms import PageSectionForm
from ..models import SiteConfigurationLog

PAGE_LINKED_DATA = {
    "home": [
        {"label": "Home Sections & Extension Thrust", "url_name": "home_sections_manager", "hint": "Section titles, \u201cIsem Ni Aran\u201d subtitle, and the thrust cards."},
        {"label": "Extension Personnel", "url_name": "personnel_list", "hint": "Photos and roles shown in the Personnel section."},
        {"label": "Extension Activities", "url_name": "activities_list", "hint": "Cards shown in the Activities section."},
        {"label": "Extension Processes", "url_name": "processes_list", "hint": "Steps shown in the Processes section."},
        {"label": "Extension Targets", "url_name": "targets_list", "hint": "Figures shown in the Targets section."},
    ],
    "services": [
        {"label": "Workflow Phases", "url_name": "workflow_phases_manager", "hint": "Proposal / MOA / Implementation cards and progress weights."},
        {"label": "Extension Processes", "url_name": "processes_list", "hint": "Drives the maintained process flow."},
        {"label": "Template Library", "url_name": "document_templates_list", "hint": "Downloadable office templates."},
        {"label": "Form Builder", "url_name": "dynamic_forms_list", "hint": "Configurable forms and checklists."},
        {"label": "Wizard Steps", "url_name": "wizard_steps_manager", "hint": "Proposal wizard step labels."},
    ],
    "reports": [
        {"label": "Extension Targets", "url_name": "targets_list", "hint": "Planned vs. actual figures."},
    ],
    "achievements": [
        {"label": "Extension Activities", "url_name": "activities_list", "hint": "Completed activities worth highlighting."},
    ],
}


PAGE_PUBLIC_URL_NAMES = {
    "home": "details_page",
    "services": "services_home",
    "reports": "reports_page",
    "achievements": "achievements_page",
}


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

    return render(request, "dashboard/admin/page_content_list.html", {"pages": pages})


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def page_content_edit(request, slug):
    """Edit a page's hero/SEO fields and manage its content sections."""
    if slug not in dict(SitePage.Slug.choices):
        raise Http404("Unknown page.")

    page = SitePage.get_for(slug)

    if request.method == "POST":
        page.title = (request.POST.get("title") or "").strip() or page.title
        page.hero_eyebrow = (request.POST.get("hero_eyebrow") or "").strip()
        page.hero_heading = (request.POST.get("hero_heading") or "").strip()
        page.hero_subheading = (request.POST.get("hero_subheading") or "").strip()
        page.meta_title = (request.POST.get("meta_title") or "").strip()
        page.meta_description = (request.POST.get("meta_description") or "").strip()
        page.is_published = request.POST.get("is_published") == "on"
        page.updated_by = request.user
        page.save()

        SiteConfigurationLog.objects.create(
            changed_by=request.user,
            summary=f'Updated "{page.title}" page content',
        )
        messages.success(request, f'"{page.title}" page updated successfully.')
        return redirect("page_content_edit", slug=page.slug)

    context = {
        "page": page,
        "sections": page.sections.all(),
        "linked_data": PAGE_LINKED_DATA.get(slug, []),
        "public_url_name": PAGE_PUBLIC_URL_NAMES.get(slug),
        "layout_choices": PageSection.Layout.choices,
    }
    return render(request, "dashboard/admin/page_content_edit.html", context)


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
            messages.success(request, "Section added successfully.")
            return redirect("page_content_edit", slug=page.slug)
    else:
        form = PageSectionForm()

    return render(request, "dashboard/admin/page_section_form.html", {
        "page": page,
        "form": form,
        "is_create": True,
    })


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def page_section_edit(request, pk):
    section = get_object_or_404(PageSection.objects.select_related("page"), pk=pk)

    if request.method == "POST":
        form = PageSectionForm(request.POST, request.FILES, instance=section)
        if form.is_valid():
            section = form.save(commit=False)
            if request.POST.get("remove_image") == "on":
                section.image = None
            section.save()
            messages.success(request, "Section updated successfully.")
            return redirect("page_content_edit", slug=section.page.slug)
    else:
        form = PageSectionForm(instance=section)

    return render(request, "dashboard/admin/page_section_form.html", {
        "page": section.page,
        "section": section,
        "form": form,
        "is_create": False,
    })


@login_required
@admin_required
@require_POST
def page_section_delete(request, pk):
    section = get_object_or_404(PageSection.objects.select_related("page"), pk=pk)
    page_slug = section.page.slug
    section.delete()
    messages.success(request, "Section deleted.")
    return redirect("page_content_edit", slug=page_slug)


@login_required
@admin_required
@require_POST
def page_section_move(request, pk):
    """Swap a section with its neighbour to reorder the page."""
    section = get_object_or_404(PageSection.objects.select_related("page"), pk=pk)
    direction = request.POST.get("direction")

    siblings = list(PageSection.objects.filter(page=section.page).order_by("order", "id"))
    index = next((i for i, s in enumerate(siblings) if s.pk == section.pk), None)

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
            section.refresh_from_db()
            swap_with.refresh_from_db()

            section.order, swap_with.order = swap_with.order, section.order
            section.save(update_fields=["order"])
            swap_with.save(update_fields=["order"])

    return redirect("page_content_edit", slug=section.page.slug)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_sections_manager(request):
    """Edit the headings/subtitles of every built-in Home section."""
    for section, _label in HomeSectionHeading.Section.choices:
        HomeSectionHeading.get_for(section)

    headings = HomeSectionHeading.objects.all()

    if request.method == "POST":
        for row in headings:
            prefix = f"section_{row.section}"
            row.heading = (request.POST.get(f"{prefix}_heading") or "").strip()
            row.subtitle = (request.POST.get(f"{prefix}_subtitle") or "").strip()
            row.caption = (request.POST.get(f"{prefix}_caption") or "").strip()
            row.nav_label = (request.POST.get(f"{prefix}_nav_label") or "").strip()
            row.is_visible = request.POST.get(f"{prefix}_is_visible") == "on"
            row.save()

        messages.success(request, "Home page sections updated successfully.")
        return redirect("home_sections_manager")

    return render(request, "dashboard/admin/home_sections_manager.html", {
        "headings": headings,
        "thrusts": HomeThrust.objects.all(),
        "thrust_heading": HomeSectionHeading.get_for(HomeSectionHeading.Section.THRUST),
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


def _valid_thrust_color(value):
    """Only allow colours from the model's allow-list."""
    allowed = {choice[0] for choice in HomeThrust.COLOR_CHOICES}
    return value if value in allowed else "text-yellow-600"


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
