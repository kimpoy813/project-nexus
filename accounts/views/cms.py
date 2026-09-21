"""
Unified admin editors for the public pages (Home, Services, Reports, Achievements).

Each page has ONE editing screen — ``page_content_edit`` — holding every piece
of content shown on that page, instead of scattering it across separate
managers:

* Home: hero, content sections, section titles, thrust cards, SDG badges,
  personnel, activities, processes, and targets.
* Services: hero, content sections, section copy, and workflow phases, plus a
  summary of the shared builders (processes, templates, forms, wizard steps)
  whose records the page displays.
* Reports / Achievements: hero and content sections (fully admin-authored).

The older standalone managers (``home_sections_manager``,
``workflow_phases_manager``) are kept as thin aliases so saved bookmarks keep
working: they render the same unified editor, and their POSTs land back on it.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Min
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from details.models import Activity
from details.models import DocumentTemplate
from details.models import DynamicFormTemplate
from details.models import ExtensionProcess
from details.models import HomeSDG
from details.models import HomeSectionHeading
from details.models import HomeThrust
from details.models import PageSection
from details.models import Personnel
from details.models import ProposalWizardStepConfig
from details.models import ServiceSectionCopy
from details.models import SitePage
from details.models import Target
from details.models import WorkflowPhase
from ..decorators import admin_required
from ..forms import PageSectionForm
from ..models import SiteConfigurationLog
from .helpers import _safe_next_url


PAGE_PUBLIC_URL_NAMES = {
    "home": "details_page",
    "services": "services_home",
    "reports": "reports_page",
    "achievements": "achievements_page",
}


def _editor_url(slug, anchor=""):
    """Canonical URL of a page's unified editor, optionally with an anchor."""
    base = reverse("page_content_edit", args=[slug])
    return f"{base}#{anchor}" if anchor else base


def _redirect_to_editor(slug, anchor=""):
    return HttpResponseRedirect(_editor_url(slug, anchor))


def _swap_with_neighbour(items, current, direction):
    """Swap ``current`` with its neighbour inside an ordered list.

    Returns True when a swap happened. Ordering is normalised first so swaps
    are always well-defined even after manual edits left gaps behind.
    """
    index = next((i for i, item in enumerate(items) if item.pk == current.pk), None)
    if index is None:
        return False

    swap_with = None
    if direction == "up" and index > 0:
        swap_with = items[index - 1]
    elif direction == "down" and index < len(items) - 1:
        swap_with = items[index + 1]

    if swap_with is None:
        return False

    for position, item in enumerate(items, start=1):
        if item.order != position:
            item.order = position
            item.save(update_fields=["order"])
    current.refresh_from_db()
    swap_with.refresh_from_db()

    current.order, swap_with.order = swap_with.order, current.order
    current.save(update_fields=["order"])
    swap_with.save(update_fields=["order"])
    return True


def _valid_thrust_color(value):
    """Only allow colours from the model's allow-list."""
    allowed = {choice[0] for choice in HomeThrust.COLOR_CHOICES}
    return value if value in allowed else "text-green-600"


# ---------------------------------------------------------------------------
# Shared apply-handlers: each saves one card of the unified editor.
# ---------------------------------------------------------------------------

def _apply_page_hero(request, page):
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


def _apply_home_headings(request):
    for section, _label in HomeSectionHeading.Section.choices:
        HomeSectionHeading.get_for(section)

    for row in HomeSectionHeading.objects.all():
        prefix = f"section_{row.section}"
        row.heading = (request.POST.get(f"{prefix}_heading") or "").strip()
        row.subtitle = (request.POST.get(f"{prefix}_subtitle") or "").strip()
        row.caption = (request.POST.get(f"{prefix}_caption") or "").strip()
        row.nav_label = (request.POST.get(f"{prefix}_nav_label") or "").strip()
        row.is_visible = request.POST.get(f"{prefix}_is_visible") == "on"
        row.save()

    messages.success(request, "Home page sections updated successfully.")


def _apply_thrust_create(request):
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, "A title is required.")
        return

    HomeThrust.objects.create(
        title=title,
        description=(request.POST.get("description") or "").strip(),
        color_class=_valid_thrust_color(request.POST.get("color_class")),
        is_visible=request.POST.get("is_visible") == "on",
        order=0,  # model assigns the next order
    )
    messages.success(request, f'Thrust "{title}" added successfully.')


