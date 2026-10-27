"""
Implementation tracker and proposal document storage.
"""
import logging

from pathlib import Path
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from ..models import Proposal
from ..models import ProposalCommentSummary
from ..models import ProposalFinalDocument
from ..models import ProposalPhaseLog
from ..models import DocumentationPhoto
from .permissions import _can_manage_phase, _can_view_proposal

logger = logging.getLogger(__name__)

#: Documentation photos are shown on a public page, so only real images of a
#: sane size are accepted. A phone photo is typically 2-6 MB.
DOCUMENTATION_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
}
DOCUMENTATION_IMAGE_MAX_BYTES = 12 * 1024 * 1024

#: Photo documentation is part of the terminal report ("Final Evaluation and
#: Documentation", appendix E.13), so it opens once the report is being filed —
#: at the progress-report stage and everything after it.
DOCUMENTATION_STAGES = {
    "TERMINAL_REPORT",
    "MONITORING",
    "REVISION",
    "COMPLETED",
}


def documentation_is_open(proposal):
    """Whether photo documentation can be filed yet.

    Either the activity has reached the stage where the terminal report is
    filed, or the report is already uploaded — an activity can sit at an
    earlier stage and still have its report on file, and its photos belong
    with the report.
    """
    if proposal.implementation_status in DOCUMENTATION_STAGES:
        return True
    return proposal.final_documents.filter(
        document_type="REPORT_FINAL"
    ).exists()


