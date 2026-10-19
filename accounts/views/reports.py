"""
Quarterly accomplishment reports and the request cycle around them.

The flow this module implements:

1. Staff, Director or Admin open a *quarterly report request* per campus (see
   :class:`details.models.QuarterlyReportRequest`), usually for every campus at
   once, with an optional due date.
2. The Campus Coordinator sees the outstanding request on their dashboard, and
   submits a report: the uploaded file, the narrative, and the quarter's
   activities, beneficiaries and partners counts.
3. Those counts answer the matching target categories and are rolled into the
   campus ``Target`` rows by
   ``details.quarterly.save_target_contributions``, so the Extension Targets
   tracker and the public Targets block reflect the same figures.
4. Staff and Director see every submission, its file, and its figures, and
   can monitor which campuses still owe a report.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from details.models import AccomplishmentReport
from details.models import QuarterlyReportRequest
from details.models import RoleCapability
from details.models import Target
from details.quarterly import contributions_from_report_counts
from details.quarterly import open_requests_for_campus
from details.quarterly import save_target_contributions
from details.quarterly import submissions_for
from .. import permissions
from ..campus_data import get_campus_choices
from ..models import Profile
from .helpers import _safe_int
from .helpers import _user_role


ACCOMPLISHMENT_SUBMIT_ROLES = permissions.ACCOMPLISHMENT_SUBMIT_ROLES


ACCOMPLISHMENT_VIEW_ONLY_ROLES = permissions.ACCOMPLISHMENT_VIEW_ONLY_ROLES


ACCOMPLISHMENT_REPORT_ROLES = permissions.ACCOMPLISHMENT_REPORT_ROLES


QUARTERLY_REQUEST_ROLES = permissions.QUARTERLY_REQUEST_ROLES


can_submit_accomplishment_reports = permissions.can_submit_accomplishment_reports


can_access_accomplishment_reports = permissions.can_view_accomplishment_reports


can_request_quarterly_reports = permissions.can_request_quarterly_reports


can_view_quarterly_requests = permissions.can_view_quarterly_requests


user_has_capability = permissions.has_capability


def _current_quarter():
    """The quarter the calendar is in, used as the form's default."""
    month = timezone.localdate().month
    return f"Q{min(4, (month - 1) // 3 + 1)}"


def _target_index(reports):
    """``{(year, campus, metric): Target}`` for the reports on screen.

    One query for the whole table, so the reports list can show "12 of 40"
    against each category instead of looking a target up per row.
    """
    reports = list(reports)
    if not reports:
        return {}

    targets = Target.objects.filter(
        year__in={report.year for report in reports},
        campus__in={report.campus for report in reports if report.campus},
    )
    return {
        (target.year, (target.campus or "").strip().casefold(), target.metric): target
        for target in targets
    }


def _report_rows(reports):
    """Rows for the reports table: each report with its category answers."""
    reports = list(reports)
    index = _target_index(reports)

    rows = []
    for report in reports:
        entries = []
        for entry in report.target_entries.all():
            key = (report.year, (report.campus or "").strip().casefold(), entry.metric)
            target = index.get(key)
            entries.append(
                {
                    "metric": entry.metric,
                    "label": entry.get_metric_display(),
                    "value": entry.value,
                    "yearly_target": target.target if target else None,
                }
            )
        rows.append({"report": report, "entries": entries})
    return rows


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@login_required
def accomplishment_reports_list(request):
    if not can_access_accomplishment_reports(request.user):
        messages.error(request, "You do not have permission to view accomplishment reports.")
        return redirect("dashboard_redirect")

    profile = getattr(request.user, "profile", None)
    role = _user_role(request.user)
    reports = AccomplishmentReport.objects.select_related(
        "submitted_by", "submitted_by__profile", "request"
    ).prefetch_related("target_entries")

    # Coordinators only see their own scope; Staff and Director see everything.
    if role == Profile.ROLE_DEPARTMENT_COORDINATOR:
        reports = reports.filter(department=getattr(profile, "department", ""))
    elif role == Profile.ROLE_CAMPUS_COORDINATOR:
        reports = reports.filter(campus=getattr(profile, "campus", ""))
    elif not permissions.sees_all_accomplishment_reports(request.user):
        reports = reports.filter(submitted_by=request.user)

    pending_requests = []
    if role == Profile.ROLE_CAMPUS_COORDINATOR:
        pending_requests = open_requests_for_campus(getattr(profile, "campus", ""))

    return render(
        request,
        "dashboard/accomplishment_reports_list.html",
        {
            "report_rows": _report_rows(reports),
            "can_submit_accomplishment": can_submit_accomplishment_reports(request.user),
            "can_view_requests": can_view_quarterly_requests(request.user),
            "pending_requests": pending_requests,
        },
    )


