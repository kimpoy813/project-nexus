from datetime import timedelta
import json
import traceback

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Min, Q, Case, When, IntegerField
from django.http import HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .campus_data import get_college_choices, get_department_choices, get_campus_choices
from .decorators import admin_required, faculty_like_required, role_required
from .forms import AdminCreateUserForm, ProfileUpdateForm, RegisterForm
from .models import Profile, Signatory
from .tokens import email_verification_token

from proposals.models import (
    Proposal,
    ProposalEvaluatorAssignment,
    ProposalReviewRound,
    ProposalSectionComment,
    ProposalCommentSummary,
    ProposalFinalDocument,
)
from details.models import (
    Activity,
    ActivityDate,
    ExtensionProcess,
    Personnel,
    ProcessStep,
    Target,
)

User = get_user_model()

FAILED_LOGIN_LIMIT = 5
FAILED_LOGIN_WINDOW = 60 * 60
BLOCK_TIMEOUT = 60 * 60


# ==============================
# RATE LIMIT HELPERS
# ==============================

def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "unknown"


def _increment_failed(identifier):
    key = f"login_fail:{identifier}"
    count = cache.get(key, 0) + 1
    cache.set(key, count, timeout=FAILED_LOGIN_WINDOW)
    if count >= FAILED_LOGIN_LIMIT:
        cache.set(f"login_block:{identifier}", True, timeout=BLOCK_TIMEOUT)
    return count


def _reset_failed(identifier):
    cache.delete(f"login_fail:{identifier}")
    cache.delete(f"login_block:{identifier}")


def _is_blocked(identifier):
    return cache.get(f"login_block:{identifier}") is True

def _get_or_create_profile(user):
    """
    Django 6.0 calls full_clean() automatically on every Model.save().
    Profile.clean() validates department vs campus/college, which fails
    for blank default profiles.  Use save(clean=False) when creating so
    the empty placeholder row is stored without triggering that check.
    """
    try:
        return Profile.objects.get(user=user), False
    except Profile.DoesNotExist:
        profile = Profile(user=user, role=Profile.ROLE_FACULTY)
        profile.save(clean=False)
        return profile, True


# ==============================
# ROLE / DASHBOARD HELPERS
# ==============================

def _normalize_role(role):
    role = (role or Profile.ROLE_FACULTY).strip().upper()
    if role == "COORDINATOR":
        return Profile.ROLE_CAMPUS_COORDINATOR
    return role


def _get_role_dashboard_name(role):
    role = _normalize_role(role)

    if role == Profile.ROLE_ADMIN:
        return "admin_dashboard"
    if role == Profile.ROLE_DIRECTOR:
        return "director_dashboard"
    if role == Profile.ROLE_DEPARTMENT_COORDINATOR:
        return "department_coordinator_dashboard"
    if role == Profile.ROLE_CAMPUS_COORDINATOR:
        return "campus_coordinator_dashboard"
    if role == Profile.ROLE_STAFF:
        return "staff_dashboard"
    return "faculty_dashboard"


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_total_proposal_steps():
    return 19


def _get_current_step(proposal):
    return max(1, _safe_int(getattr(proposal, "current_step", 1), 1))


def _get_comment_count_for_current_round(proposal):
    try:
        current_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    except Exception:
        current_round = None

    if not current_round:
        return 0

    return ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=current_round,
    ).count()


def _get_review_level(proposal):
    return (getattr(proposal, "review_level", "") or "").upper().strip()


def _get_process_label(proposal):
    if proposal.status == Proposal.OverallStatus.COMPLETED:
        return "Completed"

    if proposal.implementation_status != Proposal.ImplementationStatus.NOT_STARTED:
        return "Implementation"

    if proposal.requires_moa and proposal.moa_status not in {
        Proposal.MOAStatus.NOT_STARTED,
        Proposal.MOAStatus.NOT_REQUIRED,
    }:
        return "MOA"

    return "Proposal"


def _get_lifecycle_milestone(proposal):
    process_label = _get_process_label(proposal)

    comment_count = _get_comment_count_for_current_round(proposal)

    if proposal.status == Proposal.OverallStatus.DRAFT:
        return f"Step {_get_current_step(proposal)} of {_get_total_proposal_steps()}"

    if process_label == "Proposal":
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION:
            return f"{_get_comment_count_for_current_round(proposal)} review comment(s) pending"
        if proposal.proposal_status == Proposal.ProposalStatus.IN_REVIEW:
            review_level = _get_review_level(proposal)
            if review_level == "DEPARTMENT":
                return "Department review ongoing"
            if review_level == "CAMPUS":
                return "Campus review ongoing"
            if review_level == "DIRECTOR":
                return "Director review ongoing"
            return "Review ongoing"
        if proposal.proposal_status == Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED:
            return "Summary sent to proponent"
        if proposal.proposal_status == Proposal.ProposalStatus.READY_FOR_PRINTING:
            return "Ready for printing"
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD:
            return "Awaiting submission and upload"
        if proposal.proposal_status == Proposal.ProposalStatus.APPROVED:
            return "Approved documents in progress"
        return proposal.get_proposal_status_display()

    if process_label == "MOA":
        return proposal.get_moa_status_display()

    if process_label == "Implementation":
        return proposal.get_implementation_status_display()

    return "Lifecycle finished"


def _get_lifecycle_description(proposal):
    process_label = _get_process_label(proposal)

    if proposal.status == Proposal.OverallStatus.DRAFT:
        return (
            f"The proposal is still being prepared and is currently on Step "
            f"{_get_current_step(proposal)} of {_get_total_proposal_steps()}."
        )

    if process_label == "Proposal":
        if proposal.proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW:
            return "The proposal has been submitted and is queued for review."
        if proposal.proposal_status == Proposal.ProposalStatus.IN_REVIEW:
            return "The proposal is currently undergoing institutional review."
        if proposal.proposal_status == Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED:
            return "The review summary has been prepared and issued to the proponent."
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION:
            return "The proposal has been returned to the proponent for revision."
        if proposal.proposal_status == Proposal.ProposalStatus.READY_FOR_PRINTING:
            return "The proposal is cleared and ready for printing."
        if proposal.proposal_status == Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD:
            return "Signed and digital copies are being submitted and uploaded."
        if proposal.proposal_status == Proposal.ProposalStatus.APPROVED:
            return (
                "The proposal is approved. Post-approval documents such as the "
                "Letter of Award, Endorsement, and Extension Agreement may now be processed."
            )
        if proposal.proposal_status == Proposal.ProposalStatus.COMPLETED:
            return "The proposal phase has been completed."
        return "The proposal is currently active in the proposal phase."

    if process_label == "MOA":
        return "The extension is currently in the MOA processing phase."

    if process_label == "Implementation":
        return "The extension is currently in the implementation and reporting phase."

    return "The extension lifecycle has been completed and formally closed."


def _build_proposal_dashboard_item(proposal):
    submitted_at = getattr(proposal, "submitted_at", None)
    updated_at = getattr(proposal, "last_saved_at", None)
    comment_count = _get_comment_count_for_current_round(proposal)

    days_since_submission = None
    if submitted_at:
        try:
            days_since_submission = max((timezone.now() - submitted_at).days, 0)
        except Exception:
            days_since_submission = None

    scope_label = proposal.get_scope_type_display() if getattr(proposal, "scope_type", None) else "—"
    process_label = _get_process_label(proposal)

    is_for_revision = (
        proposal.proposal_status == Proposal.ProposalStatus.FOR_REVISION
        or proposal.moa_status == Proposal.MOAStatus.FOR_REVISION
        or proposal.implementation_status == Proposal.ImplementationStatus.REVISION
    )

    is_draft = (
        proposal.status == Proposal.OverallStatus.DRAFT
        and proposal.proposal_status == Proposal.ProposalStatus.DRAFTING
    )

    needs_attention = bool(
        is_for_revision
        or proposal.proposal_status in {
            Proposal.ProposalStatus.READY_FOR_PRINTING,
            Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
        }
        or (comment_count > 0 and proposal.proposal_status in {
            Proposal.ProposalStatus.FOR_REVISION,
            Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
        })
    )

    return {
        "proposal": proposal,
        "current_step": _get_current_step(proposal),
        "total_steps": _get_total_proposal_steps(),
        "progress_percent": proposal.overall_progress,
        "status_label": proposal.current_status_label,
        "status_stage": proposal.current_phase_label,
        "status_milestone": _get_lifecycle_milestone(proposal),
        "status_description": _get_lifecycle_description(proposal),
        "process_label": process_label,
        "comment_count": comment_count,
        "submitted_at": submitted_at,
        "updated_at": updated_at,
        "days_since_submission": days_since_submission,
        "is_for_revision": is_for_revision,
        "needs_attention": needs_attention,
        "is_draft": is_draft,
        "scope_label": scope_label,
        "proposal_fill": min(proposal.proposal_progress, 100),
        "proposal_remaining": max(0, 100 - proposal.proposal_progress),
        "moa_fill": min(proposal.moa_progress, 100),
        "moa_remaining": max(0, 100 - proposal.moa_progress),
        "implementation_fill": min(proposal.implementation_progress, 100),
        "implementation_remaining": max(0, 100 - proposal.implementation_progress),
    }


