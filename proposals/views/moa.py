"""
MOA drafting wizard, tracker, and uploads.
"""

from urllib3 import request
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from ..forms import MOAAttachmentsForm
from ..forms import MOADraftForm
from ..forms import MOAPartiesForm
from ..forms import MOATermsForm
from ..moa_docx import build_moa_document
from ..moa_forms import MOASubmissionForm
from ..models import MOANotification
from ..models import MOASubmission
from ..models import Proposal
from ..models import ProposalAttachment
from ..models import ProposalFinalDocument
from ..models import ProposalPhaseLog
from accounts.decorators import faculty_like_required
from .constants import MOA_DRAFT_CHECKBOX_FIELDS, MOA_DRAFT_TEXT_FIELDS, MOA_STEP_LABELS
from .helpers import _notify_proponent
from .permissions import _can_edit, _can_manage_phase, _can_view_proposal, _is_staff


def build_moa_wizard_steps(current_step):
    steps = []
    for item in MOA_STEP_LABELS:
        no = item["no"]
        if no == current_step:
            state = "current"
        elif no < current_step:
            state = "completed"
        else:
            state = "upcoming"
        steps.append({**item, "state": state})
    return steps


def _build_moa_wizard_context(proposal, step):
    total_steps = len(MOA_STEP_LABELS)
    progress = int(((step - 1) / total_steps) * 100) if total_steps else 0
    return {
        "proposal": proposal,
        "step": step,
        "total_steps": total_steps,
        "progress": progress,
        "wizard_steps": build_moa_wizard_steps(step),
    }


def _set_moa_status_if_possible(proposal, status_value):
    """
    Safe setter for MOA status so the view won't crash if the model field/value
    names differ slightly in your current branch.
    """
    if hasattr(proposal, "moa_status"):
        proposal.moa_status = status_value
        proposal.save(update_fields=["moa_status"])


