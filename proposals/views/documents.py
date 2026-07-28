"""
Template downloads, file previews, and approval document handling.
"""

from copy import copy
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from pathlib import Path
from urllib.parse import quote
from urllib3 import request
import math
import mimetypes
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from ..docx_forms import build_extension_form_docx
from ..models import Proposal
from ..models import ProposalAttachment
from ..models import ProposalFinalDocument
from accounts.decorators import faculty_like_required
from accounts.decorators import role_required
from .constants import SDG_LIST
from .permissions import _can_edit, _can_view_proposal, _is_staff


def set_estimated_row_height(ws, cell_ref, text, chars_per_line=70, base_height=15):
    text = str(text or "")
    row = ws[cell_ref].row

    if not text.strip():
        ws.row_dimensions[row].height = base_height
        ws[cell_ref].alignment = Alignment(
            wrap_text=True,
            vertical="top",
            horizontal="left",
        )
        return

    raw_lines = text.split("\n")
    visual_lines = 0

    for line in raw_lines:
        visual_lines += max(1, math.ceil(len(line or "") / chars_per_line))

    ws.row_dimensions[row].height = max(base_height, visual_lines * base_height + 4)
    ws[cell_ref].alignment = Alignment(
        wrap_text=True,
        vertical="top",
        horizontal="left",
    )


def copy_cell_style(src_cell, dst_cell):
    if src_cell.has_style:
        dst_cell._style = copy(src_cell._style)
    if src_cell.font:
        dst_cell.font = copy(src_cell.font)
    if src_cell.fill:
        dst_cell.fill = copy(src_cell.fill)
    if src_cell.border:
        dst_cell.border = copy(src_cell.border)
    if src_cell.alignment:
        dst_cell.alignment = copy(src_cell.alignment)
    if src_cell.number_format:
        dst_cell.number_format = src_cell.number_format
    if src_cell.protection:
        dst_cell.protection = copy(src_cell.protection)


def copy_row_heights(ws, src_start_row, src_end_row, target_start_row):
    for offset, src_row in enumerate(range(src_start_row, src_end_row + 1)):
        target_row = target_start_row + offset
        src_dim = ws.row_dimensions[src_row]
        if src_dim.height is not None:
            ws.row_dimensions[target_row].height = src_dim.height


def copy_block(ws, src_start_row, src_end_row, src_start_col, src_end_col, target_start_row):
    row_offset = target_start_row - src_start_row

    for src_row in range(src_start_row, src_end_row + 1):
        for src_col in range(src_start_col, src_end_col + 1):
            src_cell = ws.cell(row=src_row, column=src_col)
            dst_cell = ws.cell(row=src_row + row_offset, column=src_col)
            dst_cell.value = src_cell.value
            copy_cell_style(src_cell, dst_cell)

    copy_row_heights(ws, src_start_row, src_end_row, target_start_row)


def copy_merged_ranges_for_block(ws, src_start_row, src_end_row, target_start_row):
    row_offset = target_start_row - src_start_row
    merges_to_add = []

    for merged in list(ws.merged_cells.ranges):
        min_col = merged.min_col
        min_row = merged.min_row
        max_col = merged.max_col
        max_row = merged.max_row

        if src_start_row <= min_row and max_row <= src_end_row:
            new_min_row = min_row + row_offset
            new_max_row = max_row + row_offset
            new_range = f"{get_column_letter(min_col)}{new_min_row}:{get_column_letter(max_col)}{new_max_row}"
            merges_to_add.append(new_range)

    for rng in merges_to_add:
        ws.merge_cells(rng)


def replicate_phase_blocks(ws, phase_titles, block_start_row, block_end_row, block_start_col, block_end_col, title_cell_col=1):
    if not phase_titles:
        return

    block_height = block_end_row - block_start_row + 1

    first_title_cell = ws.cell(row=block_start_row, column=title_cell_col)
    first_title_cell.value = phase_titles[0]
    set_estimated_row_height(ws, first_title_cell.coordinate, phase_titles[0], chars_per_line=70)

    if len(phase_titles) == 1:
        return

    for idx, phase_title in enumerate(phase_titles[1:], start=1):
        new_block_start = block_start_row + (idx * block_height)
        ws.insert_rows(new_block_start, amount=block_height)

        copy_block(ws, block_start_row, block_end_row, block_start_col, block_end_col, new_block_start)
        copy_merged_ranges_for_block(ws, block_start_row, block_end_row, new_block_start)

        title_cell = ws.cell(row=new_block_start, column=title_cell_col)
        title_cell.value = phase_title
        set_estimated_row_height(ws, title_cell.coordinate, phase_title, chars_per_line=70)


