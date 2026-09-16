"""
Quarterly accomplishment reports.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from details.models import AccomplishmentReport
from details.models import RoleCapability
from .. import permissions
from ..campus_data import get_campus_choices
from ..models import Profile
from .helpers import _safe_int, _user_role


ACCOMPLISHMENT_SUBMIT_ROLES = permissions.ACCOMPLISHMENT_SUBMIT_ROLES


ACCOMPLISHMENT_VIEW_ONLY_ROLES = permissions.ACCOMPLISHMENT_VIEW_ONLY_ROLES


ACCOMPLISHMENT_REPORT_ROLES = permissions.ACCOMPLISHMENT_REPORT_ROLES


can_submit_accomplishment_reports = permissions.can_submit_accomplishment_reports


can_access_accomplishment_reports = permissions.can_view_accomplishment_reports


user_has_capability = permissions.has_capability


@login_required
def accomplishment_reports_list(request):
    if not can_access_accomplishment_reports(request.user):
        messages.error(request, "You do not have permission to view accomplishment reports.")
        return redirect("dashboard_redirect")

    profile = getattr(request.user, "profile", None)
    role = _user_role(request.user)
    reports = AccomplishmentReport.objects.select_related("submitted_by", "submitted_by__profile")

    # Coordinators only see their own scope; Staff and Director see everything.
    if role == Profile.ROLE_DEPARTMENT_COORDINATOR:
        reports = reports.filter(department=getattr(profile, "department", ""))
    elif role == Profile.ROLE_CAMPUS_COORDINATOR:
        reports = reports.filter(campus=getattr(profile, "campus", ""))
    elif not permissions.sees_all_accomplishment_reports(request.user):
        reports = reports.filter(submitted_by=request.user)

    return render(
        request,
        "dashboard/accomplishment_reports_list.html",
        {
            "reports": reports,
            "can_submit_accomplishment": can_submit_accomplishment_reports(request.user),
        },
    )


@login_required
def accomplishment_report_create(request):
    if not user_has_capability(request.user, RoleCapability.Capability.SUBMIT_QUARTERLY_ACCOMPLISHMENT):
        messages.error(request, "You do not have permission to submit accomplishment reports.")
        return redirect("dashboard_redirect")

    profile = getattr(request.user, "profile", None)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        year = _safe_int(request.POST.get("year"), timezone.now().year)
        quarter = (request.POST.get("quarter") or "").strip()
        if not title or quarter not in dict(AccomplishmentReport.Quarter.choices):
            messages.error(request, "Title and quarter are required.")
        else:
            AccomplishmentReport.objects.create(
                title=title,
                year=year,
                quarter=quarter,
                campus=(request.POST.get("campus") or getattr(profile, "campus", "") or "").strip(),
                college=(request.POST.get("college") or getattr(profile, "college", "") or "").strip(),
                department=(request.POST.get("department") or getattr(profile, "department", "") or "").strip(),
                narrative=(request.POST.get("narrative") or "").strip(),
                activities_count=_safe_int(request.POST.get("activities_count"), 0),
                beneficiaries_count=_safe_int(request.POST.get("beneficiaries_count"), 0),
                partners_count=_safe_int(request.POST.get("partners_count"), 0),
                attachment=request.FILES.get("attachment"),
                submitted_by=request.user,
            )
            messages.success(request, "Quarterly accomplishment report submitted.")
            return redirect("accomplishment_reports_list")

    return render(
        request,
        "dashboard/accomplishment_report_form.html",
        {
            "quarter_choices": AccomplishmentReport.Quarter.choices,
            "profile": profile,
            "current_year": timezone.now().year,
            # Live campus list from the admin-managed Campus table so the
            # cascading college/department selects have a source of truth.
            "campus_choices": [value for value, _label in get_campus_choices()],
        },
    )