def _get_user_proposals_context(user):
    my_proposals = (
        Proposal.objects.filter(
            Q(created_by=user)
            | Q(proponents__user=user)
            | Q(collaborators__user=user)
        )
        .distinct()
        .order_by("-last_saved_at")
        .prefetch_related("proponents", "collaborators")
    )

    drafts = my_proposals.filter(
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).order_by("-last_saved_at")

    submitted_queryset = my_proposals.exclude(
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).annotate(
        _attention_rank=Case(
            When(proposal_status=Proposal.ProposalStatus.FOR_REVISION, then=0),
            When(proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING, then=1),
            When(proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD, then=1),
            When(proposal_status=Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED, then=2),
            default=3,
            output_field=IntegerField(),
        )
    ).order_by("_attention_rank", "-submitted_at", "-last_saved_at")

    all_proposals = [_build_proposal_dashboard_item(proposal) for proposal in my_proposals]

    # --- Signed proposal flag (for hiding Download/Upload buttons once signed is uploaded) ---
    proposal_ids = [item["proposal"].id for item in all_proposals]
    signed_ids = set(
        ProposalFinalDocument.objects.filter(
            proposal_id__in=proposal_ids,
            document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
        ).values_list("proposal_id", flat=True)
    )
    for item in all_proposals:
        item["signed_uploaded"] = item["proposal"].id in signed_ids

    # Attach released approval documents for Approved/Claiming cards (LOA/Endorsement/Agreement)
    from proposals.models import ProposalFinalDocument as _PFD
    doc_types = [
        _PFD.DocumentType.LETTER_OF_AWARD,
        _PFD.DocumentType.ENDORSEMENT_FOR_APPROVAL,
        _PFD.DocumentType.EXTENSION_AGREEMENT,
    ]
    docs = _PFD.objects.filter(
        proposal_id__in=proposal_ids,
        document_type__in=doc_types,
    ).select_related("proposal")

    docs_by_pid = {}
    for d in docs:
        docs_by_pid.setdefault(d.proposal_id, {})[d.document_type] = d

    for item in all_proposals:
        pid = item["proposal"].id
        by_type = docs_by_pid.get(pid, {})
        item["loa_doc"] = by_type.get(_PFD.DocumentType.LETTER_OF_AWARD)
        item["endorse_doc"] = by_type.get(_PFD.DocumentType.ENDORSEMENT_FOR_APPROVAL)
        item["agreement_doc"] = by_type.get(_PFD.DocumentType.EXTENSION_AGREEMENT)

        # Claim is enabled when proposal is Approved/Claiming and all 3 docs exist.
        item["can_claim"] = (
            item["proposal"].proposal_status == Proposal.ProposalStatus.APPROVED
            and item["loa_doc"] is not None
            and item["endorse_doc"] is not None
            and item["agreement_doc"] is not None
        )


    needs_attention_count = sum(1 for item in all_proposals if item.get("needs_attention"))
    # Sort proposals that need attention first (stable sort keeps existing ordering within groups)
    all_proposals.sort(key=lambda x: (not x.get("needs_attention", False)))

    proposal_phase_count = 0
    moa_phase_count = 0
    implementation_phase_count = 0
    completed_phase_count = 0

    for item in all_proposals:
        process_label = item["process_label"]
        if process_label == "Completed":
            completed_phase_count += 1
        elif process_label == "Implementation":
            implementation_phase_count += 1
        elif process_label == "MOA":
            moa_phase_count += 1
        else:
            proposal_phase_count += 1

    under_review_count = submitted_queryset.filter(
        proposal_status__in=[
            Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
            Proposal.ProposalStatus.IN_REVIEW,
            Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
            Proposal.ProposalStatus.FOR_REVISION,
        ]
    ).count()

    approved_count = submitted_queryset.filter(
        proposal_status__in=[
            Proposal.ProposalStatus.READY_FOR_PRINTING,
            Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
            Proposal.ProposalStatus.APPROVED,
            Proposal.ProposalStatus.COMPLETED,
        ]
    ).count()

    return {
        "drafts": drafts,
        "submitted_proposals": submitted_queryset,
        "all_proposals": all_proposals,
        "draft_count": drafts.count(),
        "submitted_count": submitted_queryset.count(),
        "under_review_count": under_review_count,
        "approved_count": approved_count,
        "needs_attention_count": needs_attention_count,
        "proposal_phase_count": proposal_phase_count,
        "moa_phase_count": moa_phase_count,
        "implementation_phase_count": implementation_phase_count,
        "completed_phase_count": completed_phase_count,
    }


def _get_reviewable_proposal_statuses():
    return [
        Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
        Proposal.ProposalStatus.IN_REVIEW,
    ]


