from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import admin_required
from ..models import Proposal, ProposalAttachment
from .helpers import _to_int


@login_required
@admin_required
def admin_legacy_proposal_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        extension_type = request.POST.get("extension_type", "")
        scope_type = request.POST.get("scope_type", "")
        campus = request.POST.get("campus", "")
        college = request.POST.get("college", "")
        department = request.POST.get("department", "")
        implementing_agency = (request.POST.get("implementing_agency") or "").strip()
        beneficiaries_who = (request.POST.get("beneficiaries_who") or "").strip()
        beneficiaries_count = _to_int(request.POST.get("beneficiaries_count"))
        estimated_month = request.POST.get("estimated_month", "")
        estimated_year = _to_int(request.POST.get("estimated_year"))
        extension_venue = (request.POST.get("extension_venue") or "").strip()
        proposal_status = request.POST.get("proposal_status", Proposal.ProposalStatus.APPROVED)

        if not title:
            messages.error(request, "Proposal title is required.")
        else:
            proposal = Proposal.objects.create(
                created_by=request.user,
                title=title,
                extension_type=extension_type,
                scope_type=scope_type,
                campus=campus,
                college=college,
                department=department,
                implementing_agency=implementing_agency,
                beneficiaries_who=beneficiaries_who,
                beneficiaries_count=beneficiaries_count,
                estimated_month=estimated_month,
                estimated_year=estimated_year,
                extension_venue=extension_venue,
                proposal_status=proposal_status,
                is_legacy=True,
                current_step=19,
            )

            # Handle files
            if request.FILES.get("legacy_proposal_file"):
                proposal.legacy_proposal_file = request.FILES["legacy_proposal_file"]
            if request.FILES.get("moa_draft_file"):
                proposal.moa_draft_file = request.FILES["moa_draft_file"]
                proposal.moa_status = Proposal.MOAStatus.COMPLETED
            if request.FILES.get("certificate_of_completion_file"):
                proposal.certificate_of_completion_file = request.FILES["certificate_of_completion_file"]
                proposal.implementation_status = Proposal.ImplementationStatus.COMPLETED
            proposal.save()

            # Handle additional attachments
            attachments = request.FILES.getlist("attachments[]")
            for f in attachments:
                ProposalAttachment.objects.create(
                    proposal=proposal,
                    file=f,
                    category=ProposalAttachment.Category.OTHER,
                )

            messages.success(request, f"Legacy proposal '{title}' uploaded successfully.")
            return redirect("admin_dashboard")

    from accounts.models import Campus, College, Department
    campuses = Campus.objects.all().order_by("name")
    colleges = College.objects.all().order_by("name")
    departments = Department.objects.all().order_by("name")

    month_choices = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    return render(
        request,
        "services/wizard/legacy_proposal_form.html",
        {
            "extension_type_choices": Proposal.ExtensionType.choices,
            "scope_type_choices": Proposal.ScopeType.choices,
            "proposal_status_choices": Proposal.ProposalStatus.choices,
            "campuses": campuses,
            "colleges": colleges,
            "departments": departments,
            "month_choices": month_choices,
        }
    )
