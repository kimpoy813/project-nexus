"""
MOA drafting wizard, tracker, and uploads.
"""

import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from ..moa_docx import build_moa_document
from ..moa_forms import MOASubmissionForm
from ..models import MOANotification
from ..models import MOASubmission
from ..models import Proposal
from ..models import ProposalFinalDocument
from ..models import ProposalPhaseLog
from accounts.decorators import faculty_like_required
from .constants import MOA_DRAFT_CHECKBOX_FIELDS, MOA_DRAFT_TEXT_FIELDS
from .dynamic_answers import (
    _attach_moa_dynamic_forms,
    _save_moa_dynamic_form_answers,
)
from .moa_sections import apply_moa_section, mark_moa_draft_complete, moa_section_initial
from .wizard_flows import moa_flow
from .helpers import _notify_proponent
from .permissions import _can_edit, _can_manage_phase, _can_view_proposal, _is_staff


def build_moa_wizard_steps(current_step):
    """MOA stepper entries, in the order the office put the steps in.

    State follows position, not step number: a hidden or deleted step leaves a
    gap in the numbering, and "completed" would otherwise be decided by
    comparing numbers that no longer run consecutively.
    """
    visible = moa_flow.visible_step_nos()
    current_index = visible.index(current_step) if current_step in visible else -1

    def state_for(config, current):
        index = visible.index(config.step_no)
        if index == current_index:
            return "current"
        return "completed" if index < current_index else "upcoming"

    return moa_flow.build_steps(current_step, state_for=state_for)


def _build_moa_wizard_context(proposal, step):
    moa_flow.ensure_defaults()
    total_steps = moa_flow.total_visible()
    position = moa_flow.position(step)
    progress = int(((position - 1) / total_steps) * 100) if total_steps else 0
    config = moa_flow.get(step)
    return {
        "proposal": proposal,
        "step": step,
        "total_steps": total_steps,
        "step_position": position,
        "step_total": total_steps,
        "next_step_no": moa_flow.step_after(step),
        "prev_step_no": moa_flow.step_before(step),
        "progress": progress,
        "wizard_steps": build_moa_wizard_steps(step),
        "wizard_step_config": config,
    }


@login_required
@faculty_like_required
def proposal_moa_step(request, proposal_id, step):
    """One step of the MOA drafting wizard.

    The step decides what it shows through its :class:`MOAWizardSection`:
    which Django form, which proposal columns it writes, which template, and
    whether it is the part that closes the draft. A step with no section at all
    is an office-built one, driven purely by the forms attached to it.
    """
    proposal = get_object_or_404(Proposal, id=proposal_id)

    moa_flow.ensure_defaults()
    step = moa_flow.normalize(step)
    section = moa_flow.section(step)

    ctx = _build_moa_wizard_context(proposal, step)
    _attach_moa_dynamic_forms(ctx, proposal, step)

    form = None
    if section is not None:
        form = section.form_class(request.POST, request.FILES if section.binds_files else None) \
            if request.method == "POST" \
            else section.form_class(initial=moa_section_initial(section, proposal))
        ctx["step_help"] = list(section.help_text)
    else:
        ctx["step_help"] = []
    ctx["form"] = form

    if request.method == "POST":
        # A step with no built-in part is always "valid": there is nothing but
        # the office's own fields to save.
        section_valid = form.is_valid() if form is not None else True

        if section_valid:
            if section is not None:
                if section.save_request is not None:
                    section.save_request(proposal, request)
                else:
                    apply_moa_section(section, proposal, form.cleaned_data)

            dynamic_missing = _save_moa_dynamic_form_answers(
                proposal, step, request.user, request
            )
            if dynamic_missing:
                messages.error(
                    request,
                    "Please complete the required admin-managed field(s): "
                    + "; ".join(dynamic_missing[:5]),
                )
                return redirect("proposal_moa_step", proposal_id=proposal.id, step=step)

            next_step = moa_flow.step_after(step)
            if next_step is not None:
                messages.success(request, "MOA step saved. Continue to the next part.")
                return redirect(
                    "proposal_moa_step", proposal_id=proposal.id, step=next_step
                )

            # The last step the office left in the wizard is the one that
            # closes the draft, whichever part - or no part - it shows.
            mark_moa_draft_complete(proposal)
            messages.success(request, "MOA draft completed and queued for Staff review.")
            return redirect("proposal_moa_summary", proposal_id=proposal.id)

    return render(request, moa_flow.template_for(step), ctx)


@login_required
@faculty_like_required
def proposal_moa_summary(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    moa_flow.ensure_defaults()
    ctx = {
        "proposal": proposal,
        "moa_wizard_steps": moa_flow.ordered(),
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