def _get_department_review_queue(user):
    profile = getattr(user, "profile", None)
    department = (getattr(profile, "department", "") or "").strip()

    return (
        Proposal.objects.filter(
            department=department,
            proposal_status__in=_get_reviewable_proposal_statuses(),
        )
        .exclude(created_by=user)
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_campus_review_queue(user):
    profile = getattr(user, "profile", None)
    campus = (getattr(profile, "campus", "") or "").strip()

    return (
        Proposal.objects.filter(
            campus=campus,
            proposal_status__in=_get_reviewable_proposal_statuses(),
        )
        .exclude(created_by=user)
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_director_review_queue(user):
    return (
        Proposal.objects.filter(
            proposal_status__in=[
                Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
                Proposal.ProposalStatus.IN_REVIEW,
            ]
        )
        .exclude(created_by=user)
        .exclude(
            review_rounds__ready_for_staff_summary=True,
            review_rounds__is_closed=False,
        )
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_evaluator_review_queue(user):
    return (
        Proposal.objects.filter(
            evaluator_assignments__evaluator=user,
            evaluator_assignments__is_active=True,
            proposal_status__in=_get_reviewable_proposal_statuses(),
        )
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_staff_summary_queue():
    return (
        Proposal.objects.filter(
            review_rounds__ready_for_staff_summary=True,
            review_rounds__is_closed=False,
            proposal_status=Proposal.ProposalStatus.IN_REVIEW,
        )
        .exclude(review_rounds__summaries__isnull=False)
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )


def _get_director_monitored_proposals(request):
    qs = (
        Proposal.objects.all()
        .select_related("created_by", "created_by__profile")
        .prefetch_related("proponents__user", "collaborators__user")
        .distinct()
        .order_by("-submitted_at", "-last_saved_at")
    )

    campus_filter = (request.GET.get("campus") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    scope_filter = (request.GET.get("scope") or "").strip()
    search = (request.GET.get("q") or "").strip()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()

    if campus_filter:
        qs = qs.filter(campus=campus_filter)

    if status_filter:
        qs = qs.filter(proposal_status=status_filter)

    if scope_filter:
        qs = qs.filter(scope_type=scope_filter)

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(research_title__icontains=search))

    if date_from:
        qs = qs.filter(last_saved_at__date__gte=date_from)

    if date_to:
        qs = qs.filter(last_saved_at__date__lte=date_to)

    return qs


def _get_proposal_prohibited_evaluator_ids(proposal):
    prohibited_ids = {proposal.created_by_id}

    proponent_user_ids = set(
        proposal.proponents.exclude(user__isnull=True).values_list("user_id", flat=True)
    )
    collaborator_user_ids = set(
        proposal.collaborators.exclude(user__isnull=True).values_list("user_id", flat=True)
    )

    prohibited_ids.update(proponent_user_ids)
    prohibited_ids.update(collaborator_user_ids)
    return prohibited_ids


def _get_assigned_evaluators_for_proposal(proposal):
    return [
        assignment.evaluator
        for assignment in proposal.evaluator_assignments.filter(is_active=True).select_related("evaluator__profile")
    ]


def _get_assignable_evaluators_for_proposal(proposal):
    prohibited_ids = _get_proposal_prohibited_evaluator_ids(proposal)

    already_assigned_ids = set(
        proposal.evaluator_assignments.filter(is_active=True).values_list("evaluator_id", flat=True)
    )

    return list(
        User.objects.filter(
            is_active=True,
            profile__role__in=[
                Profile.ROLE_FACULTY,
                Profile.ROLE_DEPARTMENT_COORDINATOR,
                Profile.ROLE_CAMPUS_COORDINATOR,
            ],
        )
        .exclude(id__in=prohibited_ids)
        .exclude(id__in=already_assigned_ids)
        .select_related("profile")
        .order_by("profile__full_name", "username")
    )


def _review_round_field_names():
    return {field.name for field in ProposalReviewRound._meta.get_fields() if hasattr(field, "name")}


def _get_open_review_round(proposal):
    try:
        current_round = proposal.get_active_review_round()
        if current_round:
            return current_round
    except Exception:
        pass

    try:
        current_round = proposal.get_current_review_round()
        if current_round and not getattr(current_round, "is_closed", False):
            return current_round
    except Exception:
        pass

    field_names = _review_round_field_names()
    qs = ProposalReviewRound.objects.filter(proposal=proposal)

    if "is_closed" in field_names:
        open_round = qs.filter(is_closed=False).order_by("-id").first()
        if open_round:
            return open_round

    return qs.order_by("-id").first()


def _create_review_round_for_proposal(proposal, user):
    field_names = _review_round_field_names()

    next_round_no = 1
    if "round_no" in field_names:
        last_round = (
            ProposalReviewRound.objects.filter(proposal=proposal)
            .order_by("-round_no")
            .values_list("round_no", flat=True)
            .first()
        )
        next_round_no = (last_round or 0) + 1

    create_kwargs = {"proposal": proposal}

    if "round_no" in field_names:
        create_kwargs["round_no"] = next_round_no
    if "started_by" in field_names:
        create_kwargs["started_by"] = user
    if "created_by" in field_names:
        create_kwargs["created_by"] = user
    if "opened_by" in field_names:
        create_kwargs["opened_by"] = user
    if "is_closed" in field_names:
        create_kwargs["is_closed"] = False
    if "ready_for_staff_summary" in field_names:
        create_kwargs.setdefault("ready_for_staff_summary", False)

    return ProposalReviewRound.objects.create(**create_kwargs)


def _get_or_create_open_review_round(proposal, user):
    review_round = _get_open_review_round(proposal)
    if review_round:
        return review_round
    return _create_review_round_for_proposal(proposal, user)


# ==============================
# CAMPUS / COLLEGE / DEPARTMENT AJAX
# ==============================

def get_colleges_ajax(request):
    campus = (request.GET.get("campus") or "").strip()
    colleges = [
        {"value": value, "label": label}
        for value, label in get_college_choices(campus)
    ]
    return JsonResponse({"colleges": colleges})


def get_departments_ajax(request):
    campus = (request.GET.get("campus") or "").strip()
    college = (request.GET.get("college") or "").strip()
    departments = [
        {"value": value, "label": label}
        for value, label in get_department_choices(campus, college)
    ]
    return JsonResponse({"departments": departments})


# ==============================
# REGISTER VIEW
# ==============================

@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                username = form.cleaned_data.get("username")
                raw_password = (
                    form.cleaned_data.get("password")
                    or form.cleaned_data.get("password1")
                )
                full_name = form.cleaned_data.get("full_name") or username
                campus = form.cleaned_data.get("campus", "")
                college = form.cleaned_data.get("college", "")
                department = form.cleaned_data.get("department", "")

                with transaction.atomic():
                    user = form.save(commit=False)

                    if raw_password:
                        user.set_password(raw_password)

                    user.is_active = False
                    user.save()

                    Profile.objects.update_or_create(
                        user=user,
                        defaults={
                            "full_name": full_name,
                            "campus": campus,
                            "college": college,
                            "department": department,
                            "role": Profile.ROLE_FACULTY,
                        },
                    )

                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = email_verification_token.make_token(user)
                verify_url = request.build_absolute_uri(
                    reverse("verify_email", kwargs={"uidb64": uid, "token": token})
                )

                subject = "Verify your NExUS account"
                html_message = render_to_string(
                    "accounts/email/verification_email.html",
                    {
                        "user": user,
                        "full_name": full_name,
                        "verify_url": verify_url,
                    },
                )
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    messages.success(
                        request,
                        "Account created! Please check your email to verify your account.",
                    )
                except Exception:
                    messages.warning(
                        request,
                        "Account created but verification email could not be sent. Please contact support.",
                    )

                return redirect("login")

            except Exception:
                traceback.print_exc()
                messages.error(request, "An error occurred while creating the account. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@require_http_methods(["GET"])
def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])

        profile, _ = _get_or_create_profile(user)
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])

        messages.success(request, "Email verified successfully! You may now log in.")
        return redirect("login")

    messages.error(request, "Invalid or expired verification link.")
    return redirect("register")


# ==============================
# LOGIN / LOGOUT
# ==============================

@require_http_methods(["GET", "POST"])
@csrf_protect
@ensure_csrf_cookie
def login_view(request):
    if request.method == "GET":
        get_token(request)

    if request.method == "GET" and request.GET.get("reason") == "idle":
        messages.warning(request, "You were logged out due to 10 minutes of inactivity.")

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        client_ip = _get_client_ip(request)

        identifiers = [client_ip]
        if identifier:
            identifiers.append(identifier.lower())

        for key in identifiers:
            if _is_blocked(key):
                messages.error(request, "Too many failed login attempts. Try again later.")
                return render(request, "accounts/login.html")

        username_to_auth = identifier
        if "@" in identifier:
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                username_to_auth = user_obj.username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=username_to_auth, password=password)

        if user:
            if not user.is_active:
                messages.error(request, "Email not verified. Please check your inbox.")
                return render(request, "accounts/login.html")

            for key in identifiers:
                _reset_failed(key)

            auth_login(request, user)
            messages.success(request, "Login successful!")

            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            profile, _ = _get_or_create_profile(request.user)
            role = _normalize_role(profile.role)
            return redirect(_get_role_dashboard_name(role))

        for key in identifiers:
            _increment_failed(key)

        messages.error(request, "Invalid username/email or password.")

    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("login")


@require_POST
@login_required
def logout_idle_view(request):
    auth_logout(request)
    return JsonResponse({"ok": True})


# ==============================
# PROFILE
# ==============================

@login_required
def profile_view(request):
    profile, _ = _get_or_create_profile(request.user)
    return render(request, "accounts/profile.html", {"profile": profile})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    profile, _ = _get_or_create_profile(request.user)

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            updated_profile = form.save(commit=False)

            full_name = form.cleaned_data.get("full_name")
            if full_name is not None:
                updated_profile.full_name = full_name

            updated_profile.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile_view")
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(
        request,
        "accounts/profile_edit.html",
        {"form": form, "profile": profile},
    )