@login_required
def proposal_implementation_tracker(request, proposal_id):
    """
    Stage tracker for the Implementation phase of a proposal.

    Proponents and staff can view the tracker. Only Staff/Director can
    advance or send back a stage. Proponents can upload the
    post-extension/progress report, final evaluation documentation, and
    (once completed) the certificate of completion.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_proposal(request.user, proposal):
        messages.error(request, "You don't have access to this proposal.")
        return redirect("dashboard_redirect")

    # If a previously completed MOA has not yet initialized implementation,
    # start it here so the user lands directly in process step 7.
    if (
        proposal.requires_moa
        and proposal.moa_status == Proposal.MOAStatus.COMPLETED
        and proposal.implementation_status in {
            Proposal.ImplementationStatus.NOT_STARTED,
            Proposal.ImplementationStatus.PREPARATION,
        }
    ):
        previous_status = proposal.implementation_status
        proposal.mark_implementation_ongoing()
        ProposalPhaseLog.objects.create(
            proposal=proposal,
            phase=ProposalPhaseLog.Phase.IMPLEMENTATION,
            from_status=previous_status,
            to_status=proposal.implementation_status,
            remarks="MOA completed; implementation tracker initialized at step 7.",
            changed_by=request.user if request.user.is_authenticated else None,
        )

    can_manage = _can_manage_phase(request.user, proposal)
    is_proponent = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )
    can_upload = is_proponent or can_manage

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        remarks = (request.POST.get("remarks") or "").strip()

        if action in {
            "upload_progress",
            "upload_terminal",
            "upload_certificate",
            "upload_documentation",
            "remove_documentation",
            "save_documentation_caption",
        }:
            if not can_upload:
                messages.error(request, "You do not have permission to upload documents here.")
                return redirect("proposal_implementation_tracker", proposal_id=proposal.id)

            if action == "upload_progress":
                report_file = request.FILES.get("report_file")
                if not report_file:
                    messages.error(request, "Please choose a file to upload.")
                else:
                    ProposalFinalDocument.add_version(
                        proposal=proposal,
                        document_type=ProposalFinalDocument.DocumentType.REPORT_PARTIAL,
                        file=report_file,
                        uploaded_by=request.user,
                        remarks=remarks,
                        is_verified=False,
                    )
                    messages.success(request, "Post activity / progress report uploaded.")

            elif action == "upload_terminal":
                report_file = request.FILES.get("report_file")
                if not report_file:
                    messages.error(request, "Please choose a file to upload.")
                else:
                    ProposalFinalDocument.add_version(
                        proposal=proposal,
                        document_type=ProposalFinalDocument.DocumentType.REPORT_FINAL,
                        file=report_file,
                        uploaded_by=request.user,
                        remarks=remarks,
                        is_verified=False,
                    )
                    messages.success(request, "Terminal report uploaded.")

            elif action == "upload_documentation":
                # Appendix E.13 of the terminal report: "photo documentation in
                # action with caption". The proponent files the photos together
                # with the report, and the public Gallery shows them.
                if not documentation_is_open(proposal):
                    messages.error(
                        request,
                        "Photo documentation is submitted with the terminal report, "
                        "at the Final Evaluation and Documentation stage.",
                    )
                    return redirect("proposal_implementation_tracker", proposal_id=proposal.id)

                photos = request.FILES.getlist("documentation_photos")
                if not photos:
                    messages.error(request, "Please choose at least one photo to upload.")
                else:
                    # Alpine renders one caption box per chosen photo, so the
                    # captions arrive as an ordered list matching ``photos``.
                    # A single shared caption is also accepted — that is what
                    # the legacy-import form sends for a whole batch — and
                    # without JavaScript each photo is saved uncaptioned, to be
                    # captioned afterwards in the list below.
                    captions = request.POST.getlist("documentation_captions")
                    shared = (request.POST.get("documentation_caption") or "").strip()
                    if not captions and shared:
                        captions = [shared] * len(photos)
                    saved = 0
                    for index, photo_file in enumerate(photos):
                        content_type = (getattr(photo_file, "content_type", "") or "").lower()
                        if content_type not in DOCUMENTATION_IMAGE_TYPES:
                            messages.error(
                                request,
                                f'"{photo_file.name}" is not a JPEG, PNG, WebP, or GIF image.',
                            )
                            continue
                        if photo_file.size > DOCUMENTATION_IMAGE_MAX_BYTES:
                            messages.error(
                                request,
                                f'"{photo_file.name}" is larger than 12 MB.',
                            )
                            continue
                        caption = captions[index].strip()[:200] if index < len(captions) else ""
                        DocumentationPhoto.objects.create(
                            proposal=proposal,
                            image=photo_file,
                            caption=caption,
                            uploaded_by=request.user,
                        )
                        saved += 1
                    if saved:
                        messages.success(
                            request,
                            f"{saved} documentation photo{'s' if saved != 1 else ''} "
                            "added. They appear in the public Gallery.",
                        )

            elif action == "save_documentation_caption":
                # Captions are part of the report, so they must stay editable
                # after the upload (a wrong caption is a documentation error).
                photo = get_object_or_404(
                    DocumentationPhoto,
                    pk=request.POST.get("photo_id"),
                    proposal=proposal,
                )
                photo.caption = (request.POST.get("caption") or "").strip()[:200]
                photo.save(update_fields=["caption"])
                messages.success(request, "Caption saved.")

            elif action == "remove_documentation":
                # ``can_upload`` already limited this to the proposal's own
                # proponents and the staff who manage it, so a mistake (or a
                # photo that should not be public) can be undone right here.
                photo = get_object_or_404(
                    DocumentationPhoto,
                    pk=request.POST.get("photo_id"),
                    proposal=proposal,
                )
                photo.delete()
                messages.success(request, "Documentation photo removed.")

            elif action == "upload_certificate":
                certificate_file = request.FILES.get("certificate_file")
                if not certificate_file:
                    messages.error(request, "Please choose a file to upload.")
                else:
                    proposal.certificate_of_completion_file = certificate_file
                    proposal.save(update_fields=["certificate_of_completion_file", "last_saved_at"])
                    messages.success(request, "Certificate of completion uploaded.")

            return redirect("proposal_implementation_tracker", proposal_id=proposal.id)

        # Everything below changes the Implementation stage -> Staff/Director only.
        if not can_manage:
            messages.error(request, "Only Staff or the Director can update the implementation stage.")
            return redirect("proposal_implementation_tracker", proposal_id=proposal.id)

        previous_status = proposal.implementation_status

        if action == "advance":
            if proposal.implementation_status == Proposal.ImplementationStatus.COMPLETED:
                messages.info(request, "Implementation is already completed.")
            elif proposal.advance_implementation():
                ProposalPhaseLog.objects.create(
                    proposal=proposal,
                    phase=ProposalPhaseLog.Phase.IMPLEMENTATION,
                    from_status=previous_status,
                    to_status=proposal.implementation_status,
                    remarks=remarks,
                    changed_by=request.user,
                )
                messages.success(
                    request,
                    f"Implementation moved to '{proposal.get_implementation_status_display()}'.",
                )
            else:
                messages.info(request, "Implementation is already at its final stage.")

        elif action == "back":
            if proposal.regress_implementation():
                ProposalPhaseLog.objects.create(
                    proposal=proposal,
                    phase=ProposalPhaseLog.Phase.IMPLEMENTATION,
                    from_status=previous_status,
                    to_status=proposal.implementation_status,
                    remarks=remarks or "Sent back to the previous stage.",
                    changed_by=request.user,
                )
                messages.success(
                    request,
                    f"Implementation sent back to '{proposal.get_implementation_status_display()}'.",
                )
            else:
                messages.info(request, "Implementation is already at its first stage.")

        else:
            messages.error(request, "Unknown action.")

        return redirect("proposal_implementation_tracker", proposal_id=proposal.id)

    progress_versions = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.REPORT_PARTIAL
    ).select_related("uploaded_by").order_by("-version")
    progress_doc = progress_versions.filter(is_current=True).first() or progress_versions.first()

    terminal_versions = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.REPORT_FINAL
    ).select_related("uploaded_by").order_by("-version")
    terminal_doc = terminal_versions.filter(is_current=True).first() or terminal_versions.first()

    documentation_photos = proposal.documentation_photos.select_related("uploaded_by")

    context = {
        "proposal": proposal,
        "steps": proposal.implementation_step_states(),
        "can_manage": can_manage,
        "can_upload": can_upload,
        "is_proponent": is_proponent,
        "progress_doc": progress_doc,
        "progress_versions": progress_versions,
        "terminal_doc": terminal_doc,
        "terminal_versions": terminal_versions,
        "documentation_photos": documentation_photos,
        "documentation_photo_count": documentation_photos.count(),
        "can_submit_documentation": can_upload and documentation_is_open(proposal),
        "logs": proposal.phase_logs.filter(phase=ProposalPhaseLog.Phase.IMPLEMENTATION),
        "is_first_stage": proposal.implementation_status in {
            Proposal.ImplementationStatus.NOT_STARTED,
            Proposal.ImplementationStatus.PREPARATION,
            Proposal.ImplementationStatus.IMPLEMENTATION,
        },
        "is_final_stage": proposal.implementation_status == Proposal.ImplementationStatus.COMPLETED,
    }
    return render(request, "services/implementation/implementation_tracker.html", context)


@login_required
def proposal_storage(request, proposal_id):
    proposal = get_object_or_404(
        Proposal.objects
        .select_related("created_by", "created_by__profile")
        .prefetch_related(
            "proponents",
            "proponents__user",
            "proponents__user__profile",
            "attachments",
            "final_documents",
        ),
        id=proposal_id,
    )

    profile = getattr(request.user, "profile", None)
    role = (getattr(profile, "role", "") or "").upper()
    is_staff = bool(getattr(request.user, "is_staff", False) or role in {"STAFF", "DIRECTOR", "ADMIN"})

    is_proponent = (
        request.user.id == proposal.created_by_id
        or proposal.proponents.filter(user=request.user).exists()
    )

    if not (is_staff or is_proponent):
        messages.error(request, "You do not have permission to view this proposal storage.")
        return redirect("dashboard_redirect")

    def field_url(field_name: str):
        f = getattr(proposal, field_name, None)
        if not f:
            return None
        try:
            return f.url
        except (ValueError, FileNotFoundError):
            # No file associated, or missing from storage.
            return None
        except Exception:
            logger.exception("Could not resolve URL for %s.", field_name)
            return None

    def file_name_from_path(url_or_name: str | None) -> str:
        if not url_or_name:
            return ""
        return Path(str(url_or_name)).name

    signed_doc = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL
    ).first()

    loa_doc = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.LETTER_OF_AWARD
    ).first()

    end_doc = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.ENDORSEMENT_FOR_APPROVAL
    ).first()

    agr_doc = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.EXTENSION_AGREEMENT
    ).first()

    attachment_rows = [
        {
            "label": "Work Plan",
            "filename": file_name_from_path(field_url("work_plan_file")),
            "file_url": field_url("work_plan_file"),
        },
        {
            "label": "Gantt Chart",
            "filename": file_name_from_path(field_url("gantt_chart_file")),
            "file_url": field_url("gantt_chart_file"),
        },
        {
            "label": "Line-item Budget",
            "filename": file_name_from_path(field_url("funding_file")),
            "file_url": field_url("funding_file"),
        },
        {
            "label": "Abstract (optional)",
            "filename": file_name_from_path(field_url("research_abstract_file")),
            "file_url": field_url("research_abstract_file"),
        },
        {
            "label": "Certificate of Completion (optional)",
            "filename": file_name_from_path(field_url("certificate_of_completion_file")),
            "file_url": field_url("certificate_of_completion_file"),
        },
    ]

    approval_rows = [
        {
            "label": "Letter of Award",
            "filename": file_name_from_path(getattr(getattr(loa_doc, "file", None), "name", None)),
            "file_url": getattr(getattr(loa_doc, "file", None), "url", None) if loa_doc else None,
            "download_url": reverse("proposal_download_approval_document", args=[proposal.id, "letter_of_award"]),
        },
        {
            "label": "Endorsement for Approval",
            "filename": file_name_from_path(getattr(getattr(end_doc, "file", None), "name", None)),
            "file_url": getattr(getattr(end_doc, "file", None), "url", None) if end_doc else None,
            "download_url": reverse("proposal_download_approval_document", args=[proposal.id, "endorsement_for_approval"]),
        },
        {
            "label": "Extension Agreement",
            "filename": file_name_from_path(getattr(getattr(agr_doc, "file", None), "name", None)),
            "file_url": getattr(getattr(agr_doc, "file", None), "url", None) if agr_doc else None,
            "download_url": reverse("proposal_download_approval_document", args=[proposal.id, "extension_agreement"]),
        },
    ]

    other_files = []
    for a in proposal.attachments.all().order_by("id"):
        file_url = None
        filename = ""
        try:
            file_url = a.file.url
            filename = Path(a.file.name).name
        except (ValueError, FileNotFoundError):
            # Attachment row exists but the file is gone; skip it.
            logger.debug("Attachment %s has no reachable file.", a.pk)
        except Exception:
            logger.exception("Could not resolve URL for attachment %s.", a.pk)
        if file_url:
            other_files.append({
                "label": a.label or a.get_category_display() or "Attachment",
                "filename": filename,
                "file_url": file_url,
            })

    review_history = []
    for round_obj in proposal.review_rounds.order_by("-round_no"):
        summary = ProposalCommentSummary.objects.filter(
            proposal=proposal,
            review_round=round_obj,
        ).order_by("-created_at").first()

        review_history.append({
            "round_no": round_obj.round_no,
            "created_at": round_obj.created_at,
            "is_closed": round_obj.is_closed,
            "ready_for_staff_summary": round_obj.ready_for_staff_summary,
            "department_review_done": round_obj.department_review_done,
            "campus_review_done": round_obj.campus_review_done,
            "director_review_done": round_obj.director_review_done,
            "evaluator_review_done": round_obj.evaluator_review_done,
            "view_url": reverse("proposal_version_summary", args=[proposal.id, round_obj.round_no]),
        })

    uploaded_files = [
        {
            "label": "Extension Proposal (Approved DOCX)",
            "filename": f"{(proposal.title or proposal.research_title or 'Proposal').strip()}.docx",
            "file_url": reverse("proposal_download_approved_docx", args=[proposal.id]),
        }
    ]

    if signed_doc and getattr(signed_doc, "file", None):
        uploaded_files.append({
            "label": "Signed Proposal",
            "filename": Path(signed_doc.file.name).name,
            "file_url": signed_doc.file.url,
        })

    uploaded_files.extend([
        *attachment_rows,
        *approval_rows,
        *other_files,
    ])

    can_claim = (
        proposal.proposal_status == Proposal.ProposalStatus.APPROVED
        and bool(loa_doc and getattr(loa_doc, "file", None))
        and bool(end_doc and getattr(end_doc, "file", None))
        and bool(agr_doc and getattr(agr_doc, "file", None))
        and is_proponent
    )

    moa_versions = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.MOA
    ).select_related("uploaded_by").order_by("-version")
    moa_doc = moa_versions.filter(is_current=True).first() or moa_versions.first()

    progress_versions = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.REPORT_PARTIAL
    ).select_related("uploaded_by").order_by("-version")

    terminal_versions = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.REPORT_FINAL
    ).select_related("uploaded_by").order_by("-version")

    context = {
        "proposal": proposal,
        "signed_doc": signed_doc,
        "moa_doc": moa_doc,
        "moa_versions": moa_versions,
        "progress_versions": progress_versions,
        "terminal_versions": terminal_versions,
        "approval_rows": approval_rows,
        "attachment_rows": attachment_rows,
        "other_files": other_files,
        "review_history": review_history,
        "uploaded_files": uploaded_files,
        "can_claim": can_claim,
    }
    return render(request, "services/post_approval/proposal_storage.html", context)
