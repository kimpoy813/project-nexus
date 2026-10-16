"""Shared parsing for the standalone and nested Extension Target editors.

Also holds the small read helpers the role dashboards use to show each
campus's yearly targets next to what was actually accomplished: the
coordinator who files the quarterly figures, and the Staff/Director who
monitor them, should see the same tracker without opening the admin
builder.
"""

from collections import OrderedDict

TARGET_NUMBER_FIELDS = (
    ("target", "Target"),
    ("actual_q1", "Actual Q1"),
    ("actual_q2", "Actual Q2"),
    ("actual_q3", "Actual Q3"),
    ("actual_q4", "Actual Q4"),
)


def _parse_target_numbers(data):
    """Return non-negative integer target values from request-like data.

    The target is a single annual figure; accomplishments are recorded by
    quarter, so blanks are intentionally treated as zero: an administrator
    can fill the quarters in as the year progresses.  The actual total is
    derived, never posted.
    """

    values = {}
    for field, label in TARGET_NUMBER_FIELDS:
        raw_value = data.get(field)
        if raw_value in (None, ""):
            raw_value = 0
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if value < 0:
            raise ValueError(f"{label} cannot be negative.")
        values[field] = value
    return values


def available_target_years(*, include_current=True):
    """Every year with target data, newest first, plus the current year."""
    from django.utils import timezone

    from details.models import Target

    years = set(Target.objects.values_list("year", flat=True))
    if include_current:
        years.add(timezone.now().year)
    return sorted(years, reverse=True)


def resolve_target_year(request, *, param="target_year", default=None):
    """The dashboard year requested via ``?target_year=YYYY``.

    Falls back to ``default``, then the current year, then the newest year
    with data, so the tracker never opens on an empty year by accident.
    """
    from django.utils import timezone

    from details.models import Target

    years = set(Target.objects.values_list("year", flat=True))
    current = timezone.now().year

    try:
        wanted = int(request.GET.get(param, ""))
    except (TypeError, ValueError):
        wanted = None
    if wanted is not None and (wanted in years or wanted == current):
        return wanted
    if default in years:
        return default
    if current in years or not years:
        return current
    return max(years)


def _pack_target_row(metric, label, target):
    """One metric's tracker row, whether or not a ``Target`` row exists yet."""
    if target is None:
        return {
            "metric": metric,
            "label": label,
            "target": None,
            "actual_q1": 0,
            "actual_q2": 0,
            "actual_q3": 0,
            "actual_q4": 0,
            "actual_total": 0,
            "progress": None,
            "has_row": False,
        }
    return {
        "metric": metric,
        "label": label,
        "target": target.target,
        "actual_q1": target.actual_q1,
        "actual_q2": target.actual_q2,
        "actual_q3": target.actual_q3,
        "actual_q4": target.actual_q4,
        "actual_total": target.actual_total,
        "progress": target.completion_percentage,
        "has_row": True,
    }


def campus_target_rows(campus, year):
    """Tracker rows for one campus and year, in metric order.

    Returns ``[]`` when no campus is given (e.g. the account has none
    assigned yet); otherwise one row per metric, with ``has_row`` False for
    metrics the Extension Office has not set a target for yet.
    """
    from details.models import Target

    if not (campus or "").strip():
        return []

    by_metric = {
        target.metric: target
        for target in Target.objects.filter(year=year, campus__iexact=campus.strip())
    }
    return [
        _pack_target_row(metric, label, by_metric.get(metric))
        for metric, label in Target.METRIC_CHOICES
    ]


def all_campus_target_rows(year):
    """``{campus: rows}`` for every campus with targets in ``year``.

    One query for the whole year, so the Staff/Director overview does not
    fan out into a lookup per campus.
    """
    from details.models import Target

    by_campus = OrderedDict()
    for target in Target.objects.filter(year=year).order_by("campus", "metric"):
        by_campus.setdefault(target.campus, {})[target.metric] = target

    grouped = OrderedDict()
    for campus, mapping in by_campus.items():
        grouped[campus] = [
            _pack_target_row(metric, label, mapping.get(metric))
            for metric, label in Target.METRIC_CHOICES
        ]
    return grouped


def overall_target_rows(year):
    """Per-metric totals across all campuses for ``year``."""
    from django.db.models import Sum

    from details.models import Target

    rows = []
    for metric, label in Target.METRIC_CHOICES:
        totals = Target.objects.filter(year=year, metric=metric).aggregate(
            target_sum=Sum("target"), actual_sum=Sum("actual_total")
        )
        target = totals["target_sum"] or 0
        actual = totals["actual_sum"] or 0
        rows.append(
            {
                "metric": metric,
                "label": label,
                "target": target,
                "actual_total": actual,
                "progress": round(100 * actual / target) if target else None,
            }
        )
    return rows