@login_required
def change_password_email_view(request):
    user_email = request.user.email

    if not user_email:
        messages.error(request, "No email address is linked to your account.")
        return redirect("profile_view")

    form = PasswordResetForm({"email": user_email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        )
        return render(
            request,
            "accounts/change_password_email_sent.html",
            {"email": user_email},
        )

    messages.error(request, "Unable to send password reset email.")
    return redirect("profile_view")


# ==============================
# DASHBOARD REDIRECTS
# ==============================

@login_required
def dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    return redirect(_get_role_dashboard_name(profile.role))


@login_required
def dashboard_redirect(request):
    profile, _ = _get_or_create_profile(request.user)
    return redirect(_get_role_dashboard_name(profile.role))


# ==============================
# ROLE-BASED DASHBOARDS
# ==============================

@login_required
@faculty_like_required
def faculty_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    assigned_review_queue = _get_evaluator_review_queue(request.user)

    proposals_ctx = _get_user_proposals_context(request.user)

    # Proposals that require proponent action
    printing_ready_count = (
        Proposal.objects.filter(
            Q(created_by=request.user) | Q(proponents__user=request.user),
            proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING,
        )
        .distinct()
        .count()
    )
    approved_download_count = printing_ready_count  # alias used by templates


    upload_required_count = (
        Proposal.objects.filter(
            Q(created_by=request.user) | Q(proponents__user=request.user),
            proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
        )
        .distinct()
        .count()
    )

    # Show the banner for proposals that were returned for revision
    # and also those with an issued summary if your workflow still uses that state.
    revision_statuses = {
        Proposal.ProposalStatus.FOR_REVISION,
        Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
    }

    revision_proposals = (
        Proposal.objects.filter(
            Q(created_by=request.user)
            | Q(proponents__user=request.user)
            | Q(collaborators__user=request.user),
            proposal_status__in=revision_statuses,
        )
        .distinct()
        .select_related("created_by", "created_by__profile")
        .order_by("-last_saved_at", "-submitted_at", "-id")
    )

    first_revision = revision_proposals.first()

    context = {
        "profile": profile,
        "nav_notif_count": (proposals_ctx.get("needs_attention_count", 0) + assigned_review_queue.count() + printing_ready_count + upload_required_count),
        "printing_ready_count": printing_ready_count,
        "upload_required_count": upload_required_count,
        "approved_download_count": approved_download_count,
        **proposals_ctx,
        "assigned_review_queue": assigned_review_queue,
        "assigned_review_count": assigned_review_queue.count(),
        "has_evaluator_assignments": assigned_review_queue.exists(),
        "first_revision": first_revision,
        "has_revision_notice": first_revision is not None,
    }

    return render(request, "dashboard/faculty_dashboard.html", context)


@login_required
@role_required(["DIRECTOR"])
def director_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)

    from django.db.models import Q

    review_queue = Proposal.objects.filter(
        Q(proposal_status=Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW)
        | Q(proposal_status=Proposal.ProposalStatus.IN_REVIEW)
        | Q(proposal_status=Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED)
        | Q(proposal_status=Proposal.ProposalStatus.FOR_REVISION)
        | Q(proposal_status=Proposal.ProposalStatus.READY_FOR_PRINTING)
        | Q(proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD)
        | Q(proposal_status=Proposal.ProposalStatus.APPROVED)
        | Q(proposal_status=Proposal.ProposalStatus.COMPLETED)
    ).order_by("-submitted_at")

    # Count only items that still require director-side workflow attention (exclude Approved/Completed)
    action_queue_count = review_queue.exclude(
        proposal_status__in=[
            Proposal.ProposalStatus.READY_FOR_PRINTING,
            Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
            Proposal.ProposalStatus.APPROVED,
            Proposal.ProposalStatus.COMPLETED,
        ]
    ).count()

    for proposal in review_queue:
        proposal.assigned_evaluators = _get_assigned_evaluators_for_proposal(proposal)
        proposal.available_evaluators = _get_assignable_evaluators_for_proposal(proposal)

    monitored_queryset = _get_director_monitored_proposals(request)
    monitored_items = [_build_proposal_dashboard_item(proposal) for proposal in monitored_queryset]

    selected_process = (request.GET.get("process") or "").strip()
    selected_campus = (request.GET.get("campus") or "").strip()
    selected_status = (request.GET.get("status") or "").strip()
    selected_scope = (request.GET.get("scope") or "").strip()
    selected_date_from = (request.GET.get("date_from") or "").strip()
    selected_date_to = (request.GET.get("date_to") or "").strip()
    search_query = (request.GET.get("q") or "").strip()

    if selected_process:
        process_map = {
            "PROPOSAL": "Proposal",
            "MOA": "MOA",
            "IMPLEMENTATION": "Implementation",
            "COMPLETED": "Completed",
        }
        wanted_label = process_map.get(selected_process)
        if wanted_label:
            monitored_items = [
                item for item in monitored_items
                if item.get("process_label") == wanted_label
            ]

    print("ALL PROPOSALS:", Proposal.objects.count())
    print("QUEUE COUNT:", review_queue.count())

    for p in review_queue:
        print(p.id, p.proposal_status)

    def build_campus_stats_from_items(items):
        grouped = {}

        for item in items:
            proposal = item["proposal"]
            campus = (proposal.campus or "").strip() or "Unassigned Campus"

            if campus not in grouped:
                grouped[campus] = {
                    "campus": campus,
                    "total": 0,
                    "proposal_count": 0,
                    "moa_count": 0,
                    "implementation_count": 0,
                    "completed_count": 0,
                    "pending_count": 0,
                    "under_review_count": 0,
                    "approved_count": 0,
                    "revision_count": 0,
                    "active_pipeline_count": 0,
                    "review_backlog_count": 0,
                    "completion_rate": 0,
                }

            row = grouped[campus]
            row["total"] += 1

            process_label = item.get("process_label", "Proposal")
            if process_label == "Proposal":
                row["proposal_count"] += 1
            elif process_label == "MOA":
                row["moa_count"] += 1
            elif process_label == "Implementation":
                row["implementation_count"] += 1
            elif process_label == "Completed":
                row["completed_count"] += 1

            p = item["proposal"]

            if p.proposal_status in [
                Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
                Proposal.ProposalStatus.IN_REVIEW,
                Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
                Proposal.ProposalStatus.FOR_REVISION,
            ]:
                row["pending_count"] += 1

            if p.proposal_status == Proposal.ProposalStatus.IN_REVIEW:
                row["under_review_count"] += 1

            if p.proposal_status in [
                Proposal.ProposalStatus.APPROVED,
                Proposal.ProposalStatus.COMPLETED,
            ]:
                row["approved_count"] += 1

            if (
                p.proposal_status == Proposal.ProposalStatus.FOR_REVISION
                or p.moa_status == Proposal.MOAStatus.FOR_REVISION
                or p.implementation_status == Proposal.ImplementationStatus.REVISION
            ):
                row["revision_count"] += 1

        for row in grouped.values():
            row["active_pipeline_count"] = (
                row["proposal_count"] + row["moa_count"] + row["implementation_count"]
            )
            row["review_backlog_count"] = (
                row["pending_count"] + row["under_review_count"] + row["revision_count"]
            )
            row["completion_rate"] = round(
                (row["completed_count"] / row["total"]) * 100, 1
            ) if row["total"] else 0

        return sorted(grouped.values(), key=lambda x: x["campus"].lower())

    campus_stats = build_campus_stats_from_items(monitored_items)

    institution_total = len(monitored_items)

    submitted_total = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW
    )
    under_review_total = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status == Proposal.ProposalStatus.IN_REVIEW
    )
    institution_revision = sum(1 for item in monitored_items if item["is_for_revision"])
    institution_approved = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status in [
            Proposal.ProposalStatus.APPROVED,
            Proposal.ProposalStatus.COMPLETED,
        ]
    )
    institution_completed = sum(
        1 for item in monitored_items
        if item["proposal"].status == Proposal.OverallStatus.COMPLETED
        or item.get("process_label") == "Completed"
    )

    institution_pending = sum(
        1 for item in monitored_items
        if item["proposal"].proposal_status in [
            Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW,
            Proposal.ProposalStatus.IN_REVIEW,
            Proposal.ProposalStatus.REVIEW_SUMMARY_ISSUED,
            Proposal.ProposalStatus.FOR_REVISION,
        ]
    )

    proposal_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "Proposal"
    )
    moa_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "MOA"
    )
    implementation_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "Implementation"
    )
    completed_process_total = sum(
        1 for item in monitored_items if item.get("process_label") == "Completed"
    )

    active_pipeline_total = (
        proposal_process_total + moa_process_total + implementation_process_total
    )

    overall_completion_rate = round(
        (institution_completed / institution_total) * 100, 1
    ) if institution_total else 0

    review_backlog_total = submitted_total + under_review_total + institution_revision

    top_completed_campus = None
    top_completion_rate_campus = None
    top_backlog_campus = None

    if campus_stats:
        top_completed_campus = max(campus_stats, key=lambda x: x["completed_count"])
        top_completion_rate_campus = max(campus_stats, key=lambda x: x["completion_rate"])
        top_backlog_campus = max(campus_stats, key=lambda x: x["review_backlog_count"])

    paginator = Paginator(monitored_items, 10)
    page_number = request.GET.get("page")
    monitored_page = paginator.get_page(page_number)

    campuses = (
        Proposal.objects.exclude(campus__isnull=True)
        .exclude(campus__exact="")
        .values_list("campus", flat=True)
        .distinct()
        .order_by("campus")
    )

    process_chart_labels = ["Proposal", "MOA", "Implementation", "Completed"]
    process_chart_data = [
        proposal_process_total,
        moa_process_total,
        implementation_process_total,
        completed_process_total,
    ]

    status_chart_labels = ["Submitted", "In Review", "Revision", "Approved", "Completed"]
    status_chart_data = [
        submitted_total,
        under_review_total,
        institution_revision,
        institution_approved,
        institution_completed,
    ]

    campus_chart_labels = [item["campus"] for item in campus_stats]
    campus_chart_total = [item["total"] for item in campus_stats]
    campus_chart_completed = [item["completed_count"] for item in campus_stats]
    campus_chart_backlog = [item["review_backlog_count"] for item in campus_stats]
    campus_chart_completion_rate = [item["completion_rate"] for item in campus_stats]
    campus_chart_proposal = [item["proposal_count"] for item in campus_stats]
    campus_chart_moa = [item["moa_count"] for item in campus_stats]
    campus_chart_implementation = [item["implementation_count"] for item in campus_stats]
    campus_chart_pending = [item["pending_count"] for item in campus_stats]
    campus_chart_under_review = [item["under_review_count"] for item in campus_stats]
    campus_chart_revision = [item["revision_count"] for item in campus_stats]

    proposals_ctx = _get_user_proposals_context(request.user)

    context = {
        "profile": profile,
        "nav_notif_count": action_queue_count,
        **proposals_ctx,
        "review_queue": review_queue,
        "review_queue_count": action_queue_count,
        "monitored_page": monitored_page,
        "campus_stats": campus_stats,
        "institution_total": institution_total,
        "institution_pending": institution_pending,
        "institution_revision": institution_revision,
        "institution_approved": institution_approved,
        "institution_completed": institution_completed,
        "submitted_total": submitted_total,
        "under_review_total": under_review_total,
        "proposal_process_total": proposal_process_total,
        "moa_process_total": moa_process_total,
        "implementation_process_total": implementation_process_total,
        "completed_process_total": completed_process_total,
        "active_pipeline_total": active_pipeline_total,
        "review_backlog_total": review_backlog_total,
        "overall_completion_rate": overall_completion_rate,
        "top_completed_campus": top_completed_campus,
        "top_completion_rate_campus": top_completion_rate_campus,
        "top_backlog_campus": top_backlog_campus,
        "campus_choices": campuses,
        "selected_campus": selected_campus,
        "selected_process": selected_process,
        "selected_status": selected_status,
        "selected_scope": selected_scope,
        "selected_date_from": selected_date_from,
        "selected_date_to": selected_date_to,
        "search_query": search_query,
        "process_chart_labels": json.dumps(process_chart_labels),
        "process_chart_data": json.dumps(process_chart_data),
        "status_chart_labels": json.dumps(status_chart_labels),
        "status_chart_data": json.dumps(status_chart_data),
        "campus_chart_labels": json.dumps(campus_chart_labels),
        "campus_chart_total": json.dumps(campus_chart_total),
        "campus_chart_completed": json.dumps(campus_chart_completed),
        "campus_chart_backlog": json.dumps(campus_chart_backlog),
        "campus_chart_completion_rate": json.dumps(campus_chart_completion_rate),
        "campus_chart_proposal": json.dumps(campus_chart_proposal),
        "campus_chart_moa": json.dumps(campus_chart_moa),
        "campus_chart_implementation": json.dumps(campus_chart_implementation),
        "campus_chart_pending": json.dumps(campus_chart_pending),
        "campus_chart_under_review": json.dumps(campus_chart_under_review),
        "campus_chart_revision": json.dumps(campus_chart_revision),
        "review_year_choices": (
            Proposal.objects.exclude(submitted_at__isnull=True)
            .dates("submitted_at", "year", order="DESC")
        ),
    }

    return render(request, "dashboard/director_dashboard.html", context)