def _save_moa_step_1(proposal, cleaned):
    changed_fields = []

    for field_name, value in [
        ("moa_title", cleaned.get("moa_title")),
        ("moa_reference_no", cleaned.get("moa_reference_no")),
        ("moa_start_date", cleaned.get("moa_start_date")),
        ("moa_end_date", cleaned.get("moa_end_date")),
        ("moa_purpose", cleaned.get("purpose")),
        ("moa_background", cleaned.get("background")),
    ]:
        if hasattr(proposal, field_name):
            setattr(proposal, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        proposal.save(update_fields=changed_fields)


def _save_moa_step_2(proposal, cleaned):
    changed_fields = []

    for field_name, value in [
        ("moa_party_one_name", cleaned.get("party_one_name")),
        ("moa_party_one_representative", cleaned.get("party_one_representative")),
        ("moa_party_two_name", cleaned.get("party_two_name")),
        ("moa_party_two_representative", cleaned.get("party_two_representative")),
        ("moa_signatories_notes", cleaned.get("signatories_notes")),
    ]:
        if hasattr(proposal, field_name):
            setattr(proposal, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        proposal.save(update_fields=changed_fields)


def _save_moa_step_3(proposal, cleaned):
    changed_fields = []

    for field_name, value in [
        ("moa_obligations", cleaned.get("obligations")),
        ("moa_deliverables", cleaned.get("deliverables")),
        ("moa_confidentiality", cleaned.get("confidentiality")),
    ]:
        if hasattr(proposal, field_name):
            setattr(proposal, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        proposal.save(update_fields=changed_fields)


def _save_moa_step_4(proposal, request):
    changed_fields = []

    moa_file = request.FILES.get("moa_file")
    if moa_file and hasattr(proposal, "moa_draft_file"):
        proposal.moa_draft_file = moa_file
        changed_fields.append("moa_draft_file")

    if changed_fields:
        proposal.save(update_fields=changed_fields)

    if hasattr(ProposalAttachment, "Category"):
        moa_category = getattr(ProposalAttachment.Category, "MOA", None)
        other_category = getattr(ProposalAttachment.Category, "OTHER", None)
    else:
        moa_category = None
        other_category = None

    for uploaded in request.FILES.getlist("supporting_docs"):
        kwargs = {
            "proposal": proposal,
            "file": uploaded,
        }
        if moa_category is not None:
            kwargs["category"] = moa_category
        elif other_category is not None:
            kwargs["category"] = other_category

        ProposalAttachment.objects.create(**kwargs)


@login_required
@faculty_like_required
def proposal_moa_step(request, proposal_id, step):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    step = int(step)
    if step < 1:
        step = 1
    if step > 4:
        step = 4

    form_map = {
        1: MOADraftForm,
        2: MOAPartiesForm,
        3: MOATermsForm,
        4: MOAAttachmentsForm,
    }
    form_class = form_map[step]

    if request.method == "POST":
        form = form_class(request.POST, request.FILES if step == 4 else None)
        if form.is_valid():
            if step == 1:
                _save_moa_step_1(proposal, form.cleaned_data)
            elif step == 2:
                _save_moa_step_2(proposal, form.cleaned_data)
            elif step == 3:
                _save_moa_step_3(proposal, form.cleaned_data)
            elif step == 4:
                _save_moa_step_4(proposal, request)
                _set_moa_status_if_possible(proposal, getattr(Proposal.MOAStatus, "DRAFT", "DRAFT"))

            if step < 4:
                messages.success(request, "MOA step saved. Continue to the next part.")
                return redirect("proposal_moa_step", proposal_id=proposal.id, step=step + 1)

            messages.success(request, "MOA draft completed and queued for Staff review.")
            return redirect("proposal_moa_summary", proposal_id=proposal.id)
    else:
        initial = {}

        if step == 1:
            for form_field, model_field in [
                ("moa_title", "moa_title"),
                ("moa_reference_no", "moa_reference_no"),
                ("moa_start_date", "moa_start_date"),
                ("moa_end_date", "moa_end_date"),
                ("purpose", "moa_purpose"),
                ("background", "moa_background"),
            ]:
                if hasattr(proposal, model_field):
                    initial[form_field] = getattr(proposal, model_field, None)

        elif step == 2:
            for form_field, model_field in [
                ("party_one_name", "moa_party_one_name"),
                ("party_one_representative", "moa_party_one_representative"),
                ("party_two_name", "moa_party_two_name"),
                ("party_two_representative", "moa_party_two_representative"),
                ("signatories_notes", "moa_signatories_notes"),
            ]:
                if hasattr(proposal, model_field):
                    initial[form_field] = getattr(proposal, model_field, None)

        elif step == 3:
            for form_field, model_field in [
                ("obligations", "moa_obligations"),
                ("deliverables", "moa_deliverables"),
                ("confidentiality", "moa_confidentiality"),
            ]:
                if hasattr(proposal, model_field):
                    initial[form_field] = getattr(proposal, model_field, None)

        form = form_class(initial=initial)

    ctx = _build_moa_wizard_context(proposal, step)
    ctx["form"] = form
    ctx["step_help"] = {
        1: [
            "Write the formal title exactly as it should appear in the document.",
            "Fill in only the dates and reference number you already know.",
            "Use a clear, concise purpose statement.",
        ],
        2: [
            "Enter the official names of both parties.",
            "Add representatives if the signatory names are already assigned.",
            "Use the notes box for signers, witnesses, and titles.",
        ],
        3: [
            "Describe each party’s responsibilities using bullets if possible.",
            "Include deliverables such as reports, outputs, or endorsements.",
            "Add confidentiality or data-sharing rules if relevant.",
        ],
        4: [
            "Upload the draft MOA if you already have the file.",
            "Attach any endorsements, letters, or annexes.",
            "This is the final review step before moving forward.",
        ],
    }.get(step, [])

    template_name = f"services/moa/step_{step}.html"
    return render(request, template_name, ctx)


@login_required
@faculty_like_required
def proposal_moa_summary(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    ctx = {
        "proposal": proposal,
    }
    return render(request, "services/moa/summary.html", ctx)


@login_required
def proposal_moa_draft(request, proposal_id):
    """
    Guided MOA drafting page for proponents and staff.

    A proponent/staff member can either:
      1. Fill out the structured form (partner institution, WHEREAS clauses,
         objectives, obligations, IP terms, funding, term/effectivity, etc.)
         to generate a fully formatted MOA .docx modeled on ISPSC's standard
         MOA format, which is saved directly as the proposal's MOA document; or
      2. Upload an already-prepared/signed MOA file instead.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    is_proponent = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )
    if not (is_proponent or _is_staff(request.user)):
        messages.error(request, "You do not have permission to manage the MOA for this proposal.")
        return redirect("dashboard_redirect")

    if not getattr(proposal, "requires_moa", False):
        messages.info(request, "This proposal does not require a MOA.")
        return redirect("proposal_storage", proposal_id=proposal.id)

    moa_versions = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.MOA
    ).select_related("uploaded_by").order_by("-version")
    moa_doc = moa_versions.filter(is_current=True).first() or moa_versions.first()

    if request.method == "POST":
        action = (request.POST.get("action") or "generate").strip().lower()

        if action == "upload":
            moa_file = request.FILES.get("moa_file")
            if not moa_file:
                messages.error(request, "Please choose a file to upload.")
                return redirect("proposal_moa_draft", proposal_id=proposal.id)

            ProposalFinalDocument.add_version(
                proposal=proposal,
                document_type=ProposalFinalDocument.DocumentType.MOA,
                file=moa_file,
                uploaded_by=request.user,
                remarks=(request.POST.get("remarks") or "").strip(),
                is_verified=False,
            )
            previous_status = proposal.moa_status
            if proposal.moa_status in {
                Proposal.MOAStatus.NOT_STARTED,
                Proposal.MOAStatus.FOR_REVISION,
            }:
                proposal.mark_moa_draft()
                ProposalPhaseLog.objects.create(
                    proposal=proposal,
                    phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status,
                    to_status=proposal.moa_status,
                    remarks=(
                        "Revised MOA document uploaded and queued for Staff review."
                        if previous_status == Proposal.MOAStatus.FOR_REVISION
                        else "MOA document uploaded and queued for Staff review."
                    ),
                    changed_by=request.user,
                )
            elif proposal.moa_status == Proposal.MOAStatus.DRAFT:
                proposal.mark_moa_draft()

            messages.success(request, "MOA document uploaded successfully and queued for Staff review.")
            return redirect("proposal_moa_tracker", proposal_id=proposal.id)

        # action == "generate": build the .docx from the submitted form fields.
        form_data = {field: (request.POST.get(field) or "").strip() for field in MOA_DRAFT_TEXT_FIELDS}
        for field in MOA_DRAFT_CHECKBOX_FIELDS:
            form_data[field] = bool(request.POST.get(field))

        # Persist so the form + generated file stay in sync on future visits.
        proposal.moa_draft_data = form_data
        proposal.save(update_fields=["moa_draft_data", "last_saved_at"])

        buffer = build_moa_document(proposal, form_data)
        safe_title = re.sub(
            r"[^A-Za-z0-9_-]+", "_", (proposal.title or proposal.research_title or "Proposal")
        ).strip("_") or "Proposal"
        filename = f"{safe_title}_MOA_Draft.docx"
        generated_file = ContentFile(buffer.getvalue(), name=filename)

        version_note = (request.POST.get("version_note") or "").strip()
        ProposalFinalDocument.add_version(
            proposal=proposal,
            document_type=ProposalFinalDocument.DocumentType.MOA,
            file=generated_file,
            uploaded_by=request.user,
            remarks=version_note or "Generated via the guided MOA drafting form.",
            is_verified=False,
        )
        previous_status = proposal.moa_status
        if proposal.moa_status in {
            Proposal.MOAStatus.NOT_STARTED,
            Proposal.MOAStatus.FOR_REVISION,
        }:
            proposal.mark_moa_draft()
            ProposalPhaseLog.objects.create(
                proposal=proposal,
                phase=ProposalPhaseLog.Phase.MOA,
                from_status=previous_status,
                to_status=proposal.moa_status,
                remarks=(
                    "Revised MOA draft generated and queued for Staff review."
                    if previous_status == Proposal.MOAStatus.FOR_REVISION
                    else "MOA draft generated and queued for Staff review."
                ),
                changed_by=request.user,
            )
        elif proposal.moa_status == Proposal.MOAStatus.DRAFT:
            proposal.mark_moa_draft()

        messages.success(request, "MOA draft generated and queued for Staff review. You can review it in the MOA Tracker or keep editing here.")
        return redirect("proposal_moa_tracker", proposal_id=proposal.id)

    # GET: pre-fill the form with the last-saved draft data (falling back to
    # sensible defaults derived from the proposal itself).
    saved = proposal.moa_draft_data or {}
    default_fields = {
        "partner_name": saved.get("partner_name", "") or proposal.implementing_agency or "",
        "partner_description": saved.get("partner_description", ""),
        "partner_address": saved.get("partner_address", ""),
        "partner_short_name": saved.get("partner_short_name", ""),
        "partner_rep_name": saved.get("partner_rep_name", ""),
        "partner_rep_title": saved.get("partner_rep_title", ""),
        "whereas_clauses": saved.get("whereas_clauses", ""),
        "objectives": saved.get("objectives", "") or (proposal.general_objective or proposal.objectives_general or ""),
        "obligations_ispsc": saved.get("obligations_ispsc", ""),
        "obligations_partner": saved.get("obligations_partner", ""),
        "ip_ownership_text": saved.get("ip_ownership_text", ""),
        "ip_license_years": saved.get("ip_license_years", "3"),
        "ip_license_royalty_free": saved.get("ip_license_royalty_free", True),
        "ip_license_exclusive": saved.get("ip_license_exclusive", True),
        "ip_license_irrevocable": saved.get("ip_license_irrevocable", True),
        "term_years": saved.get("term_years", "3"),
        "funding_ispsc": saved.get("funding_ispsc", ""),
        "funding_partner": saved.get("funding_partner", ""),
        "data_privacy_text": saved.get("data_privacy_text", ""),
        "amendments_text": saved.get("amendments_text", ""),
        "termination_notice_days": saved.get("termination_notice_days", "30"),
        "misc_text": saved.get("misc_text", ""),
        "partner_witness1_name": saved.get("partner_witness1_name", ""),
        "partner_witness1_title": saved.get("partner_witness1_title", ""),
        "partner_witness2_name": saved.get("partner_witness2_name", ""),
        "partner_witness2_title": saved.get("partner_witness2_title", ""),
    }

    context = {
        "proposal": proposal,
        "moa_doc": moa_doc,
        "moa_versions": moa_versions,
        "default_fields": default_fields,
    }
    return render(request, "services/moa/moa_draft.html", context)


@login_required
def proposal_moa_tracker(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    if not _can_view_proposal(request.user, proposal):
        messages.error(request, "You don't have access to this proposal.")
        return redirect("dashboard_redirect")

    if not proposal.requires_moa:
        messages.info(request, "This proposal does not require a MOA.")
        return redirect("proposal_storage", proposal_id=proposal.id)

    # Legacy safety: if a draft file already exists but the proposal was never
    # moved out of NOT_STARTED, surface it as Draft so Staff/Director can send
    # it to Legal Review from this tracker. New uploads do this in moa_upload().
    if (
        proposal.moa_status == Proposal.MOAStatus.NOT_STARTED
        and (
            MOASubmission.objects.filter(proposal=proposal).exists()
            or ProposalFinalDocument.objects.filter(
                proposal=proposal,
                document_type=ProposalFinalDocument.DocumentType.MOA,
            ).exists()
            or bool(getattr(proposal, "moa_draft_file", None))
        )
    ):
        previous_status = proposal.moa_status
        proposal.mark_moa_draft()
        ProposalPhaseLog.objects.create(
            proposal=proposal,
            phase=ProposalPhaseLog.Phase.MOA,
            from_status=previous_status,
            to_status=proposal.moa_status,
            remarks="MOA draft upload detected; moved to Draft status.",
            changed_by=None,
        )

    can_manage   = _can_manage_phase(request.user, proposal)
    is_proponent = (
        request.user == proposal.created_by
        or proposal.proponents.filter(user=request.user).exists()
    )

    # ── POST ──────────────────────────────────────────────────────────────────
    if request.method == "POST":
        action  = (request.POST.get("action") or "").strip()
        remarks = (request.POST.get("remarks") or "").strip()

        # Mark notification read
        if action == "mark_read":
            MOANotification.objects.filter(
                id=request.POST.get("notification_id"), recipient=request.user
            ).update(is_read=True)
            return redirect("proposal_moa_tracker", proposal_id=proposal.id)

        if not can_manage:
            messages.error(request, "Only Staff or the Director can update the MOA stage.")
            return redirect("proposal_moa_tracker", proposal_id=proposal.id)

        previous_status = proposal.moa_status
        S = Proposal.MOAStatus

        # Draft → Legal Review
        if action == "legal_review":
            if proposal.moa_status != S.DRAFT:
                messages.error(request, "The MOA must be in Draft status to send it for Legal Review.")
            else:
                proposal.mark_moa_legal_review()
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks or "Draft sent to Legal Review.", changed_by=request.user,
                )
                messages.success(request, "MOA is now In Legal Review.")

        # Legal Review → For Revision (remarks required, notify proponent)
        elif action == "for_revision":
            if proposal.moa_status != S.LEGAL_REVIEW:
                messages.error(request, "The MOA must be In Legal Review to send it for Revision.")
            elif not remarks:
                messages.error(request, "Please provide revision remarks so the proponent knows what to fix.")
            else:
                proposal.mark_moa_for_revision()
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks, changed_by=request.user,
                )
                _notify_proponent(
                    proposal=proposal, sent_by=request.user,
                    notification_type=MOANotification.NotificationType.REVISION,
                    message=(
                        f"Your MOA draft for \"{proposal.display_title}\" has been returned "
                        f"for revision.\n\nRemarks: {remarks}"
                    ),
                )
                messages.success(request, "MOA sent for Revision. The proponent has been notified.")

        # Legal Review → Certification Ready (notify proponent)
        elif action == "certification_ready":
            if proposal.moa_status != S.LEGAL_REVIEW:
                messages.error(request, "The MOA must be In Legal Review to mark it as Certification Ready.")
            else:
                proposal.mark_moa_certification_ready()
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks or "Legal review cleared. MOA is Certification Ready.",
                    changed_by=request.user,
                )
                _notify_proponent(
                    proposal=proposal, sent_by=request.user,
                    notification_type=MOANotification.NotificationType.CERT_READY,
                    message=(
                        f"Great news! The MOA for \"{proposal.display_title}\" has passed legal "
                        f"review and the Certification is now being prepared. No further action "
                        f"is needed from your end at this time."
                    ),
                )
                messages.success(request, "MOA marked as Certification Ready. The proponent has been notified.")

        # Certification Ready → Agenda Brief & Presentation
        elif action == "agenda":
            if proposal.moa_status != S.CERTIFICATION_READY:
                messages.error(request, "The MOA must be Certification Ready to prepare the Agenda Brief.")
            else:
                proposal.mark_moa_agenda_and_presentation()
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks or "MOA prepared for Agenda Brief & Presentation.",
                    changed_by=request.user,
                )
                messages.success(request, "MOA is now in Agenda Brief & Presentation.")

        # Agenda Brief → MOA Completed, then move into Implementation
        elif action == "complete":
            if proposal.moa_status != S.AGENDA_AND_PRESENTATION:
                messages.error(request, "The MOA must be in Agenda Brief & Presentation to mark it Completed.")
            else:
                proposal.mark_moa_completed()
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks or "MOA signed and completed.", changed_by=request.user,
                )

                implementation_previous_status = proposal.implementation_status
                if proposal.implementation_status in {
                    Proposal.ImplementationStatus.NOT_STARTED,
                    Proposal.ImplementationStatus.PREPARATION,
                }:
                    proposal.mark_implementation_ongoing()
                    ProposalPhaseLog.objects.create(
                        proposal=proposal,
                        phase=ProposalPhaseLog.Phase.IMPLEMENTATION,
                        from_status=implementation_previous_status,
                        to_status=proposal.implementation_status,
                        remarks="MOA completed; moved to Implementation of Extension Activity.",
                        changed_by=request.user,
                    )

                _notify_proponent(
                    proposal=proposal, sent_by=request.user,
                    notification_type=MOANotification.NotificationType.COMPLETED,
                    message=(
                        f"The MOA for \"{proposal.display_title}\" has been completed and signed "
                        f"by all parties. The project is now in the Implementation of Extension "
                        f"Activity stage."
                    ),
                )
                messages.success(
                    request,
                    "MOA marked as Completed. The proponent has been notified and the project was moved to Implementation.",
                )
                return redirect("proposal_implementation_tracker", proposal_id=proposal.id)

        # Fallback: keep generic advance/back
        elif action == "advance":
            if proposal.advance_moa():
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks, changed_by=request.user,
                )
                messages.success(request, f"MOA advanced to '{proposal.get_moa_status_display()}'.")
            else:
                messages.info(request, "The MOA is already at its final stage.")

        elif action == "back":
            if proposal.regress_moa():
                ProposalPhaseLog.objects.create(
                    proposal=proposal, phase=ProposalPhaseLog.Phase.MOA,
                    from_status=previous_status, to_status=proposal.moa_status,
                    remarks=remarks or "Sent back to the previous stage.", changed_by=request.user,
                )
                messages.success(request, f"MOA sent back to '{proposal.get_moa_status_display()}'.")
            else:
                messages.info(request, "The MOA is already at its first stage.")

        else:
            messages.error(request, "Unknown action.")

        return redirect("proposal_moa_tracker", proposal_id=proposal.id)

    # ── GET ───────────────────────────────────────────────────────────────────
    moa_doc = proposal.final_documents.filter(
        document_type=ProposalFinalDocument.DocumentType.MOA
    ).first()

    notifications = MOANotification.objects.filter(
        proposal=proposal, recipient=request.user,
    ).order_by("-created_at")[:10]

    unread_count = MOANotification.objects.filter(
        proposal=proposal, recipient=request.user, is_read=False,
    ).count()

    S = Proposal.MOAStatus
    context = {
        "proposal":       proposal,
        "steps":          proposal.moa_step_states(),
        "can_manage":     can_manage,
        "is_proponent":   is_proponent,
        "moa_doc":        moa_doc,
        "logs":           proposal.phase_logs.filter(phase=ProposalPhaseLog.Phase.MOA).order_by("-created_at"),
        "is_first_stage": proposal.moa_status in {S.NOT_STARTED, S.DRAFT},
        "is_final_stage": proposal.moa_status == S.COMPLETED,
        "notifications":  notifications,
        "unread_count":   unread_count,
        "status_draft":         proposal.moa_status == S.DRAFT,
        "status_legal_review":  proposal.moa_status == S.LEGAL_REVIEW,
        "status_for_revision":  proposal.moa_status == S.FOR_REVISION,
        "status_cert_ready":    proposal.moa_status == S.CERTIFICATION_READY,
        "status_agenda":        proposal.moa_status == S.AGENDA_AND_PRESENTATION,
        "status_completed":     proposal.moa_status == S.COMPLETED,
    }
    return render(request, "services/moa/moa_tracker.html", context)


@login_required
def moa_upload(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    can_manage = _can_manage_phase(request.user, proposal)
    can_upload = can_manage or _can_edit(request.user, proposal)
    if not can_upload:
        messages.error(request, "You do not have permission to upload a MOA draft for this proposal.")
        return redirect("dashboard_redirect")

    existing = MOASubmission.objects.filter(proposal=proposal).first()

    if request.method == "POST":
        form = MOASubmissionForm(request.POST, request.FILES)

        if existing and not request.FILES.get("moa_file"):
            form.fields["moa_file"].required = False

        if form.is_valid():
            obj = existing if existing else MOASubmission(proposal=proposal, submitted_by=request.user)

            obj.partner_agency_name = form.cleaned_data["partner_agency_name"]
            obj.partner_address     = form.cleaned_data["partner_address"]
            obj.year                = form.cleaned_data["year"]
            obj.duration            = form.cleaned_data["duration"]

            uploaded_file = form.cleaned_data.get("moa_file")
            file_was_uploaded = bool(uploaded_file)

            if uploaded_file:
                if existing and existing.moa_file:
                    existing.moa_file.delete(save=False)
                obj.moa_file = uploaded_file

            obj.save()

            # A submitted or re-submitted draft should immediately become
            # visible to Staff/Director as Draft, ready to prepare for Legal
            # Review. If Legal Review already started, do not move it backward.
            draft_upload_statuses = {
                Proposal.MOAStatus.NOT_STARTED,
                Proposal.MOAStatus.DRAFT,
                Proposal.MOAStatus.FOR_REVISION,
            }
            if proposal.moa_status in draft_upload_statuses and (file_was_uploaded or not existing):
                previous_status = proposal.moa_status
                if proposal.moa_status != Proposal.MOAStatus.DRAFT:
                    proposal.mark_moa_draft()
                    ProposalPhaseLog.objects.create(
                        proposal=proposal,
                        phase=ProposalPhaseLog.Phase.MOA,
                        from_status=previous_status,
                        to_status=proposal.moa_status,
                        remarks=(
                            "Revised MOA draft uploaded by proponent."
                            if previous_status == Proposal.MOAStatus.FOR_REVISION
                            else "MOA draft uploaded and queued for Staff review."
                        ),
                        changed_by=request.user,
                    )
                else:
                    proposal.mark_moa_draft()

            messages.success(request, "MOA draft uploaded successfully and queued for Staff review.")
            return redirect("proposal_moa_tracker", proposal_id=proposal_id)
    else:
        initial = {}
        if existing:
            initial = {
                "partner_agency_name": existing.partner_agency_name,
                "partner_address":     existing.partner_address,
                "year":                existing.year,
                "duration":            existing.duration,
            }
        form = MOASubmissionForm(initial=initial)
        if existing:
            form.fields["moa_file"].required = False

    return render(request, "services/moa/moa_upload.html", {
        "proposal": proposal,
        "form":     form,
        "existing": existing,
    })