def replicate_table_blocks_only(ws, copies_needed, block_start_row, block_end_row, block_start_col, block_end_col):
    if copies_needed <= 1:
        return

    block_height = block_end_row - block_start_row + 1

    for idx in range(1, copies_needed):
        new_block_start = block_start_row + (idx * block_height)
        ws.insert_rows(new_block_start, amount=block_height)

        copy_block(ws, block_start_row, block_end_row, block_start_col, block_end_col, new_block_start)
        copy_merged_ranges_for_block(ws, block_start_row, block_end_row, new_block_start)


def get_best_sheet(workbook, preferred_names):
    for name in preferred_names:
        if name in workbook.sheetnames:
            return workbook[name]
    return workbook[workbook.sheetnames[0]]


def replicate_funding_blocks(ws, phase_titles):
    if not phase_titles:
        return

    block_start_row = 3
    block_end_row = 10
    block_start_col = 1
    block_end_col = 5
    block_height = block_end_row - block_start_row + 1

    ws["A3"] = phase_titles[0]

    if len(phase_titles) == 1:
        return

    for idx, phase_title in enumerate(phase_titles[1:], start=1):
        new_block_start = block_start_row + (idx * block_height)
        ws.insert_rows(new_block_start, amount=block_height)
        copy_block(ws, block_start_row, block_end_row, block_start_col, block_end_col, new_block_start)
        copy_merged_ranges_for_block(ws, block_start_row, block_end_row, new_block_start)
        ws.cell(row=new_block_start, column=1).value = phase_title