@login_required
@role_required(["DIRECTOR", "STAFF"])
@require_POST
def proposal_mark_ready_for_summary(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)

    review_round = proposal.get_active_review_round() or proposal.get_current_review_round()
    if not review_round:
        messages.error(request, "No active review round found.")
        return redirect("director_dashboard")

    # Block re-queue if summary already sent for this round
    if ProposalCommentSummary.objects.filter(
        proposal=proposal,
        review_round=review_round,
        sent_to_proponent=True,
    ).exists():
        messages.warning(request, "A summary has already been issued for the current review round.")
        return redirect("director_dashboard")

    # Require at least one director comment in this round
    has_director_comment = ProposalSectionComment.objects.filter(
        proposal=proposal,
        review_round=review_round,
        reviewer=request.user,
        reviewer_role="DIRECTOR",
    ).exists()
    if not has_director_comment:
        messages.error(request, "Please add at least one director comment before marking ready for summary.")
        return redirect("director_dashboard")

    if not getattr(review_round, "ready_for_staff_summary", False):
        review_round.ready_for_staff_summary = True
        review_round.save(update_fields=["ready_for_staff_summary"])

    proposal.proposal_status = Proposal.ProposalStatus.IN_REVIEW
    proposal.save(update_fields=["proposal_status"])

    messages.success(request, "Proposal marked ready for staff summary.")
    return redirect("director_dashboard")


@login_required
@role_required(["DIRECTOR"])
@require_POST
def proposal_assign_evaluator(request, proposal_id, evaluator_id):
    try:
        proposal = get_object_or_404(
            Proposal.objects.prefetch_related(
                "proponents__user",
                "collaborators__user",
                "review_rounds",
                "evaluator_assignments__evaluator__profile",
            ),
            id=proposal_id,
        )

        evaluator = get_object_or_404(
            User.objects.select_related("profile"),
            id=evaluator_id,
            is_active=True,
        )

        allowed_roles = {
            Profile.ROLE_FACULTY,
            Profile.ROLE_DEPARTMENT_COORDINATOR,
            Profile.ROLE_CAMPUS_COORDINATOR,
        }

        evaluator_role = getattr(getattr(evaluator, "profile", None), "role", "")
        if evaluator_role not in allowed_roles:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "Selected user cannot be assigned as evaluator."},
                    status=400,
                )
            messages.error(request, "Selected user cannot be assigned as evaluator.")
            return redirect("director_dashboard")

        prohibited_ids = _get_proposal_prohibited_evaluator_ids(proposal)
        if evaluator.id in prohibited_ids:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "message": "This faculty member cannot be assigned as evaluator for this proposal."},
                    status=400,
                )
            messages.error(request, "This faculty member cannot be assigned as evaluator for this proposal.")
            return redirect("director_dashboard")

        review_round = _get_or_create_open_review_round(proposal, request.user)

        assignment, created = ProposalEvaluatorAssignment.objects.get_or_create(
            proposal=proposal,
            review_round=review_round,
            evaluator=evaluator,
            defaults={
                "assigned_by": request.user,
                "is_active": True,
                "is_completed": False,
            },
        )

        if not created:
            changed = False

            if not assignment.is_active:
                assignment.is_active = True
                changed = True

            if assignment.is_completed:
                assignment.is_completed = False
                changed = True

            if assignment.assigned_by_id != request.user.id:
                assignment.assigned_by = request.user
                changed = True

            if changed:
                assignment.save()

        if proposal.proposal_status == Proposal.ProposalStatus.SUBMITTED_FOR_REVIEW:
            proposal.transition_proposal_status(
                Proposal.ProposalStatus.IN_REVIEW
            )
            proposal.save(update_fields=["proposal_status"])

        assigned_evaluators = _get_assigned_evaluators_for_proposal(proposal)
        available_evaluators = _get_assignable_evaluators_for_proposal(proposal)

        evaluator_name = getattr(getattr(evaluator, "profile", None), "full_name", "") or evaluator.username

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "ok": True,
                "message": f'"{evaluator_name}" has been added as evaluator.',
                "proposal_id": str(proposal.id),
                "assigned_evaluators": [
                    {
                        "id": ev.id,
                        "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                        "remove_url": reverse("proposal_remove_evaluator", args=[proposal.id, ev.id]),
                    }
                    for ev in assigned_evaluators
                ],
                "available_evaluators": [
                    {
                        "id": ev.id,
                        "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                    }
                    for ev in available_evaluators
                ],
                "status_label": proposal.current_status_label,
            })

        messages.success(request, f'"{evaluator_name}" has been added as evaluator.')
        return redirect("director_dashboard")

    except Exception as e:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": f"Server error: {str(e)}"},
                status=500,
            )
        raise


@login_required
@role_required(["DIRECTOR"])
@require_POST
def proposal_remove_evaluator(request, proposal_id, evaluator_id):
    proposal = get_object_or_404(
        Proposal.objects.prefetch_related(
            "evaluator_assignments__evaluator__profile",
            "proponents__user",
            "collaborators__user",
            "review_rounds",
        ),
        id=proposal_id,
    )

    review_round = _get_open_review_round(proposal)

    qs = ProposalEvaluatorAssignment.objects.filter(
        proposal=proposal,
        evaluator_id=evaluator_id,
        is_active=True,
    )

    if review_round is not None:
        qs = qs.filter(review_round=review_round)

    assignment = qs.first()

    if not assignment:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": "Evaluator assignment not found."}, status=404)
        messages.error(request, "Evaluator assignment not found.")
        return redirect("director_dashboard")

    assignment.is_active = False
    assignment.save(update_fields=["is_active"])

    assigned_evaluators = _get_assigned_evaluators_for_proposal(proposal)
    available_evaluators = _get_assignable_evaluators_for_proposal(proposal)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "message": "Evaluator removed successfully.",
            "proposal_id": str(proposal.id),
            "assigned_evaluators": [
                {
                    "id": ev.id,
                    "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                    "remove_url": reverse("proposal_remove_evaluator", args=[proposal.id, ev.id]),
                }
                for ev in assigned_evaluators
            ],
            "available_evaluators": [
                {
                    "id": ev.id,
                    "name": getattr(getattr(ev, "profile", None), "full_name", "") or ev.username,
                }
                for ev in available_evaluators
            ],
        })

    messages.success(request, "Evaluator removed successfully.")
    return redirect("director_dashboard")