@login_required
def accomplishment_report_detail(request, pk):
    report = get_object_or_404(
        AccomplishmentReport.objects.select_related(
            "submitted_by", "submitted_by__profile", "request"
        ).prefetch_related("target_entries"),
        pk=pk,
    )

    if not _can_view_report(request.user, report):
        messages.error(request, "You do not have permission to view this report.")
        return redirect("dashboard_redirect")

    row = _report_rows([report])[0]
    return render(
        request,
        "dashboard/accomplishment_report_detail.html",
        {
            "report": report,
            "entries": row["entries"],
            "can_submit_accomplishment": can_submit_accomplishment_reports(request.user),
            "can_view_requests": can_view_quarterly_requests(request.user),
        },
    )


def _can_view_report(user, report):
    """Mirror the list scoping, so a deep link cannot widen it."""
    if not can_access_accomplishment_reports(user):
        return False

    if permissions.sees_all_accomplishment_reports(user):
        return True

    if report.submitted_by_id == getattr(user, "id", None):
        return True

    profile = getattr(user, "profile", None)
    role = _user_role(user)

    if role == Profile.ROLE_CAMPUS_COORDINATOR:
        return permissions.same_scope(report.campus, getattr(profile, "campus", ""))
    if role == Profile.ROLE_DEPARTMENT_COORDINATOR:
        return permissions.same_scope(
            report.department, getattr(profile, "department", "")
        )
    return False