def _apply_sdg_labels(request):
    for badge in HomeSDG.objects.all():
        prefix = f"sdg_{badge.id}"
        badge.label = (request.POST.get(f"{prefix}_label") or "").strip() or badge.label
        badge.is_visible = request.POST.get(f"{prefix}_is_visible") == "on"
        badge.save()

    messages.success(request, "SDG badges updated successfully.")


def _apply_sdg_move(request):
    badge = get_object_or_404(HomeSDG, pk=request.POST.get("pk"))
    _swap_with_neighbour(
        list(HomeSDG.objects.order_by("order", "id")),
        badge,
        request.POST.get("direction"),
    )


def _apply_services_copy(request):
    for key, _label in ServiceSectionCopy.Key.choices:
        ServiceSectionCopy.get_for(key)

    for block in ServiceSectionCopy.objects.all():
        prefix = f"copy_{block.key}"
        block.eyebrow = (request.POST.get(f"{prefix}_eyebrow") or "").strip()
        block.heading = (request.POST.get(f"{prefix}_heading") or "").strip()
        block.subheading = (request.POST.get(f"{prefix}_subheading") or "").strip()
        block.footer_note = (request.POST.get(f"{prefix}_footer_note") or "").strip()
        block.empty_text = (request.POST.get(f"{prefix}_empty_text") or "").strip()
        block.nav_label = (request.POST.get(f"{prefix}_nav_label") or "").strip()
        raw_anchor = (request.POST.get(f"{prefix}_anchor") or "").strip()
        block.anchor = slugify(raw_anchor)[:60]
        block.is_visible = request.POST.get(f"{prefix}_is_visible") == "on"
        block.save()

    messages.success(request, "Services page copy updated successfully.")


def _apply_workflow_phases(request):
    for phase in WorkflowPhase.objects.all():
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


# ---------------------------------------------------------------------------
# Unified editor context
# ---------------------------------------------------------------------------

def _home_editor_context(request):
    """Everything rendered on the Home page, for its unified editor."""
    for section, _label in HomeSectionHeading.Section.choices:
        HomeSectionHeading.get_for(section)

    years = list(Target.objects.values_list("year", flat=True).distinct().order_by("-year"))
    try:
        targets_year = int(request.GET.get("targets_year") or (years[0] if years else 2026))
    except (TypeError, ValueError):
        targets_year = years[0] if years else 2026

    return {
        "headings": HomeSectionHeading.objects.all(),
        "thrusts": HomeThrust.objects.all(),
        "thrust_heading": HomeSectionHeading.get_for(HomeSectionHeading.Section.THRUST),
        "color_choices": HomeThrust.COLOR_CHOICES,
        "home_sdgs": HomeSDG.objects.all(),
        "personnel": Personnel.objects.all().order_by("name"),
        "activities": (
            Activity.objects.prefetch_related("dates")
            .annotate(first_date=Min("dates__date"))
            .order_by("-first_date", "-id")
        ),
        "processes": ExtensionProcess.objects.prefetch_related("steps").order_by("order", "id"),
        "targets": Target.objects.filter(year=targets_year).order_by("campus", "metric"),
        "targets_year": targets_year,
        "target_years": years or [targets_year],
    }


def _services_editor_context():
    """Everything rendered on the Services page, for its unified editor."""
    for key, _label in ServiceSectionCopy.Key.choices:
        ServiceSectionCopy.get_for(key)

    return {
        "services_copy": ServiceSectionCopy.objects.all(),
        "workflow_phases": WorkflowPhase.objects.all(),
        "processes": ExtensionProcess.objects.prefetch_related("steps").order_by("order", "id"),
        "office_templates": DocumentTemplate.objects.all().order_by("category", "title"),
        "office_forms": DynamicFormTemplate.objects.prefetch_related("fields").order_by("applies_to", "name"),
        "wizard_steps": ProposalWizardStepConfig.objects.all().order_by("display_order", "step_no"),
    }