from collections import OrderedDict
from django.db.models import OuterRef, Subquery
@login_required
@role_required(["STAFF"])
def staff_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)

    # Pull ALL review rounds flagged as ready (latest first).
    # Do NOT filter by is_closed here — some workflows may close the round when marking ready.
    ready_rounds = (
        ProposalReviewRound.objects.filter(ready_for_staff_summary=True)
        .select_related("proposal", "proposal__created_by", "proposal__created_by__profile")
        .order_by("-id")
    )

    # Keep only the latest ready round per proposal (prevents duplicates if any historical rounds were flagged).
    latest_by_proposal = OrderedDict()
    for rr in ready_rounds:
        pid = rr.proposal_id
        if pid not in latest_by_proposal:
            latest_by_proposal[pid] = rr

    summary_queue = []
    pending_count = 0
    draft_count = 0

    for rr in latest_by_proposal.values():
        p = rr.proposal

        # Status flags for TEMPLATE (these are dynamic attrs, not model fields)
        p.active_round_no = getattr(rr, "round_no", None) or 1

        # Summaries are tied to the review round.
        # Prefer rr.summaries if your FK uses related_name="summaries"; fallback to ProposalCommentSummary.
        try:
            summaries_qs = rr.summaries.all()
        except Exception:
            summaries_qs = ProposalCommentSummary.objects.filter(review_round=rr)

        p.summary_sent = summaries_qs.filter(sent_to_proponent=True).exists()
        p.has_draft_summary = summaries_qs.filter(sent_to_proponent=False).exists()

        # Queue rule:
        # - show if NOT sent
        # - count as draft if saved but not sent
        # - count as pending if nothing saved yet
        if p.summary_sent:
            continue

        if p.has_draft_summary:
            draft_count += 1
        else:
            pending_count += 1

        summary_queue.append(p)

    # Sort newest first (submitted_at, then last_saved_at)
    summary_queue.sort(
        key=lambda x: (
            getattr(x, "submitted_at", None) or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()),
            getattr(x, "last_saved_at", None) or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()),
        ),
        reverse=True,
    )

    # --- Signed Proposal Verification queue (uploaded but not yet verified) ---
    signed_queue = ProposalFinalDocument.objects.filter(
        document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
        is_verified=False,
        proposal__proposal_status=Proposal.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
    ).select_related(
        "proposal",
        "proposal__created_by",
        "proposal__created_by__profile",
        "uploaded_by",
        "uploaded_by__profile",
    ).order_by("-uploaded_at")

    signed_pending_count = signed_queue.count()


    context = {
        "profile": profile,
        "nav_notif_count": (pending_count + draft_count + signed_pending_count),
        "summary_queue": summary_queue,
        "pending_count": pending_count,
        "draft_count": draft_count,
        "signed_queue": signed_queue,
        "signed_pending_count": signed_pending_count,
    }
    return render(request, "dashboard/staff_dashboard.html", context)


@login_required
@role_required(["DEPARTMENT_COORDINATOR"])
def department_coordinator_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    review_queue = _get_department_review_queue(request.user)
    action_queue_count = review_queue.count()

    proposals_ctx = _get_user_proposals_context(request.user)

    context = {
        "profile": profile,
        "nav_notif_count": (proposals_ctx.get("needs_attention_count", 0) + action_queue_count),
        **proposals_ctx,
        "review_queue": review_queue,
        "review_queue_count": review_queue.count(),
        "action_queue_count": action_queue_count,
    }
    return render(request, "dashboard/department_coordinator_dashboard.html", context)


@login_required
@role_required(["CAMPUS_COORDINATOR"])
def campus_coordinator_dashboard(request):
    profile, _ = _get_or_create_profile(request.user)
    review_queue = _get_campus_review_queue(request.user)
    action_queue_count = review_queue.count()

    proposals_ctx = _get_user_proposals_context(request.user)

    context = {
        "profile": profile,
        "nav_notif_count": (proposals_ctx.get("needs_attention_count", 0) + action_queue_count),
        **proposals_ctx,
        "review_queue": review_queue,
        "review_queue_count": review_queue.count(),
        "action_queue_count": action_queue_count,
    }
    return render(request, "dashboard/campus_coordinator_dashboard.html", context)


# ==============================
# ADMIN DASHBOARD / USERS
# ==============================

