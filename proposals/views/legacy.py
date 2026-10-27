from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from accounts.decorators import admin_required
from ..models import (
    DocumentationPhoto,
    Proposal,
    ProposalAttachment,
    ProposalPhaseLog,
    ProposalProponent,
)
from ..legacy_forms import LegacyProposalForm
from .constants import LAST_BUILTIN_STEP_NO


@login_required
@admin_required
def admin_legacy_proposal_create(request):
    form = LegacyProposalForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=Proposal(created_by=request.user, is_legacy=True, current_step=LAST_BUILTIN_STEP_NO),
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            proposal = form.save()
            for position, user in enumerate(form.cleaned_data["assigned_proponents"]):
                profile = getattr(user, "profile", None)
                ProposalProponent.objects.create(
                    proposal=proposal,
                    user=user,
                    full_name=getattr(profile, "full_name", "") or user.get_full_name() or user.username,
                    email=user.email,
                    sort_order=position,
                )
            for file in request.FILES.getlist("attachments[]"):
                ProposalAttachment.objects.create(
                    proposal=proposal, file=file, category=ProposalAttachment.Category.OTHER,
                )
            # Photo documentation is what the public Gallery shows, so a legacy
            # import is the one chance to file it for work that predates the
            # system (the live equivalent is the terminal report step).
            caption = (form.cleaned_data.get("documentation_caption") or "").strip()[:200]
            for file in form.cleaned_data.get("documentation_photos") or []:
                DocumentationPhoto.objects.create(
                    proposal=proposal,
                    image=file,
                    caption=caption or proposal.title,
                    uploaded_by=request.user,
                )
            for phase, status in [
                (ProposalPhaseLog.Phase.MOA, proposal.moa_status),
                (ProposalPhaseLog.Phase.IMPLEMENTATION, proposal.implementation_status),
            ]:
                if status != "NOT_STARTED":
                    ProposalPhaseLog.objects.create(
                        proposal=proposal, phase=phase, to_status=status,
                        remarks="Imported by admin through Legacy Records Upload.",
                        changed_by=request.user,
                    )
        messages.success(request, f"Legacy activity '{proposal.title}' uploaded successfully.")
        return redirect("admin_dashboard")

    from accounts.models import Campus, College, Department

    # Live campus list from the admin-managed Campus table, preselected with
    # the current admin's own campus. College/department lists are scoped to
    # that campus so the selects start consistent with what the cascading
    # dropdowns would show after the user picks a campus.
    campuses = Campus.objects.all().order_by("name")

    profile = getattr(request.user, "profile", None)
    if request.method == "POST":
        # Re-rendering after a validation error: keep what the admin picked.
        selected_campus = (request.POST.get("campus") or "").strip()
        selected_college = (request.POST.get("college") or "").strip()
        selected_department = (request.POST.get("department") or "").strip()
    else:
        selected_campus = getattr(profile, "campus", "") or ""
        selected_college = getattr(profile, "college", "") or ""
        selected_department = getattr(profile, "department", "") or ""

    if selected_campus:
        colleges = College.objects.filter(campus__name=selected_campus).order_by("name")
        if selected_college:
            departments = Department.objects.filter(
                campus__name=selected_campus, college__name=selected_college
            ).order_by("name")
        else:
            departments = Department.objects.filter(
                campus__name=selected_campus, college__isnull=True
            ).order_by("name")
    else:
        colleges = College.objects.none()
        departments = Department.objects.none()

    month_choices = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    return render(
        request,
        "services/wizard/legacy_proposal_form.html",
        {
            "form": form,
            "campuses": campuses,
            "colleges": colleges,
            "departments": departments,
            "selected_campus": selected_campus,
            "selected_college": selected_college,
            "selected_department": selected_department,
            "month_choices": month_choices,
        }
    )
