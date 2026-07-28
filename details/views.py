from django.http import Http404
from django.shortcuts import render
from django.db.models import Sum, Q, Max, Min
from django.utils import timezone
from .models import (
    Personnel,
    Activity,
    Target,
    ProcessStep,
    ExtensionProcess,
    HomeSectionHeading,
    HomeThrust,
    SitePage,
)



def details_page(request):
    personnel = Personnel.objects.all()
    # Activities (multi-date) - ordered by latest date
    activities = (
        Activity.objects.prefetch_related("dates").all()
        .annotate(first_date=Min("dates__date"), last_date=Max("dates__date"))
        .order_by("-last_date", "-id")
    )

    # ✅ Processes - ordered by "order"
    process_steps = ExtensionProcess.objects.all().prefetch_related("steps").order_by("order", "id")
    targets = Target.objects.all()

    # Year selection
    year = int(request.GET.get('year', 2026))
    yearly_targets = targets.filter(year=year)

    # Overall totals
    overall_targets = {}
    for key, label in Target.METRIC_CHOICES:
        sums = yearly_targets.filter(metric=key).aggregate(
            planned=Sum('planned_total'),
            actual=Sum('actual_total')
        )
        overall_targets[key] = {
            'label': label,
            'planned': sums['planned'] or 0,
            'actual': sums['actual'] or 0,
        }

    # Group by campus
    from collections import OrderedDict
    targets_by_campus = OrderedDict()
    for t in yearly_targets.order_by('campus', 'metric'):
        targets_by_campus.setdefault(t.campus, []).append(t)

    context = {
        'personnel': personnel,
        'activities': activities,
        'process_steps': process_steps,
        'targets_by_campus': targets_by_campus,
        'overall_targets': overall_targets,
        'selected_year': year,
        'page': SitePage.get_for(SitePage.Slug.HOME),
        'home_sections': HomeSectionHeading.as_map(),
        'home_headings': HomeSectionHeading.objects.all(),
        'home_thrusts': HomeThrust.objects.filter(is_visible=True),
    }

    return render(request, 'details/details_page.html', context)


def _render_content_page(request, slug, template="details/content_page.html"):
    """Render a fully admin-managed public page.

    Unpublished pages stay reachable for admins (so they can preview drafts)
    but return 404 for everyone else.
    """
    page = SitePage.get_for(slug)

    if not page.is_published:
        profile = getattr(getattr(request, "user", None), "profile", None)
        role = (getattr(profile, "role", "") or "").upper()
        is_admin = role == "ADMIN" or getattr(request.user, "is_superuser", False)
        if not is_admin:
            raise Http404("This page is not available.")

    return render(
        request,
        template,
        {
            "page": page,
            "sections": page.visible_sections,
            "is_preview": not page.is_published,
        },
    )


def reports_page(request):
    return _render_content_page(request, SitePage.Slug.REPORTS)


def achievements_page(request):
    return _render_content_page(request, SitePage.Slug.ACHIEVEMENTS)