@login_required
@faculty_like_required
def download_work_plan_template(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_edit(request.user, proposal):
        messages.error(request, "You don't have access to this draft.")
        return redirect("services_home")

    template_dir = Path(__file__).resolve().parent / "template_files"

    if proposal.scope_type == "PROGRAM":
        template_path = template_dir / "program_work_plan_template.xlsx"
        preferred_sheet_names = ["Program Work Plan", "Work Plan", "Sheet1", "Sheet"]
        filename_prefix = "Program"
    else:
        template_path = template_dir / "project_work_plan_template.xlsx"
        preferred_sheet_names = ["Project Work Plan", "Work Plan", "Sheet1", "Sheet"]
        filename_prefix = "Project"

    if not template_path.exists():
        messages.error(request, "Work Plan template file not found.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=16)

    wb = load_workbook(template_path)
    ws = get_best_sheet(wb, preferred_sheet_names)

    title_value = proposal.title or ""

    sdg_name_map = {code: name for code, name in SDG_LIST}
    sdg_lines = []
    for item in proposal.sdg_links.all().order_by("sdg_code"):
        sdg_title = sdg_name_map.get(item.sdg_code, item.sdg_code)
        line = f"SDG {item.sdg_code} - {sdg_title}"
        if (item.explanation or "").strip():
            line += f": {item.explanation.strip()}"
        sdg_lines.append(line)
    sdg_value = "\n".join(sdg_lines)

    thrust_lines = []
    for item in proposal.thrust_links.all().order_by("id"):
        line = item.thrust_name or ""
        if (item.explanation or "").strip():
            line += f": {item.explanation.strip()}"
        if line.strip():
            thrust_lines.append(line)
    thrust_value = "\n".join(thrust_lines)

    gender_lines = []
    for item in proposal.gender_issue_links.all().order_by("id"):
        if item.issue_key == "others":
            if (item.other_text or "").strip():
                gender_lines.append(f"• Others:\n      {item.other_text.strip()}")
        else:
            gender_lines.append(f"• {item.issue_label}")
    gender_value = "\n".join(gender_lines)

    ws["A3"] = title_value
    ws["A5"] = sdg_value
    ws["A7"] = thrust_value
    ws["A9"] = gender_value

    set_estimated_row_height(ws, "A3", title_value, chars_per_line=90)
    set_estimated_row_height(ws, "A5", sdg_value, chars_per_line=70)
    set_estimated_row_height(ws, "A7", thrust_value, chars_per_line=70)
    set_estimated_row_height(ws, "A9", gender_value, chars_per_line=65)

    if proposal.scope_type == "PROGRAM":
        phase_titles = [
            prj.title for prj in proposal.program_projects.all().order_by("order", "id")
            if (prj.title or "").strip()
        ]

        replicate_phase_blocks(
            ws=ws,
            phase_titles=phase_titles,
            block_start_row=12,
            block_end_row=24,
            block_start_col=1,
            block_end_col=3,
            title_cell_col=1,
        )

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    safe_title = proposal.title or "Proposal"
    response["Content-Disposition"] = f'attachment; filename="{filename_prefix}_Work_Plan_{safe_title}.xlsx"'
    return response


@login_required
@faculty_like_required
def download_gantt_chart_template(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_edit(request.user, proposal):
        messages.error(request, "You don't have access to this draft.")
        return redirect("services_home")

    template_dir = Path(__file__).resolve().parent / "template_files"

    if proposal.scope_type == "PROGRAM":
        template_path = template_dir / "program_gantt_chart_template.xlsx"
        download_name = f"Program_Gantt_Chart_{proposal.title or 'Proposal'}.xlsx"
    else:
        template_path = template_dir / "project_gantt_chart_template.xlsx"
        download_name = f"Project_Gantt_Chart_{proposal.title or 'Proposal'}.xlsx"

    if not template_path.exists():
        messages.error(request, "Gantt Chart template file not found.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=16)

    if proposal.scope_type != "PROGRAM":
        return FileResponse(
            open(template_path, "rb"),
            as_attachment=True,
            filename=download_name,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    wb = load_workbook(template_path)
    ws = wb[wb.sheetnames[0]]

    replicate_table_blocks_only(
        ws=ws,
        copies_needed=proposal.program_projects.count(),
        block_start_row=3,
        block_end_row=9,
        block_start_col=1,
        block_end_col=5,
    )

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return response


@login_required
@faculty_like_required
def download_funding_template(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_edit(request.user, proposal):
        messages.error(request, "You don't have access to this draft.")
        return redirect("services_home")

    template_dir = Path(__file__).resolve().parent / "template_files"

    if proposal.scope_type == "PROGRAM":
        template_path = template_dir / "program_funding_template.xlsx"
        download_name = f"Program_Line-Item_Budget_{proposal.title or 'Proposal'}.xlsx"
    else:
        template_path = template_dir / "project_funding_template.xlsx"
        download_name = f"Project_Line-Item_Budget_{proposal.title or 'Proposal'}.xlsx"

    if not template_path.exists():
        messages.error(request, "Funding template file not found.")
        return redirect("proposal_wizard", proposal_id=proposal.id, step=17)

    wb = load_workbook(template_path)
    ws = wb["Work Plan Template"]

    if proposal.scope_type == "PROGRAM":
        phase_titles = [
            prj.title for prj in proposal.program_projects.all().order_by("order", "id")
            if (prj.title or "").strip()
        ]
        replicate_funding_blocks(ws, phase_titles)
    else:
        ws["A3"] = proposal.title or ""

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{download_name}"'
    return response


@login_required
def proposal_file_preview(request, proposal_id, file_type, attachment_id=None):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_proposal(request.user, proposal):
        raise Http404("You do not have access to this file.")

    file_field = None

    if file_type == "work_plan":
        file_field = proposal.work_plan_file
    elif file_type == "gantt_chart":
        file_field = proposal.gantt_chart_file
    elif file_type == "funding":
        file_field = proposal.funding_file
    elif file_type == "research_abstract":
        file_field = proposal.research_abstract_file
    elif file_type == "certificate":
        file_field = proposal.certificate_of_completion_file
    elif file_type == "attachment":
        if not attachment_id:
            raise Http404("Attachment not found.")
        attachment = get_object_or_404(ProposalAttachment, id=attachment_id, proposal=proposal)
        file_field = attachment.file
    else:
        raise Http404("Invalid file type.")

    if not file_field:
        raise Http404("File not found.")

    file_path = file_field.path
    filename = Path(file_path).name
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{quote(filename)}"'
    return response


@login_required
@faculty_like_required
def proposal_download_approved_docx(request, proposal_id):
    """
    Proponent downloads the final proposal DOCX for printing.

    Workflow rule:
      - When Director has cleared the proposal (READY_FOR_PRINTING),
        the FIRST download transitions it to FOR_SUBMISSION_AND_UPLOAD.
      - Subsequent downloads do not change status.
    """

    # Prefetch everything the DOCX builder is likely to access to prevent N+1 queries.
    proposal = get_object_or_404(
        Proposal.objects
        .select_related("created_by", "created_by__profile")
        .prefetch_related(
            "proponents", "proponents__user", "proponents__user__profile",
            "collaborators", "collaborators__user", "collaborators__user__profile",
            "program_projects",
            "sdg_links",
            "thrust_links",
            "gender_issue_links",
            "specific_objectives",
            "methodologies",
            "output_outcomes",
            "attachments",
        ),
        id=proposal_id
    )

    # Permission check WITHOUT extra DB hits.
    is_proponent = (
        request.user.id == proposal.created_by_id
        or any((pp.user_id == request.user.id) for pp in proposal.proponents.all())
    )
    if not is_proponent:
        messages.error(request, "You do not have permission to download this proposal.")
        return redirect("dashboard_redirect")

    allowed_statuses = {
        Proposal.ProposalStatus.READY_FOR_PRINTING,
        Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
        Proposal.ProposalStatus.APPROVED,
        Proposal.ProposalStatus.COMPLETED,
    }
    if proposal.proposal_status not in allowed_statuses:
        messages.error(request, "This proposal is not yet cleared for printing.")
        return redirect("dashboard_redirect")

    # Transition on first print/download (FAST PATH: one SQL UPDATE, no heavy save hooks)
    if proposal.proposal_status == Proposal.ProposalStatus.READY_FOR_PRINTING:
        with transaction.atomic():
            updated = Proposal.objects.filter(
                id=proposal.id,
                proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING,
            ).update(
                proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
                last_saved_at=timezone.now(),
            )
            if updated:
                proposal.proposal_status = Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD

    sdg_title_map = {code: name for code, name in SDG_LIST}

    # IMPORTANT: call as keyword-only to match your build_extension_form_docx signature
    data = build_extension_form_docx(proposal=proposal, sdg_title_map=sdg_title_map)

    filename_title = (proposal.title or proposal.research_title or "Proposal").strip()
    filename = f"{filename_title}.docx".replace("/", "-").replace("\\", "-")

    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
@faculty_like_required
def proposal_download_approval_document(request, proposal_id, document_type):
    """
    Download one released approval document and advance the proposal phase
    once the three approval documents have all been released and downloaded.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    is_proponent = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )
    if not (is_proponent or _is_staff(request.user)):
        messages.error(request, "You do not have permission to download this approval document.")
        return redirect("dashboard_redirect")

    doc_map = {
        "letter_of_award": ProposalFinalDocument.DocumentType.LETTER_OF_AWARD,
        "endorsement_for_approval": ProposalFinalDocument.DocumentType.ENDORSEMENT_FOR_APPROVAL,
        "extension_agreement": ProposalFinalDocument.DocumentType.EXTENSION_AGREEMENT,
    }
    final_doc_type = doc_map.get(document_type)
    if not final_doc_type:
        raise Http404("Invalid approval document type.")

    final_doc = proposal.final_documents.filter(document_type=final_doc_type).first()
    if not final_doc or not getattr(final_doc, "file", None):
        raise Http404("Approval document not found.")

    _mark_approval_documents_completed(proposal)

    file_path = final_doc.file.path
    filename = Path(file_path).name
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
    return response


@login_required
@faculty_like_required
@require_http_methods(["GET", "POST"])
def proposal_upload_signed_proposal(request, proposal_id):
    """
    Proponent uploads the signed proposal.

    Updated rule:
      - Upload does NOT auto-approve.
      - Staff verifies the signed proposal, then releases LOA / Endorsement / Extension Agreement.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    is_proponent = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )
    if not is_proponent:
        messages.error(request, "You do not have permission to upload files for this proposal.")
        return redirect("dashboard_redirect")

    if proposal.proposal_status != Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD:
        messages.error(request, "This proposal is not yet ready for signed upload.")
        return redirect("dashboard_redirect")

    if request.method == "POST":
        signed_file = request.FILES.get("signed_proposal_file")
        if not signed_file:
            messages.error(request, "Please choose a signed proposal file to upload.")
            return redirect("proposal_upload_signed_proposal", proposal_id=proposal.id)

        # Each upload becomes a new version; the previous one is kept for history.
        ProposalFinalDocument.add_version(
            proposal=proposal,
            document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
            file=signed_file,
            uploaded_by=request.user,
            remarks="",
            is_verified=False,  # STAFF will verify
        )

        # Optional: keep a single attachment link for easy download.
        ProposalAttachment.objects.filter(
            proposal=proposal,
            category=ProposalAttachment.Category.OTHER,
            label="Signed Proposal",
        ).delete()
        ProposalAttachment.objects.create(
            proposal=proposal,
            file=signed_file,
            category=ProposalAttachment.Category.OTHER,
            label="Signed Proposal",
        )

        proposal.last_saved_at = timezone.now()
        proposal.save(update_fields=["last_saved_at"])

        messages.success(request, "Signed proposal uploaded. Awaiting staff verification.")
        return redirect("dashboard_redirect")

    signed_doc = ProposalFinalDocument.objects.filter(
        proposal=proposal,
        document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
    ).first()

    return render(
        request,
        "services/post_approval/upload_signed_proposal.html",
        {"proposal": proposal, "signed_doc": signed_doc},
    )


@login_required
@role_required(["STAFF"])
@require_http_methods(["GET", "POST"])
def staff_release_approval_documents(request, proposal_id):
    """
    STAFF verifies signed proposal and uploads/releases the final approval documents:
      - Letter of Award
      - Endorsement for Approval
      - Extension Agreement

    Updated rule:
      - Proposal becomes APPROVED / CLAIMING only when ALL 3 are released.
      - This view does NOT mark the proposal COMPLETED (proponent "Claimed" should do that).
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if proposal.proposal_status not in {
        Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
        Proposal.ProposalStatus.APPROVED,
        Proposal.ProposalStatus.COMPLETED,
    }:
        messages.error(request, "This proposal is not yet ready for document release.")
        return redirect("dashboard_redirect")

    signed_doc = ProposalFinalDocument.objects.filter(
        proposal=proposal,
        document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
    ).first()

    if request.method == "POST":
        now = timezone.now()

        # Optional staff verification controls in your form:
        #   signed_action = "verify" | "reject"
        #   signed_remarks = text
        signed_action = (request.POST.get("signed_action") or "").strip().lower()
        signed_remarks = (request.POST.get("signed_remarks") or "").strip()

        if signed_doc and signed_action in {"verify", "reject"}:
            signed_doc.is_verified = (signed_action == "verify")
            signed_doc.remarks = signed_remarks
            signed_doc.save(update_fields=["is_verified", "remarks"])

        loa_file = request.FILES.get("letter_of_award_file")
        endorsement_file = request.FILES.get("endorsement_file")
        agreement_file = request.FILES.get("extension_agreement_file")

        uploaded_any = bool(loa_file or endorsement_file or agreement_file)

        # If staff is already uploading the final docs, treat that as an implicit verification step
        # (so you don't *have* to add new form controls immediately).
        if signed_doc and uploaded_any and not signed_doc.is_verified and signed_action != "reject":
            signed_doc.is_verified = True
            if signed_remarks:
                signed_doc.remarks = signed_remarks
            signed_doc.save(update_fields=["is_verified", "remarks"])

        # Enforce verification before releasing final docs
        verified_signed = ProposalFinalDocument.objects.filter(
            proposal=proposal,
            document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
            is_verified=True,
        ).first()
        if not verified_signed:
            messages.error(request, "Signed proposal is not yet VERIFIED by staff.")
            return redirect("staff_release_approval_documents", proposal_id=proposal.id)

        if loa_file:
            ProposalFinalDocument.add_version(
                proposal=proposal,
                document_type=ProposalFinalDocument.DocumentType.LETTER_OF_AWARD,
                file=loa_file,
                uploaded_by=request.user,
                remarks="",
                is_verified=True,
            )
            ProposalAttachment.objects.filter(
                proposal=proposal,
                category=ProposalAttachment.Category.OTHER,
                label="Letter of Award",
            ).delete()
            ProposalAttachment.objects.create(
                proposal=proposal,
                file=loa_file,
                category=ProposalAttachment.Category.OTHER,
                label="Letter of Award",
            )
            if not proposal.letter_of_award_released_at:
                proposal.letter_of_award_released_at = now

        if endorsement_file:
            ProposalFinalDocument.add_version(
                proposal=proposal,
                document_type=ProposalFinalDocument.DocumentType.ENDORSEMENT_FOR_APPROVAL,
                file=endorsement_file,
                uploaded_by=request.user,
                remarks="",
                is_verified=True,
            )
            ProposalAttachment.objects.filter(
                proposal=proposal,
                category=ProposalAttachment.Category.OTHER,
                label="Endorsement for Approval",
            ).delete()
            ProposalAttachment.objects.create(
                proposal=proposal,
                file=endorsement_file,
                category=ProposalAttachment.Category.OTHER,
                label="Endorsement for Approval",
            )
            if not proposal.endorsement_released_at:
                proposal.endorsement_released_at = now

        if agreement_file:
            ProposalFinalDocument.add_version(
                proposal=proposal,
                document_type=ProposalFinalDocument.DocumentType.EXTENSION_AGREEMENT,
                file=agreement_file,
                uploaded_by=request.user,
                remarks="",
                is_verified=True,
            )
            ProposalAttachment.objects.filter(
                proposal=proposal,
                category=ProposalAttachment.Category.OTHER,
                label="Extension Agreement",
            ).delete()
            ProposalAttachment.objects.create(
                proposal=proposal,
                file=agreement_file,
                category=ProposalAttachment.Category.OTHER,
                label="Extension Agreement",
            )
            if not proposal.extension_agreement_released_at:
                proposal.extension_agreement_released_at = now

        proposal.last_saved_at = now
        proposal.save(update_fields=[
            "letter_of_award_released_at",
            "endorsement_released_at",
            "extension_agreement_released_at",
            "last_saved_at",
        ])

        # Mark APPROVED / CLAIMING only when all 3 are released
        if (
            proposal.letter_of_award_released_at
            and proposal.endorsement_released_at
            and proposal.extension_agreement_released_at
        ):
            if proposal.proposal_status != Proposal.ProposalStatus.APPROVED:
                proposal.approve_proposal()
            messages.success(request, "All approval documents released. Proposal is now APPROVED / CLAIMING.")
        else:
            messages.success(request, "Documents updated. Release the remaining documents to mark Approved / Claiming.")

        return redirect("dashboard_redirect")

    loa_doc = ProposalFinalDocument.objects.filter(
        proposal=proposal,
        document_type=ProposalFinalDocument.DocumentType.LETTER_OF_AWARD,
    ).first()
    end_doc = ProposalFinalDocument.objects.filter(
        proposal=proposal,
        document_type=ProposalFinalDocument.DocumentType.ENDORSEMENT_FOR_APPROVAL,
    ).first()
    agr_doc = ProposalFinalDocument.objects.filter(
        proposal=proposal,
        document_type=ProposalFinalDocument.DocumentType.EXTENSION_AGREEMENT,
    ).first()

    context = {
        "proposal": proposal,
        "signed_doc": signed_doc,
        "loa_doc": loa_doc,
        "end_doc": end_doc,
        "agr_doc": agr_doc,
        "letter_of_award_released_at": proposal.letter_of_award_released_at,
        "endorsement_released_at": proposal.endorsement_released_at,
        "extension_agreement_released_at": proposal.extension_agreement_released_at,
    }
    return render(request, "services/post_approval/release_documents.html", context)


def _mark_approval_documents_completed(proposal):
    """
    Advance the proposal phase when the staff-released approval documents
    have been received/downloaded and the proposal is already approved.
    """
    if proposal.proposal_status != Proposal.ProposalStatus.APPROVED:
        return False

    if not (
        proposal.letter_of_award_released_at
        and proposal.endorsement_released_at
        and proposal.extension_agreement_released_at
    ):
        return False

    proposal.mark_proposal_completed()

    if getattr(proposal, "requires_moa", False):
        if proposal.moa_status in {Proposal.MOAStatus.NOT_STARTED, Proposal.MOAStatus.NOT_REQUIRED}:
            proposal.moa_status = Proposal.MOAStatus.DRAFT

    if proposal.status == Proposal.OverallStatus.DRAFT:
        proposal.status = Proposal.OverallStatus.ACTIVE

    proposal.save(update_fields=["moa_status", "status", "last_saved_at"])
    return True


@login_required
@faculty_like_required
@require_POST
def proposal_mark_claimed(request, proposal_id):
    """
    Proponent confirms they have received the released approval documents.

    Updated workflow:
      APPROVED / CLAIMING -> Proposal Completed (proposal phase)
      and then MOA phase starts (if requires_moa).
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    is_proponent = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )
    if not is_proponent:
        messages.error(request, "You do not have permission to claim this proposal.")
        return redirect("dashboard_redirect")

    if proposal.proposal_status != Proposal.ProposalStatus.APPROVED:
        messages.error(request, "This proposal is not yet in Approved / Claiming status.")
        return redirect("dashboard_redirect")

    # Enforce that all 3 approval documents were released by staff.
    if not (
        proposal.letter_of_award_released_at
        and proposal.endorsement_released_at
        and proposal.extension_agreement_released_at
    ):
        messages.error(request, "Approval documents are not yet fully released.")
        return redirect("dashboard_redirect")

    _mark_approval_documents_completed(proposal)

    messages.success(request, "Proposal claimed. MOA phase is now started.")
    return redirect("dashboard_redirect")
