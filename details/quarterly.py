"""Shared helpers for the quarterly accomplishment report cycle.

The request-side matching lives here rather than in a view because both the
coordinator-facing submission and the Staff/Director monitoring screens need
it and they must agree exactly on which report answers which request.
"""

from .models import (
    AccomplishmentReport,
    QuarterlyReportRequest,
)


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