@login_required
def accomplishment_report_create(request):
    if not user_has_capability(request.user, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT):
        messages.error(request, "You do not have permission to submit accomplishment reports.")
        return redirect("dashboard_redirect")

    profile = getattr(request.user, "profile", None)
    role = _user_role(request.user)

    # Only a Campus Coordinator answers for a campus target. A Department
    # Coordinator's scope sits inside a campus, so their answers would land on
    # the wrong row of the tracker.
    is_campus_coordinator = role == Profile.ROLE_CAMPUS_COORDINATOR
    can_answer_targets = is_campus_coordinator
    own_campus = (getattr(profile, "campus", "") or "").strip()

    report_request = _request_for_submission(request)
    pending_requests = (
        open_requests_for_campus(own_campus) if can_answer_targets else []
    )

    values = _submission_values(request, profile, report_request)
    if is_campus_coordinator:
        # A Campus Coordinator files for exactly one campus - the request
        # being answered, otherwise their own assignment - so the form shows
        # no campus/college/department inputs at all. The scope below is the
        # only scope the report can be saved under.
        values["campus"] = (
            (getattr(report_request, "campus", "") or own_campus) or ""
        ).strip()
    # A filed request is a correction, not a fresh set of figures: keep the
    # counts available but render their section without the initial emphasis.
    previous_submission = (
        submissions_for([report_request]).get(report_request.pk)
        if is_campus_coordinator and report_request else None
    )
    if request.method == "GET" and previous_submission:
        # Re-showing what was filed before beats an empty grid: the figures
        # are replaced, not added, so a correction starts from the old answer.
        values.update(_previous_counts(previous_submission))
    contributions = {}

    if request.method == "POST":
        error = None
        if not values["title"] or values["quarter"] not in dict(
            AccomplishmentReport.Quarter.choices
        ):
            error = "Title and quarter are required."
        elif is_campus_coordinator and not values["campus"]:
            error = (
                "Your account has no campus assigned yet. Ask the Admin to set "
                "your campus before filing a report."
            )
        elif (
            is_campus_coordinator
            and (request.POST.get("campus") or "").strip()
            and not permissions.same_scope(
                (request.POST.get("campus") or "").strip(), values["campus"]
            )
        ):
            # The form sends no campus field; a mismatched value here means a
            # hand-crafted POST trying to file for another campus.
            error = (
                f"Your account files reports for {values['campus']}. "
                "You cannot file for another campus."
            )
        elif (
            report_request
            and not is_campus_coordinator
            and not permissions.same_scope(report_request.campus, values["campus"])
        ):
            error = (
                "This report answers the request for "
                f"{report_request.campus}. Keep the campus set to that campus, "
                "or open the request again from your dashboard."
            )
        elif report_request and not request.FILES.get("attachment"):
            error = "Attach the quarterly report file before submitting."

        # The counts are the coordinator's one set of figures. The same
        # numbers answer the matching target categories, so the form never
        # asks for Programs / Participants / Partners a second time.
        if error is None and can_answer_targets:
            try:
                contributions = contributions_from_report_counts(values)
            except ValueError as exc:
                error = str(exc)
            else:
                if contributions and not values["campus"]:
                    error = (
                        "Your account has no campus assigned yet, so the target "
                        "figures cannot be recorded. Ask the Admin to set your "
                        "campus first."
                    )

        if error:
            messages.error(request, error)
        else:
            if report_request is None and contributions and can_answer_targets:
                # Filing for a quarter the campus was asked about answers that
                # request even when the coordinator came in through the plain
                # "Submit Report" button.
                report_request = _matching_open_request(
                    values["year"], values["quarter"], values["campus"]
                )

            report = AccomplishmentReport.objects.create(
                title=values["title"],
                year=values["year"],
                quarter=values["quarter"],
                campus=values["campus"],
                # A campus report covers the whole campus, so it carries no
                # college/department scope of its own.
                college="" if is_campus_coordinator else (request.POST.get("college") or getattr(profile, "college", "") or "").strip(),
                department="" if is_campus_coordinator else (request.POST.get("department") or getattr(profile, "department", "") or "").strip(),
                narrative=values["narrative"],
                activities_count=_safe_int(values["activities_count"], 0),
                beneficiaries_count=_safe_int(values["beneficiaries_count"], 0),
                partners_count=_safe_int(values["partners_count"], 0),
                attachment=request.FILES.get("attachment"),
                submitted_by=request.user,
                request=report_request,
            )
            if contributions:
                save_target_contributions(report, contributions)

            message = "Quarterly accomplishment report submitted."
            if contributions:
                message += (
                    " Your target figures were recorded for "
                    f"{report.get_quarter_display()} {report.year}."
                )
            messages.success(request, message)
            return redirect("accomplishment_reports_list")

    return render(
        request,
        "dashboard/accomplishment_report_form.html",
        {
            "quarter_choices": AccomplishmentReport.Quarter.choices,
            "profile": profile,
            "current_year": values["year"],
            # Live campus list from the admin-managed Campus table so the
            # cascading college/department selects have a source of truth.
            "campus_choices": [value for value, _label in get_campus_choices()],
            "is_campus_coordinator": is_campus_coordinator,
            "filing_campus": values["campus"],
            "selected_campus": values["campus"],
            "selected_quarter": values["quarter"],
            "values": values,
            "report_request": report_request,
            "is_resubmission": previous_submission is not None,
            "pending_requests": pending_requests,
        },
    )


