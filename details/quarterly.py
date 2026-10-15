"""Shared helpers for the quarterly accomplishment report cycle.

Two things live here rather than in a view, because both the coordinator-facing
submission and the Staff/Director monitoring screens need them and they must
agree exactly:

* Parsing and storing the per-category answers a coordinator files alongside
  the uploaded report file, and
* Rolling those answers into the campus :class:`~details.models.Target` rows so
  the Extension Targets tracker reflects what was reported instead of being
  maintained by hand a second time.
"""

import logging

from .models import (
    AccomplishmentReport,
    AccomplishmentTargetEntry,
    QuarterlyReportRequest,
    Target,
)

logger = logging.getLogger(__name__)


#: Which ``Target`` field a quarter's figure belongs in.
QUARTER_ACTUAL_FIELDS = {
    AccomplishmentReport.Quarter.Q1: "actual_q1",
    AccomplishmentReport.Quarter.Q2: "actual_q2",
    AccomplishmentReport.Quarter.Q3: "actual_q3",
    AccomplishmentReport.Quarter.Q4: "actual_q4",
}

#: Prefix used by the submission form for the per-category answer inputs.
CONTRIBUTION_FIELD_PREFIX = "target_"


def parse_target_contributions(data, *, metrics=None):
    """Return ``{metric: value}`` parsed from a request-like mapping.

    Raises :class:`ValueError` with a field-specific message so the view can
    hand it straight to ``messages.error``.

    A blank category is *skipped*, not read as zero: the coordinator is
    answering "how much did this quarter include", and recording an untouched
    box as 0 would understate the campus. A category really at zero is filed by
    typing 0. An entirely blank submission returns ``{}`` - nothing was
    answered, so nothing is written.
    """
    metrics = list(metrics or [value for value, _label in Target.METRIC_CHOICES])

    values = {}
    for metric in metrics:
        raw = data.get(f"{CONTRIBUTION_FIELD_PREFIX}{metric}")
        text = "" if raw is None else str(raw).strip()
        if text == "":
            continue

        label = dict(Target.METRIC_CHOICES).get(metric, metric)
        try:
            number = int(text)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if number < 0:
            raise ValueError(f"{label} cannot be negative.")
        values[metric] = number
    return values


def save_target_contributions(report, contributions):
    """Store ``contributions`` on ``report`` and roll them into the tracker.

    Removes rows for categories that are no longer answered so a correction
    (a category emptied on resubmission) does not leave a stale figure behind.
    """
    if not contributions:
        report.target_entries.all().delete()
        return []

    for metric, value in contributions.items():
        AccomplishmentTargetEntry.objects.update_or_create(
            report=report,
            metric=metric,
            defaults={"value": value},
        )
    report.target_entries.exclude(metric__in=list(contributions)).delete()

    return sync_report_targets(report)


def sync_report_targets(report):
    """Write ``report``'s quarterly figures into the campus ``Target`` rows.

    The most recently saved report for a campus+quarter wins, so a coordinator
    correcting their answer replaces the previous figure rather than adding to
    it. A ``Target`` row is created when the campus has not been given one for
    that metric yet, with a yearly target of 0 - the answer is still recorded
    and the tracker shows it as "no target set".
    """
    field = QUARTER_ACTUAL_FIELDS.get(report.quarter)
    if not field or not report.campus:
        return []

    targets = []
    for entry in report.target_entries.all():
        target, _created = Target.objects.get_or_create(
            year=report.year,
            campus=report.campus,
            metric=entry.metric,
            defaults={"target": 0},
        )
        if getattr(target, field) != entry.value:
            setattr(target, field, entry.value)
            target.save(update_fields=[field])
        targets.append(target)
    return targets


def submissions_for(requests):
    """Map ``request.pk -> answering report`` for a list of requests.

    One query, so a monitoring page showing every campus does not fan out into
    a report lookup per row. A report answers a request when it is linked to it
    explicitly or when it matches the request's campus, year and quarter - the
    latter so an older report filed before the request existed still counts.
    """
    requests = list(requests)
    if not requests:
        return {}

    candidates = AccomplishmentReport.objects.select_related(
        "submitted_by", "submitted_by__profile"
    ).filter(
        year__in={request.year for request in requests},
        quarter__in={request.quarter for request in requests},
    )

    submissions = {}
    for report in candidates.order_by("updated_at", "id"):
        key = (report.year, report.quarter, (report.campus or "").strip().casefold())
        for request in requests:
            matches = report.request_id == request.pk or key == (
                request.year,
                request.quarter,
                (request.campus or "").strip().casefold(),
            )
            if matches:
                # Ordered oldest-first, so the newest answer overwrites.
                submissions[request.pk] = report

    return submissions


def open_requests_for_campus(campus):
    """Open requests for ``campus`` that the coordinator has not answered yet."""
    if not (campus or "").strip():
        return []

    requests = list(
        QuarterlyReportRequest.objects.filter(
            campus__iexact=campus.strip(),
            status=QuarterlyReportRequest.Status.OPEN,
        ).order_by("year", "quarter")
    )
    submissions = submissions_for(requests)
    return [request for request in requests if request.pk not in submissions]


def pending_requests_for_user(user):
    """Outstanding requests addressed to a Campus Coordinator, newest first."""
    from accounts import permissions

    if not permissions.is_campus_coordinator(user):
        return []

    profile = getattr(user, "profile", None)
    pending = open_requests_for_campus(getattr(profile, "campus", ""))
    return sorted(
        pending,
        key=lambda request: (request.year, request.quarter),
        reverse=True,
    )


def request_form_context(year, campus, *, values=None):
    """What the submission form needs to render the category answer rows.

    For every ``Target`` category it reports the yearly target already set for
    this campus (if any) and the figure filed for the quarter being reported,
    so the coordinator can see what they are contributing to. ``values``
    overrides the filed figures - used when a rejected submission is rendered
    back with what the coordinator just typed.
    """
    targets = {
        target.metric: target
        for target in Target.objects.filter(
            year=year, campus__iexact=(campus or "").strip()
        )
    }
    answered = dict(values or {})

    rows = []
    for metric, label in Target.METRIC_CHOICES:
        target = targets.get(metric)
        rows.append(
            {
                "metric": metric,
                "label": label,
                "yearly_target": target.target if target else None,
                "answered": answered.get(metric),
            }
        )
    return rows


def posted_contributions(data):
    """Raw (unvalidated) contribution inputs, for re-rendering a form."""
    return {
        metric: (data.get(f"{CONTRIBUTION_FIELD_PREFIX}{metric}") or "").strip()
        for metric, _label in Target.METRIC_CHOICES
    }
