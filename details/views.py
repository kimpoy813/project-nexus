from django.shortcuts import render
from django.db.models import Sum, Q, Max, Min
from django.utils import timezone
from .models import Personnel, Activity, Target, ProcessStep, ExtensionProcess



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
    }

    return render(request, 'details/details_page.html', context)