def _submission_values(request, profile, report_request):
    """The title/year/quarter/campus/narrative the form starts or re-renders with.

    Posted data wins, so a rejected submission is handed back exactly as typed.
    Otherwise the request being answered decides the period, and the profile
    provides the campus.
    """
    def pick(field, fallback=""):
        return (request.POST.get(field) or "").strip() or (fallback or "").strip()

    year = _safe_int(
        request.POST.get("year") or request.GET.get("year"),
        getattr(report_request, "year", None) or timezone.now().year,
    )
    return {
        "title": pick("title", getattr(report_request, "default_title", "")),
        "year": year,
        "quarter": pick(
            "quarter",
            request.GET.get("quarter") or getattr(report_request, "quarter", ""),
        ),
        "campus": pick(
            "campus",
            getattr(report_request, "campus", "")
            or getattr(profile, "campus", ""),
        ),
        "narrative": (request.POST.get("narrative") or "").strip(),
        # Blank, not "0": an untouched count means "not answered this quarter"
        # and must not overwrite an actual already on the target tracker.
        "activities_count": (request.POST.get("activities_count") or "").strip(),
        "beneficiaries_count": (request.POST.get("beneficiaries_count") or "").strip(),
        "partners_count": (request.POST.get("partners_count") or "").strip(),
    }


def _previous_counts(previous):
    """Count inputs to prefill from a previously filed report.

    Reports filed before the form was consolidated answered Programs /
    Participants / Partners instead of filling counts, so fall back to those
    target entries when the report's counts are all zero.
    """
    counts = {
        "activities_count": previous.activities_count,
        "beneficiaries_count": previous.beneficiaries_count,
        "partners_count": previous.partners_count,
    }
    if any(counts.values()):
        return {field: str(value) for field, value in counts.items()}

    entries = previous.target_contributions()
    return {
        "activities_count": str(entries.get("programs", "")),
        "beneficiaries_count": str(entries.get("participants", "")),
        "partners_count": str(entries.get("partners", "")),
    }


def _matching_open_request(year, quarter, campus):
    """The open request a submission answers, matched on its period and scope."""
    if not campus:
        return None

    open_requests = QuarterlyReportRequest.objects.filter(
        year=year,
        quarter=quarter,
        status=QuarterlyReportRequest.Status.OPEN,
    )
    for item in open_requests:
        if permissions.same_scope(item.campus, campus):
            return item
    return None


def _request_for_submission(request):
    """The request this submission answers, from ``?request=<pk>`` or the body.

    A request outside the coordinator's own campus is ignored rather than
    linked, so a hand-edited id cannot make someone else's row look answered.
    """
    raw = request.POST.get("request") or request.GET.get("request")
    if not raw:
        return None

    try:
        request_pk = int(raw)
    except (TypeError, ValueError):
        return None

    report_request = QuarterlyReportRequest.objects.filter(pk=request_pk).first()
    if report_request is None or not report_request.is_open:
        return None

    if not permissions.sees_all_quarterly_requests(request.user):
        profile = getattr(request.user, "profile", None)
        if not permissions.same_scope(
            report_request.campus, getattr(profile, "campus", "")
        ):
            return None

    return report_request


# ---------------------------------------------------------------------------
# Requests - "the system asks the Campus Coordinator"
# ---------------------------------------------------------------------------

@login_required
def accomplishment_requests_list(request):
    if not can_view_quarterly_requests(request.user):
        messages.error(request, "You do not have permission to view report requests.")
        return redirect("dashboard_redirect")

    profile = getattr(request.user, "profile", None)
    requests_qs = QuarterlyReportRequest.objects.select_related(
        "requested_by", "requested_by__profile"
    )

    if not permissions.sees_all_quarterly_requests(request.user):
        requests_qs = requests_qs.filter(campus__iexact=getattr(profile, "campus", ""))

    current_year = _safe_int(request.GET.get("year"), timezone.now().year)
    show_all = request.GET.get("all") in {"1", "true", "yes"}
    if not show_all:
        requests_qs = requests_qs.filter(year=current_year)

    requests_list = list(requests_qs)
    submissions = submissions_for(requests_list)

    rows = []
    for item in requests_list:
        submission = submissions.get(item.pk)
        rows.append(
            {
                "request": item,
                "submission": submission,
                # A closed request that already has a report stays "Reported".
                "state": (
                    "submitted"
                    if submission
                    else ("closed" if not item.is_open else "awaiting")
                ),
            }
        )

    years = list(
        QuarterlyReportRequest.objects.values_list("year", flat=True).distinct()
    )
    for extra in (current_year, timezone.now().year):
        if extra not in years:
            years.append(extra)
    years.sort(reverse=True)

    return render(
        request,
        "dashboard/accomplishment_requests_list.html",
        {
            "rows": rows,
            "current_year": current_year,
            "show_all": show_all,
            "years": years,
            "awaiting_count": sum(1 for row in rows if row["state"] == "awaiting"),
            "submitted_count": sum(1 for row in rows if row["state"] == "submitted"),
            "can_request": can_request_quarterly_reports(request.user),
            "can_submit_accomplishment": can_submit_accomplishment_reports(request.user),
            "campus_choices": [value for value, _label in get_campus_choices()],
            "quarter_choices": AccomplishmentReport.Quarter.choices,
            "default_quarter": _current_quarter(),
        },
    )


