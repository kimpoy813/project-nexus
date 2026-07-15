# -----------------------------------------------------------------------
# ADD THIS TO: your moa app's views.py (e.g. moa/views.py)
# -----------------------------------------------------------------------
# pip install docxtpl
# -----------------------------------------------------------------------

import io
import os

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from docxtpl import DocxTemplate

from proposals.models import Proposal  # adjust import to your app layout
from .forms import MOAUploadForm
from .models import MOADocument

# Resolves to <this app's directory>/templates_docx/moa_template.docx
# regardless of where the project root is — no manual path juggling needed.
MOA_TEMPLATE_PATH = os.path.join(
    apps.get_app_config("moa").path, "templates_docx", "moa_template.docx"
)


@login_required
def generate_moa_draft(request, proposal_id):
    """
    Renders moa_template.docx with data pulled from the Proposal,
    and returns it as a downloadable .docx for the coordinator to
    finalize offline in Word.
    """
    proposal = get_object_or_404(Proposal, pk=proposal_id)

    doc = DocxTemplate(MOA_TEMPLATE_PATH)

    signing_date = getattr(proposal, "moa_signing_date", None)

    ispsc_items = proposal.ispsc_responsibilities_list or [
        "Plan and implement the extension program.",
        "Provide resource persons/lecturers relevant to the project.",
        "Facilitate issuance of certificates to participants and resource persons.",
        "Monitor and supervise implementation to ensure program objectives are met.",
        "Prepare and provide copies of the terminal report to both parties.",
    ]
    partner_items = proposal.partner_responsibilities_list or [
        "Provide the venue and necessary logistics for the activity.",
        "Shoulder food and other necessary monetary expenses for the activity.",
        "Allocate available time for the purpose of the program.",
        "Ensure participation of the target number of beneficiaries.",
        "Assist in disseminating information regarding the activity.",
    ]

    def lettered(items):
        letters = "abcdefghijklmnopqrstuvwxyz"
        return "\n".join(f"{letters[i]}. {item}" for i, item in enumerate(items))

    context = {
        "campus_name": proposal.campus.name,
        "day_of_month": signing_date.strftime("%d") if signing_date else "____",
        "month_year": signing_date.strftime("%B %Y") if signing_date else "____",
        "moa_year": signing_date.strftime("%Y") if signing_date else "____",
        "venue": proposal.venue or proposal.campus.municipality,
        "ispsc_president_name": proposal.college_signatory_name or "____",
        "partner_name": proposal.partner_agency,
        "partner_org_type": proposal.partner_org_type or "Local Government Unit",
        "partner_location": proposal.partner_location or proposal.venue,
        "partner_address": proposal.partner_address,
        "partner_rep_name": proposal.partner_rep_name,
        "partner_rep_position": proposal.partner_rep_position,
        "extension_focus_area": proposal.extension_focus_area or proposal.title,
        "partner_rationale": proposal.partner_rationale or
            "the value of this collaboration to the community it serves",
        "project_title": proposal.title,
        "project_description": proposal.project_description or
            "the implementation of a training/seminar program",
        "beneficiaries": proposal.beneficiaries or "the identified target participants",
        "program_name": proposal.program.name if hasattr(proposal, "program") else proposal.department.name,
        "department": proposal.department.name,
        "ispsc_responsibilities": lettered(ispsc_items),
        "partner_responsibilities": lettered(partner_items),
        "effectivity_period": proposal.effectivity_period or
            f"{proposal.start_date.year}-{proposal.end_date.year}",
        "dean_name": proposal.dean_name or "____",
        "director_name": proposal.director.get_full_name() if getattr(proposal, "director", None) else "____",
        "proponent_name": proposal.coordinator.get_full_name(),
    }
    doc.render(context)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    # Log this generation as a version in the MOA history
    MOADocument.objects.create(
        proposal=proposal,
        file="",  # generated draft isn't stored server-side until uploaded back
        status="draft_generated",
        uploaded_by=request.user,
    )

    filename = f"MOA_Draft_{proposal.title[:40].replace(' ', '_')}.docx"
    return FileResponse(buffer, as_attachment=True, filename=filename)


@login_required
def upload_moa(request, proposal_id):
    """
    Coordinator uploads the finalized/signed MOA. Creates a new
    MOADocument version and routes it into the review chain.
    """
    proposal = get_object_or_404(Proposal, pk=proposal_id)

    if request.method == "POST":
        form = MOAUploadForm(request.POST, request.FILES)
        if form.is_valid():
            moa_doc = form.save(commit=False)
            moa_doc.proposal = proposal
            moa_doc.uploaded_by = request.user
            moa_doc.status = "uploaded"
            moa_doc.save()
            messages.success(request, "MOA uploaded successfully and sent for review.")
            return redirect("moa_detail", proposal_id=proposal.id)
    else:
        form = MOAUploadForm()

    return render(request, "moa/upload_moa.html", {
        "form": form,
        "proposal": proposal,
    })


@login_required
def moa_detail(request, proposal_id):
    """
    Shows MOA version history for a proposal — used by
    Coordinator/Director/Evaluator roles to review and comment.
    """
    proposal = get_object_or_404(Proposal, pk=proposal_id)
    moa_documents = proposal.moa_documents.all()  # ordered by -version via Meta

    return render(request, "moa/moa_detail.html", {
        "proposal": proposal,
        "moa_documents": moa_documents,
    })


@login_required
def review_moa(request, moa_id):
    """
    Reviewer (Coordinator/Director/Evaluator) approves, requests
    revisions, or finalizes a specific MOA version.
    """
    moa_doc = get_object_or_404(MOADocument, pk=moa_id)

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "")

        if action == "request_revisions":
            moa_doc.status = "revisions_requested"
        elif action == "finalize":
            moa_doc.status = "finalized"
        elif action == "mark_under_review":
            moa_doc.status = "under_review"

        moa_doc.reviewer_comment = comment
        moa_doc.save()
        messages.success(request, "MOA status updated.")

    return redirect("moa_detail", proposal_id=moa_doc.proposal.id)
