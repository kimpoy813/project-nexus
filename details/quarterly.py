"""Shared helpers for the quarterly accomplishment report cycle.

Two things live here rather than in a view, because both the coordinator-facing
submission and the Staff/Director monitoring screens need them and they must
agree exactly:

* Mapping the counts a coordinator files alongside the uploaded report file to
  the target categories they answer, and
* Rolling those figures into the campus :class:`~details.models.Target` rows so
  the Extension Targets tracker reflects what was reported instead of being
  maintained by hand a second time.

The submission form asks for each figure once, as a count on the report. That
same count is the coordinator's answer for the matching target category, so
there is no second set of category inputs to fill in.
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

#: The count inputs on the submission form, the target category each one
#: answers, and the label to mention in a validation error. The form asks for
#: the figure once; the report stores it as a count and the target tracker
#: receives the same number.
COUNT_TARGET_METRICS = (
    ("activities_count", "programs", "Activities Count"),
    ("beneficiaries_count", "participants", "Beneficiaries Count"),
    ("partners_count", "partners", "Partners Count"),
)


def contributions_from_report_counts(data):
    """Return ``{metric: value}`` for the counts a coordinator answered.

    Raises :class:`ValueError` with a field-specific message so the view can
    hand it straight to ``messages.error``.

    A blank count is *skipped*, not read as zero: the count boxes start empty,
    and recording an untouched box as 0 would wipe an actual the campus may
    already have on the tracker. A category really at zero is filed by typing
    0. An entirely blank set returns ``{}`` - nothing was answered, so nothing
    is written.

    Technology Transfer has no count box on the report, so it is not touched
    by a submission; it is maintained from the target editor.
    """
    values = {}
    for field, metric, label in COUNT_TARGET_METRICS:
        raw = data.get(field)
        text = "" if raw is None else str(raw).strip()
        if text == "":
            continue

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