@login_required
def accomplishment_request_create(request):
    if not can_request_quarterly_reports(request.user):
        messages.error(request, "You do not have permission to request quarterly reports.")
        return redirect("dashboard_redirect")

    campus_choices = [value for value, _label in get_campus_choices()]

    if request.method == "POST":
        year = _safe_int(request.POST.get("year"), timezone.now().year)
        quarter = (request.POST.get("quarter") or "").strip()
        selected = request.POST.getlist("campuses")
        if "ALL" in selected:
            selected = list(campus_choices)
        instructions = (request.POST.get("instructions") or "").strip()
        due_date = (request.POST.get("due_date") or "").strip() or None

        if quarter not in dict(AccomplishmentReport.Quarter.choices):
            messages.error(request, "Choose the quarter to request.")
        elif not selected:
            messages.error(request, "Choose at least one campus to ask.")
        else:
            created, existing = 0, 0
            for campus in selected:
                _, was_created = QuarterlyReportRequest.objects.get_or_create(
                    year=year,
                    quarter=quarter,
                    campus=campus,
                    defaults={
                        "instructions": instructions,
                        "due_date": due_date,
                        "requested_by": request.user,
                    },
                )
                if was_created:
                    created += 1
                else:
                    existing += 1
                    # Re-opening is the useful outcome of asking again.
                    QuarterlyReportRequest.objects.filter(
                        year=year, quarter=quarter, campus=campus
                    ).update(
                        status=QuarterlyReportRequest.Status.OPEN,
                        instructions=instructions or "",
                        due_date=due_date,
                    )

            messages.success(
                request,
                f"Requested {created} campus report{'' if created == 1 else 's'} for "
                f"{dict(AccomplishmentReport.Quarter.choices)[quarter]} {year}."
                + (f" {existing} already existed and were re-opened." if existing else ""),
            )
            return redirect(
                f"{reverse('accomplishment_requests_list')}?{urlencode({'year': year})}"
            )

    return render(
        request,
        "dashboard/accomplishment_request_form.html",
        {
            "campus_choices": campus_choices,
            "quarter_choices": AccomplishmentReport.Quarter.choices,
            "default_year": timezone.now().year,
            "default_quarter": _current_quarter(),
        },
    )


@login_required
def accomplishment_request_close(request, pk):
    """Open or close one request (POST only)."""
    if not can_request_quarterly_reports(request.user):
        messages.error(request, "You do not have permission to change report requests.")
        return redirect("dashboard_redirect")

    report_request = get_object_or_404(QuarterlyReportRequest, pk=pk)

    if report_request.is_open:
        report_request.status = QuarterlyReportRequest.Status.CLOSED
        note = "closed"
    else:
        report_request.status = QuarterlyReportRequest.Status.OPEN
        note = "re-opened"
    report_request.save(update_fields=["status", "updated_at"])

    messages.success(
        request,
        f"{report_request.campus} - {report_request.period_label} request {note}.",
    )
    return redirect(
        f"{reverse('accomplishment_requests_list')}?"
        f"{urlencode({'year': report_request.year})}"
    )