def _page_editor_context(slug, request):
    page = SitePage.get_for(slug)
    context = {
        "page": page,
        "sections": page.sections.all(),
        "public_url_name": PAGE_PUBLIC_URL_NAMES.get(slug),
        "layout_choices": PageSection.Layout.choices,
    }
    if slug == SitePage.Slug.HOME:
        context.update(_home_editor_context(request))
    elif slug == SitePage.Slug.SERVICES:
        context.update(_services_editor_context())
    return context


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

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
    """One editing screen per page: hero, sections, and every built-in block.

    Each card on the page posts back here with a ``form_id`` saying which
    block it is; the response lands back on the same card via an anchor.
    """
    if slug not in dict(SitePage.Slug.choices):
        raise Http404("Unknown page.")

    page = SitePage.get_for(slug)

    if request.method == "POST":
        form_id = (request.POST.get("form_id") or "hero").strip()

        if form_id == "home_headings" and slug == SitePage.Slug.HOME:
            _apply_home_headings(request)
            return _redirect_to_editor(slug, "section-titles")
        elif form_id == "thrust_create" and slug == SitePage.Slug.HOME:
            _apply_thrust_create(request)
            return _redirect_to_editor(slug, "thrusts")
        elif form_id == "sdg_labels" and slug == SitePage.Slug.HOME:
            _apply_sdg_labels(request)
            return _redirect_to_editor(slug, "sdg-badges")
        elif form_id == "sdg_move" and slug == SitePage.Slug.HOME:
            _apply_sdg_move(request)
            return _redirect_to_editor(slug, "sdg-badges")
        elif form_id == "services_copy" and slug == SitePage.Slug.SERVICES:
            _apply_services_copy(request)
            return _redirect_to_editor(slug, "section-copy")
        elif form_id == "workflow_phases" and slug == SitePage.Slug.SERVICES:
            _apply_workflow_phases(request)
            return _redirect_to_editor(slug, "workflow")
        else:
            _apply_page_hero(request, page)
            return _redirect_to_editor(slug, "page-header")

    return render(
        request,
        "dashboard/admin/page_content_edit.html",
        _page_editor_context(slug, request),
    )


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
    _swap_with_neighbour(
        list(PageSection.objects.filter(page=section.page).order_by("order", "id")),
        section,
        request.POST.get("direction"),
    )
    return redirect("page_content_edit", slug=section.page.slug)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_sections_manager(request):
    """Legacy alias of the Home page's unified editor.

    Kept so saved bookmarks and older links keep working: it renders the same
    editor, and heading POSTs land back on its Section Titles card.
    """
    if request.method == "POST":
        _apply_home_headings(request)
        return _redirect_to_editor(SitePage.Slug.HOME, "section-titles")

    return render(
        request,
        "dashboard/admin/page_content_edit.html",
        _page_editor_context(SitePage.Slug.HOME, request),
    )


def _thrust_back_url(request):
    """Where thrust add/edit forms return to (the Thrust card by default)."""
    return _safe_next_url(request, _editor_url(SitePage.Slug.HOME, "thrusts"))


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_thrust_create(request):
    back_url = _thrust_back_url(request)

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
            return HttpResponseRedirect(back_url)

    return render(request, "dashboard/admin/home_thrust_form.html", {
        "color_choices": HomeThrust.COLOR_CHOICES,
        "is_create": True,
        "back_url": back_url,
        "next": request.GET.get("next", ""),
    })


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def home_thrust_edit(request, pk):
    thrust = get_object_or_404(HomeThrust, pk=pk)
    back_url = _thrust_back_url(request)

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
            return HttpResponseRedirect(back_url)

    return render(request, "dashboard/admin/home_thrust_form.html", {
        "thrust": thrust,
        "color_choices": HomeThrust.COLOR_CHOICES,
        "is_create": False,
        "back_url": back_url,
        "next": request.GET.get("next", ""),
    })


@login_required
@admin_required
@require_POST
def home_thrust_delete(request, pk):
    thrust = get_object_or_404(HomeThrust, pk=pk)
    title = thrust.title
    thrust.delete()
    messages.success(request, f'Thrust "{title}" deleted.')
    return HttpResponseRedirect(_thrust_back_url(request))


@login_required
@admin_required
@require_POST
def home_thrust_move(request, pk):
    """Swap a thrust card with its neighbour to reorder the grid."""
    thrust = get_object_or_404(HomeThrust, pk=pk)
    _swap_with_neighbour(
        list(HomeThrust.objects.order_by("order", "id")),
        thrust,
        request.POST.get("direction"),
    )
    return HttpResponseRedirect(_thrust_back_url(request))


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def workflow_phases_manager(request):
    """Legacy alias of the Services page's unified editor.

    Kept so saved bookmarks and older links keep working: it renders the same
    editor, and phase POSTs land back on its Workflow card.
    """
    if request.method == "POST":
        _apply_workflow_phases(request)
        return _redirect_to_editor(SitePage.Slug.SERVICES, "workflow")

    return render(
        request,
        "dashboard/admin/page_content_edit.html",
        _page_editor_context(SitePage.Slug.SERVICES, request),
    )