@login_required
@admin_required
def admin_dashboard(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    profiles = Profile.objects.select_related("user").all().order_by("-user__date_joined")

    context = {
        "profiles": profiles,
        "nav_notif_count": Profile.objects.filter(email_verified=False).count(),
        "total_users": User.objects.count(),
        "verified_users": Profile.objects.filter(email_verified=True).count(),
        "unverified_users": Profile.objects.filter(email_verified=False).count(),
        "active_today": User.objects.filter(last_login__gte=today_start).count(),
        "faculty_count": Profile.objects.filter(role=Profile.ROLE_FACULTY).count(),
        "evaluator_count": User.objects.filter(
            proposal_evaluator_assignments__is_active=True
        ).distinct().count(),
        "department_coordinator_count": Profile.objects.filter(
            role=Profile.ROLE_DEPARTMENT_COORDINATOR
        ).count(),
        "campus_coordinator_count": Profile.objects.filter(
            role=Profile.ROLE_CAMPUS_COORDINATOR
        ).count(),
        "director_count": Profile.objects.filter(role=Profile.ROLE_DIRECTOR).count(),
        "personnel_count": Personnel.objects.count(),
        "activities_count": Activity.objects.count(),
        "processes_count": ExtensionProcess.objects.count(),
        "targets_count": Target.objects.count(),
        "signatories_count": Signatory.objects.count(),
        "total_content": (
            Personnel.objects.count()
            + Activity.objects.count()
            + ExtensionProcess.objects.count()
            + Target.objects.count()
            + Signatory.objects.count()
        ),
        "recent_users": Profile.objects.select_related("user").filter(
            user__date_joined__gte=week_ago
        ).order_by("-user__date_joined")[:5],
    }
    return render(request, "dashboard/admin_dashboard.html", context)


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def admin_create_account(request):
    if request.method == "POST":
        form = AdminCreateUserForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=form.cleaned_data["username"],
                        email=form.cleaned_data.get("email", ""),
                        password=form.cleaned_data["password"],
                    )

                    full_name = form.cleaned_data.get("full_name") or user.username

                    Profile.objects.update_or_create(
                        user=user,
                        defaults={
                            "full_name": full_name,
                            "campus": form.cleaned_data.get("campus", ""),
                            "college": form.cleaned_data.get("college", ""),
                            "department": form.cleaned_data.get("department", ""),
                            "role": form.cleaned_data["role"],
                            "email_verified": not bool(form.cleaned_data.get("email")),
                        },
                    )

                messages.success(request, f'Account "{user.username}" created successfully.')
                return redirect("admin_dashboard")

            except Exception as e:
                messages.error(request, f"Error creating account: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AdminCreateUserForm()

    return render(request, "accounts/admin_create_account.html", {"form": form})


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def admin_edit_user(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    profile, _ = _get_or_create_profile(user_obj)

    if request.method == "POST":
        try:
            with transaction.atomic():
                user_obj.username = (request.POST.get("username") or user_obj.username).strip()
                user_obj.email = (request.POST.get("email") or "").strip()
                user_obj.is_active = request.POST.get("is_active") == "on"

                new_password = (request.POST.get("password") or "").strip()
                if new_password:
                    user_obj.set_password(new_password)

                user_obj.save()

                requested_role = (request.POST.get("role") or profile.role or Profile.ROLE_FACULTY).strip().upper()
                allowed_roles = {choice[0] for choice in Profile.ROLE_CHOICES}
                if requested_role not in allowed_roles:
                    requested_role = Profile.ROLE_FACULTY

                full_name = (request.POST.get("full_name") or "").strip() or user_obj.username

                profile.full_name = full_name
                profile.campus = (request.POST.get("campus") or "").strip()
                profile.college = (request.POST.get("college") or "").strip()
                profile.department = (request.POST.get("department") or "").strip()
                profile.role = requested_role
                profile.email_verified = request.POST.get("email_verified") == "on"
                profile.save()

            messages.success(request, f'User "{user_obj.username}" updated successfully.')
            return redirect("admin_dashboard")
        except Exception as e:
            messages.error(request, f"Error updating user: {e}")

    return render(
        request,
        "accounts/admin_edit_user.html",
        {
            "edit_user": user_obj,
            "edit_profile": profile,
            "role_choices": Profile.ROLE_CHOICES,
        },
    )


@login_required
@admin_required
def admin_user_detail(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    profile, _ = _get_or_create_profile(user_obj)

    related_proposals = Proposal.objects.filter(
        Q(created_by=user_obj)
        | Q(proponents__user=user_obj)
        | Q(collaborators__user=user_obj)
    ).distinct().order_by("-last_saved_at", "-submitted_at")

    return render(
        request,
        "accounts/admin_user_detail.html",
        {
            "view_user": user_obj,
            "view_profile": profile,
            "related_proposals": related_proposals,
        },
    )


@login_required
@admin_required
def manage_roles(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        new_role = (request.POST.get("role") or "").upper()

        allowed_roles = {choice[0] for choice in Profile.ROLE_CHOICES}
        if new_role not in allowed_roles:
            messages.error(request, "Invalid role selected.")
            return redirect("admin_dashboard")

        if user_id and new_role:
            try:
                profile = Profile.objects.get(user__id=user_id)
                old_role = profile.role
                profile.role = new_role

                if profile.role == Profile.ROLE_ADMIN:
                    profile.email_verified = True

                profile.save()
                messages.success(
                    request,
                    f"Role updated for {profile.full_name} from {old_role} to {new_role}.",
                )
            except Profile.DoesNotExist:
                messages.error(request, "User profile not found.")
            except Exception as e:
                messages.error(request, f"Error updating role: {str(e)}")

        return redirect("admin_dashboard")

    return redirect("admin_dashboard")


# ==============================
# DEBUG LOGIN
# ==============================

@ensure_csrf_cookie
@csrf_protect
def debug_login_view(request):
    if request.method == "POST":
        return HttpResponseRedirect(reverse("login"))
    return render(request, "debug_login.html")


# ==============================
# CONTENT MANAGEMENT
# ==============================

@login_required
@admin_required
def admin_content_dashboard(request):
    context = {
        "personnel_count": Personnel.objects.count(),
        "activities_count": Activity.objects.count(),
        "processes_count": ExtensionProcess.objects.count(),
        "targets_count": Target.objects.count(),
        "signatories_count": Signatory.objects.count(),
    }
    return render(request, "dashboard/admin/content_dashboard.html", context)


# ==============================
# SIGNATORIES MANAGEMENT (ADMIN)
# ==============================

@login_required
@admin_required
def signatories_list(request):
    signatories = Signatory.objects.all().order_by(
        "position_title",
        "campus",
        "college",
        "department",
        "full_name",
    )
    return render(request, "dashboard/admin/signatories_list.html", {"signatories": signatories})


def _signatory_scope_meta(position_title):
    # Returns (scope_level, help_text)
    pt = (position_title or "").strip()

    global_positions = {
        Signatory.Position.DIRECTOR_EXTENSION,
        Signatory.Position.VPRDE,
        Signatory.Position.SUC_PRESIDENT_III,
    }
    campus_positions = {
        Signatory.Position.CAMPUS_EXTENSION_COORDINATOR,
        Signatory.Position.CAMPUS_DIRECTOR,
    }
    college_positions = {Signatory.Position.DEAN}
    dept_positions = {Signatory.Position.DEPARTMENT_EXTENSION_COORDINATOR}

    if pt in global_positions:
        return "global", "Global position: leave campus/college/department blank."
    if pt in campus_positions:
        return "campus", "Campus-scoped position: select a campus."
    if pt in college_positions:
        return "college", "College-scoped position: select campus and college."
    if pt in dept_positions:
        return "department", "Department-scoped position: select campus, college, and department."
    return "global", "Set the scope fields as needed."


def _build_scope_choices(campus_value, college_value):
    campus_value = (campus_value or "").strip()
    college_value = (college_value or "").strip()

    college_choices = []
    dept_choices = []

    if campus_value:
        college_choices = [c[0] for c in get_college_choices(campus_value)]
        if college_value:
            dept_choices = [d[0] for d in get_department_choices(campus_value, college_value)]

    return college_choices, dept_choices


@login_required
@admin_required
def signatory_create(request):
    if request.method == "POST":
        position_title = (request.POST.get("position_title") or Signatory.Position.DIRECTOR_EXTENSION).strip()
        campus = (request.POST.get("campus") or "").strip()
        college = (request.POST.get("college") or "").strip()
        department = (request.POST.get("department") or "").strip()

        full_name = (request.POST.get("full_name") or "").strip()
        credentials = (request.POST.get("credentials") or "").strip()

        signatory = Signatory(
            position_title=position_title,
            campus=campus,
            college=college,
            department=department,
            full_name=full_name,
            credentials=credentials,
        )

        try:
            signatory.full_clean()
            signatory.save()
            messages.success(request, f'Signatory "{signatory.display_name}" added successfully.')
            return redirect("signatories_list")
        except Exception as e:
            messages.error(request, f"Please correct the errors: {e}")

        college_choices, dept_choices = _build_scope_choices(campus, college)
        scope_level, scope_help = _signatory_scope_meta(position_title)

        return render(
            request,
            "dashboard/admin/signatory_form.html",
            {
                "mode": "create",
                "position_choices": Signatory.Position.choices,
                "campus_choices": [c[0] for c in get_campus_choices()],
                "college_choices": college_choices,
                "department_choices": dept_choices,
                "scope_level": scope_level,
                "scope_help": scope_help,
                "form_data": request.POST,
            },
        )

    scope_level, scope_help = _signatory_scope_meta(Signatory.Position.DIRECTOR_EXTENSION)
    return render(
        request,
        "dashboard/admin/signatory_form.html",
        {
            "mode": "create",
            "position_choices": Signatory.Position.choices,
            "campus_choices": [c[0] for c in get_campus_choices()],
            "college_choices": [],
            "department_choices": [],
            "scope_level": scope_level,
            "scope_help": scope_help,
            "form_data": {},
        },
    )


@login_required
@admin_required
def signatory_edit(request, pk):
    signatory = get_object_or_404(Signatory, pk=pk)

    if request.method == "POST":
        signatory.position_title = (request.POST.get("position_title") or signatory.position_title).strip()
        signatory.campus = (request.POST.get("campus") or "").strip()
        signatory.college = (request.POST.get("college") or "").strip()
        signatory.department = (request.POST.get("department") or "").strip()

        signatory.full_name = (request.POST.get("full_name") or "").strip()
        signatory.credentials = (request.POST.get("credentials") or "").strip()

        try:
            signatory.full_clean()
            signatory.save()
            messages.success(request, "Signatory updated successfully.")
            return redirect("signatories_list")
        except Exception as e:
            messages.error(request, f"Please correct the errors: {e}")

    college_choices, dept_choices = _build_scope_choices(signatory.campus, signatory.college)
    scope_level, scope_help = _signatory_scope_meta(signatory.position_title)

    return render(
        request,
        "dashboard/admin/signatory_form.html",
        {
            "mode": "edit",
            "signatory": signatory,
            "position_choices": Signatory.Position.choices,
            "campus_choices": [c[0] for c in get_campus_choices()],
            "college_choices": college_choices,
            "department_choices": dept_choices,
            "scope_level": scope_level,
            "scope_help": scope_help,
            "form_data": {
                "position_title": signatory.position_title,
                "campus": signatory.campus,
                "college": signatory.college,
                "department": signatory.department,
                "full_name": signatory.full_name,
                "credentials": signatory.credentials,
            },
        },
    )


@login_required
@admin_required
@require_POST
def signatory_delete(request, pk):
    signatory = get_object_or_404(Signatory, pk=pk)
    name = signatory.display_name
    signatory.delete()
    messages.success(request, f'Signatory "{name}" deleted successfully.')
    return redirect("signatories_list")



@login_required
@admin_required
def personnel_list(request):
    personnel = Personnel.objects.all().order_by("name")
    return render(request, "dashboard/admin/personnel_list.html", {"personnel": personnel})


@login_required
@admin_required
def personnel_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        position = (request.POST.get("position") or "").strip()
        email = (request.POST.get("email") or "").strip()
        photo = request.FILES.get("photo")

        if name and position and photo:
            Personnel.objects.create(name=name, position=position, email=email, photo=photo)
            messages.success(request, f'Personnel "{name}" added successfully!')
            return redirect("personnel_list")

        messages.error(request, "Name, position, and photo are required.")

    return render(request, "dashboard/admin/personnel_form.html")


@login_required
@admin_required
def personnel_edit(request, pk):
    person = get_object_or_404(Personnel, pk=pk)

    if request.method == "POST":
        person.name = (request.POST.get("name") or "").strip()
        person.position = (request.POST.get("position") or "").strip()
        person.email = (request.POST.get("email") or "").strip()
        if request.FILES.get("photo"):
            person.photo = request.FILES["photo"]
        person.save()
        messages.success(request, f'"{person.name}" updated successfully!')
        return redirect("personnel_list")

    return render(request, "dashboard/admin/personnel_form.html", {"person": person})


@login_required
@admin_required
def personnel_delete(request, pk):
    person = get_object_or_404(Personnel, pk=pk)
    name = person.name
    person.delete()
    messages.success(request, f'"{name}" deleted successfully!')
    return redirect("personnel_list")


@login_required
@admin_required
def activities_list(request):
    activities = Activity.objects.all().annotate(first_date=Min("dates__date")).order_by("-first_date", "-id")
    return render(request, "dashboard/admin/activities_list.html", {"activities": activities})


@login_required
@admin_required
def activity_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        image = request.FILES.get("image")
        active = request.POST.get("active") == "on"
        dates = request.POST.getlist("dates[]")

        cleaned_dates = [(d or "").strip() for d in dates if (d or "").strip()]

        if title and description and cleaned_dates:
            activity = Activity.objects.create(
                title=title,
                description=description,
                image=image,
                active=active,
            )
            for d in cleaned_dates:
                ActivityDate.objects.get_or_create(activity=activity, date=d)

            messages.success(request, f'Activity "{title}" added successfully!')
            return redirect("activities_list")

        messages.error(request, "Title, description, and at least one date are required.")

    return render(request, "dashboard/admin/activity_form.html")


@login_required
@admin_required
def activity_edit(request, pk):
    activity = get_object_or_404(Activity, pk=pk)

    if request.method == "POST":
        activity.title = (request.POST.get("title") or "").strip()
        activity.description = (request.POST.get("description") or "").strip()
        activity.active = request.POST.get("active") == "on"
        if request.FILES.get("image"):
            activity.image = request.FILES["image"]
        activity.save()

        ActivityDate.objects.filter(activity=activity).delete()
        for d in request.POST.getlist("dates[]"):
            d = (d or "").strip()
            if d:
                ActivityDate.objects.get_or_create(activity=activity, date=d)

        messages.success(request, f'"{activity.title}" updated successfully!')
        return redirect("activities_list")

    return render(request, "dashboard/admin/activity_form.html", {"activity": activity})


@login_required
@admin_required
def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    title = activity.title
    activity.delete()
    messages.success(request, f'"{title}" deleted successfully!')
    return redirect("activities_list")


@login_required
@admin_required
def processes_list(request):
    processes = ExtensionProcess.objects.all().prefetch_related("steps")
    return render(request, "dashboard/admin/processes_list.html", {"processes": processes})


@login_required
@admin_required
def process_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Title is required.")
            return redirect("processes_list")

        process = ExtensionProcess.objects.create(title=title)

        for desc in request.POST.getlist("step_description[]"):
            desc = (desc or "").strip()
            if desc:
                ProcessStep.objects.create(process=process, description=desc)

        messages.success(request, f'Process "{title}" created successfully!')
        return redirect("processes_list")

    return render(request, "dashboard/admin/process_form.html")


@login_required
@admin_required
def process_edit(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)

    if request.method == "POST":
        process.title = (request.POST.get("title") or "").strip()
        process.order = request.POST.get("order") or 0
        process.save()

        step_ids = request.POST.getlist("step_id[]")
        step_descriptions = request.POST.getlist("step_description[]")
        step_orders = request.POST.getlist("step_order[]")

        max_len = max(len(step_ids), len(step_descriptions), len(step_orders), 0)

        def pad(lst, size, fill=""):
            return lst + [fill] * (size - len(lst))

        step_ids = pad(step_ids, max_len)
        step_descriptions = pad(step_descriptions, max_len)
        step_orders = pad(step_orders, max_len, "0")

        valid_step_ids = [sid for sid in step_ids if sid]
        process.steps.exclude(id__in=valid_step_ids).delete()

        for i in range(max_len):
            step_id = step_ids[i].strip()
            desc = step_descriptions[i].strip()
            step_order = step_orders[i].strip() or "0"

            if not desc:
                continue

            if step_id:
                step = ProcessStep.objects.filter(id=step_id, process=process).first()
                if step:
                    step.description = desc
                    step.order = int(step_order)
                    step.save()
            else:
                ProcessStep.objects.create(
                    process=process,
                    description=desc,
                    order=int(step_order),
                )

        messages.success(request, f'Process "{process.title}" updated successfully!')
        return redirect("processes_list")

    return render(request, "dashboard/admin/process_form.html", {"process": process})


@login_required
@admin_required
def process_delete(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)
    title = process.title
    process.delete()
    messages.success(request, f'Process "{title}" deleted successfully!')
    return redirect("processes_list")


@login_required
@admin_required
@require_POST
def reorder_process_steps(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)

    try:
        data = json.loads(request.body.decode("utf-8"))
        step_ids = data.get("step_ids", [])

        for index, step_id in enumerate(step_ids, start=1):
            ProcessStep.objects.filter(process=process, id=step_id).update(order=index)

        return JsonResponse({"ok": True})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


# ==============================
# TARGETS MANAGEMENT
# ==============================

@login_required
@admin_required
def targets_list(request):
    year = request.GET.get("year", 2026)
    targets = Target.objects.filter(year=year).order_by("campus", "metric")
    years = Target.objects.values_list("year", flat=True).distinct().order_by("-year")

    if not years:
        years = [int(year)]

    context = {
        "targets": targets,
        "current_year": int(year),
        "years": years,
    }
    return render(request, "dashboard/admin/targets_list.html", context)


@login_required
@admin_required
def target_create(request):
    campuses = (
        Profile.objects.exclude(campus__isnull=True)
        .exclude(campus__exact="")
        .values_list("campus", flat=True)
        .distinct()
        .order_by("campus")
    )

    if request.method == "POST":
        year = request.POST.get("year")
        campus = request.POST.get("campus")
        metric = request.POST.get("metric")

        if Target.objects.filter(year=year, campus=campus, metric=metric).exists():
            messages.error(request, "Target already exists for this year, campus, and metric.")
            return redirect("targets_list")

        Target.objects.create(
            year=year,
            campus=campus,
            metric=metric,
            planned_q1=request.POST.get("planned_q1", 0),
            planned_q2=request.POST.get("planned_q2", 0),
            planned_q3=request.POST.get("planned_q3", 0),
            planned_q4=request.POST.get("planned_q4", 0),
            actual_q1=request.POST.get("actual_q1", 0),
            actual_q2=request.POST.get("actual_q2", 0),
            actual_q3=request.POST.get("actual_q3", 0),
            actual_q4=request.POST.get("actual_q4", 0),
        )

        messages.success(request, f"Target created for {campus} ({year})")
        return redirect("targets_list")

    return render(request, "dashboard/admin/target_form.html", {"campuses": campuses})


@login_required
@admin_required
def target_edit(request, pk):
    target = get_object_or_404(Target, pk=pk)

    if request.method == "POST":
        target.planned_q1 = request.POST.get("planned_q1", 0)
        target.planned_q2 = request.POST.get("planned_q2", 0)
        target.planned_q3 = request.POST.get("planned_q3", 0)
        target.planned_q4 = request.POST.get("planned_q4", 0)
        target.actual_q1 = request.POST.get("actual_q1", 0)
        target.actual_q2 = request.POST.get("actual_q2", 0)
        target.actual_q3 = request.POST.get("actual_q3", 0)
        target.actual_q4 = request.POST.get("actual_q4", 0)
        target.save()

        messages.success(request, "Target updated successfully!")
        return redirect("targets_list")

    return render(request, "dashboard/admin/target_form.html", {"target": target})


@login_required
@admin_required
def target_delete(request, pk):
    target = get_object_or_404(Target, pk=pk)
    campus = target.campus
    metric = target.get_metric_display()
    year = target.year
    target.delete()

    messages.success(request, f"Target deleted: {campus} - {metric} ({year})")
    return redirect("targets_list")


# ==============================
# FACULTY DRAFT DELETE
# ==============================

@login_required
@faculty_like_required
@require_POST
def faculty_delete_draft(request, proposal_id):
    draft = Proposal.objects.filter(
        id=proposal_id,
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).first()

    if not draft:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "Draft not found."},
                status=404,
            )
        messages.error(request, "Draft not found.")
        return redirect("dashboard_redirect")

    if draft.created_by != request.user:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {"ok": False, "message": "Only the creator can delete this draft."},
                status=403,
            )
        messages.error(request, "Only the creator can delete this draft.")
        return redirect("dashboard_redirect")

    title = draft.title or draft.research_title or "Untitled Draft"
    draft.delete()

    remaining_drafts = Proposal.objects.filter(
        Q(created_by=request.user)
        | Q(proponents__user=request.user)
        | Q(collaborators__user=request.user),
        status=Proposal.OverallStatus.DRAFT,
        proposal_status=Proposal.ProposalStatus.DRAFTING,
    ).distinct().count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "message": f'"{title}" draft deleted successfully.',
            "proposal_id": str(proposal_id),
            "draft_count": remaining_drafts,
        })

    messages.success(request, f'"{title}" draft deleted successfully.')
    return redirect("dashboard_redirect")
