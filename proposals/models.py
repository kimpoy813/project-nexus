from datetime import timedelta
import uuid

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Proposal(models.Model):
    class OverallStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "In Progress"
        COMPLETED = "COMPLETED", "Extension Completed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    class ProposalStatus(models.TextChoices):
        DRAFTING = "DRAFTING", "Drafting"
        SUBMITTED_FOR_REVIEW = "SUBMITTED_FOR_REVIEW", "Submitted for Review"
        IN_REVIEW = "IN_REVIEW", "In Review"
        REVIEW_SUMMARY_ISSUED = "REVIEW_SUMMARY_ISSUED", "Review Summary Issued"
        FOR_REVISION = "FOR_REVISION", "For Revision"
        READY_FOR_PRINTING = "READY_FOR_PRINTING", "Ready to Print"
        FOR_SUBMISSION_AND_UPLOAD = "FOR_SUBMISSION_AND_UPLOAD", "Submission & Uploading of the Proposal"
        APPROVED = "APPROVED", "Approved / Claiming"
        COMPLETED = "COMPLETED", "Proposal Completed"

    class MOAStatus(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not Required"
        NOT_STARTED = "NOT_STARTED", "Not Started"
        DRAFT = "DRAFT", "Draft"
        LEGAL_REVIEW = "LEGAL_REVIEW", "Legal Review"
        FOR_REVISION = "FOR_REVISION", "Under Revision"
        CERTIFICATION_READY = "CERTIFICATION_READY", "Certification Ready"
        AGENDA_AND_PRESENTATION = "AGENDA_AND_PRESENTATION", "Agenda Brief & Presentation"
        COMPLETED = "COMPLETED", "MOA Completed"

    class ImplementationStatus(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        PREPARATION = "PREPARATION", "Preparation"
        MONITORING = "MONITORING", "Monitoring"
        POST_ACTIVITY_REPORT = "POST_ACTIVITY_REPORT", "Post Activity Report / Progress Report"
        TERMINAL_REPORT = "TERMINAL_REPORT", "Terminal Report"
        TERMINAL_REVIEW = "TERMINAL_REVIEW", "Review of Terminal Report"
        REVISION = "REVISION", "Revision"
        COMPLETED = "COMPLETED", "Implementation Completed"

    class ExtensionType(models.TextChoices):
        RESEARCH_FACULTY = "RESEARCH_FACULTY", "Research-based (Faculty)"
        RESEARCH_STUDENT = "RESEARCH_STUDENT", "Research-based (Student)"
        REQUEST_BASED = "REQUEST_BASED", "Request-based"
        COMMUNITY_BASED = "COMMUNITY_BASED", "Community-based"

    class ScopeType(models.TextChoices):
        PROGRAM = "PROGRAM", "Program"
        PROJECT = "PROJECT", "Project"
        ACTIVITY = "ACTIVITY", "Activity only"

    class ReviewLevel(models.TextChoices):
        DEPARTMENT = "DEPARTMENT", "Department"
        CAMPUS = "CAMPUS", "Campus"
        DIRECTOR = "DIRECTOR", "Director"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="proposals_created",
    )

    campus = models.CharField(max_length=120, blank=True, default="")
    college = models.CharField(max_length=120, blank=True, default="")
    department = models.CharField(max_length=120, blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=OverallStatus.choices,
        default=OverallStatus.DRAFT,
    )
    proposal_status = models.CharField(
        max_length=40,
        choices=ProposalStatus.choices,
        default=ProposalStatus.DRAFTING,
    )
    moa_status = models.CharField(
        max_length=30,
        choices=MOAStatus.choices,
        default=MOAStatus.NOT_STARTED,
    )
    implementation_status = models.CharField(
        max_length=30,
        choices=ImplementationStatus.choices,
        default=ImplementationStatus.NOT_STARTED,
    )
    review_level = models.CharField(
        max_length=20,
        choices=ReviewLevel.choices,
        blank=True,
        default="",
    )

    current_step = models.PositiveSmallIntegerField(default=1)
    completed_steps = models.JSONField(default=list, blank=True)
    skipped_steps = models.JSONField(default=list, blank=True)
    last_saved_at = models.DateTimeField(auto_now=True)

    highest_proposal_progress = models.PositiveSmallIntegerField(default=0)
    highest_moa_progress = models.PositiveSmallIntegerField(default=0)
    highest_implementation_progress = models.PositiveSmallIntegerField(default=0)

    requires_moa = models.BooleanField(default=True)

    extension_type = models.CharField(
        max_length=40,
        choices=ExtensionType.choices,
        blank=True,
        default="",
    )
    scope_type = models.CharField(
        max_length=20,
        choices=ScopeType.choices,
        blank=True,
        default="",
    )

    research_title = models.CharField(max_length=300, blank=True, default="")
    title = models.CharField(max_length=300, blank=True, default="")

    implementing_agency = models.CharField(max_length=255, blank=True, default="")
    budgetary_requirement = models.CharField(max_length=255, blank=True, default="")

    beneficiaries_count = models.PositiveIntegerField(null=True, blank=True)
    beneficiaries_who = models.TextField(blank=True, default="")

    estimated_month = models.CharField(max_length=20, blank=True, default="")
    estimated_year = models.PositiveIntegerField(null=True, blank=True)
    extension_venue = models.CharField(max_length=255, blank=True, default="")

    rationale_background = models.TextField(blank=True, default="")
    significance = models.TextField(blank=True, default="")
    general_objective = models.TextField(blank=True, default="")

    sex_male = models.PositiveIntegerField(default=0, blank=True)
    sex_female = models.PositiveIntegerField(default=0, blank=True)
    g_lesbian = models.PositiveIntegerField(default=0, blank=True)
    g_gay = models.PositiveIntegerField(default=0, blank=True)
    g_bisexual = models.PositiveIntegerField(default=0, blank=True)
    g_transgender = models.PositiveIntegerField(default=0, blank=True)
    g_straight = models.PositiveIntegerField(default=0, blank=True)
    g_others = models.PositiveIntegerField(default=0, blank=True)

    work_plan_file = models.FileField(
        upload_to="proposal_files/work_plans/",
        blank=True,
        null=True,
    )
    gantt_chart_file = models.FileField(
        upload_to="proposal_files/gantt_charts/",
        blank=True,
        null=True,
    )
    funding_file = models.FileField(
        upload_to="proposal_files/funding/",
        blank=True,
        null=True,
    )
    research_abstract_file = models.FileField(
        upload_to="proposal_files/research_abstracts/",
        blank=True,
        null=True,
    )
    certificate_of_completion_file = models.FileField(
        upload_to="proposal_files/certificates_of_completion/",
        blank=True,
        null=True,
    )

    is_locked = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    letter_of_award_released_at = models.DateTimeField(null=True, blank=True)
    endorsement_released_at = models.DateTimeField(null=True, blank=True)
    extension_agreement_released_at = models.DateTimeField(null=True, blank=True)
    moa_started_at = models.DateTimeField(null=True, blank=True)
    moa_signed_at = models.DateTimeField(null=True, blank=True)
    implementation_started_at = models.DateTimeField(null=True, blank=True)
    implementation_completed_at = models.DateTimeField(null=True, blank=True)
    partial_reports_submitted_at = models.DateTimeField(null=True, blank=True)
    final_reports_submitted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    participants_total = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    date_venue = models.TextField(blank=True, default="")
    extension_site = models.CharField(max_length=255, blank=True, default="")
    rationale = models.TextField(blank=True, default="")
    objectives_general = models.TextField(blank=True, default="")
    objectives_specific = models.TextField(blank=True, default="")
    methodology = models.TextField(blank=True, default="")
    output_outcome = models.TextField(blank=True, default="")
    monitoring_eval = models.TextField(blank=True, default="")
    gender_issues = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-last_saved_at"]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title or self.research_title or f"Proposal {self.pk}"

    @property
    def total_participants_profiled(self):
        return (
            (self.sex_male or 0)
            + (self.sex_female or 0)
            + (self.g_lesbian or 0)
            + (self.g_gay or 0)
            + (self.g_bisexual or 0)
            + (self.g_transgender or 0)
            + (self.g_straight or 0)
            + (self.g_others or 0)
        )

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be earlier than start date.")
        if self.current_step < 1:
            raise ValidationError("Current step must be at least 1.")

    def save(self, *args, **kwargs):
        self.sync_overall_status()
        self.sync_highest_progress()
        self.full_clean()
        super().save(*args, **kwargs)

    def get_current_review_round(self):
        return self.review_rounds.order_by("-round_no").first()

    def get_active_review_round(self):
        return self.review_rounds.filter(is_closed=False).order_by("-round_no").first()

    def start_review_round(self):
        ProposalReviewRound = apps.get_model("proposals", "ProposalReviewRound")

        active_round = self.get_active_review_round()
        if active_round:
            return active_round

        current = self.get_current_review_round()
        next_round_no = 1 if not current else current.round_no + 1

        return ProposalReviewRound.objects.create(
            proposal=self,
            round_no=next_round_no,
        )
    
    def resubmit(self):
        current_round = self.get_current_review_round()

        if current_round:
            current_round.is_closed = True
            current_round.ready_for_staff_summary = False
            current_round.save()

        self.is_locked = False
        self.start_review_round()
        self.transition_proposal_status(self.ProposalStatus.SUBMITTED_FOR_REVIEW)
        self.save()

    def resubmit_for_recheck(self):
        ProposalEvaluatorAssignment = apps.get_model(
            "proposals",
            "ProposalEvaluatorAssignment",
        )

        current_round = self.get_active_review_round()
        if not current_round:
            current_round = self.start_review_round()

        ProposalEvaluatorAssignment.objects.filter(
            proposal=self,
            review_round=current_round,
            is_active=True,
        ).update(is_completed=False)

        current_round.evaluator_review_done = False
        current_round.director_review_done = False
        current_round.ready_for_staff_summary = False
        current_round.save(
            update_fields=[
                "evaluator_review_done",
                "director_review_done",
                "ready_for_staff_summary",
            ]
        )

        self.transition_proposal_status(
            self.ProposalStatus.SUBMITTED_FOR_REVIEW
        )

    PROPOSAL_PROGRESS_MAP = {
        ProposalStatus.DRAFTING: 10,
        ProposalStatus.SUBMITTED_FOR_REVIEW: 25,
        ProposalStatus.IN_REVIEW: 40,
        ProposalStatus.REVIEW_SUMMARY_ISSUED: 50,
        ProposalStatus.FOR_REVISION: 55,
        ProposalStatus.READY_FOR_PRINTING: 70,
        ProposalStatus.FOR_SUBMISSION_AND_UPLOAD: 85,
        ProposalStatus.APPROVED: 95,
        ProposalStatus.COMPLETED: 100,
    }

    MOA_PROGRESS_MAP = {
        MOAStatus.NOT_REQUIRED: 100,
        MOAStatus.NOT_STARTED: 0,
        MOAStatus.DRAFT: 15,
        MOAStatus.LEGAL_REVIEW: 35,
        MOAStatus.FOR_REVISION: 50,
        MOAStatus.CERTIFICATION_READY: 70,
        MOAStatus.AGENDA_AND_PRESENTATION: 85,
        MOAStatus.COMPLETED: 100,
    }

    IMPLEMENTATION_PROGRESS_MAP = {
        ImplementationStatus.NOT_STARTED: 0,
        ImplementationStatus.PREPARATION: 15,
        ImplementationStatus.MONITORING: 35,
        ImplementationStatus.POST_ACTIVITY_REPORT: 55,
        ImplementationStatus.TERMINAL_REPORT: 70,
        ImplementationStatus.TERMINAL_REVIEW: 82,
        ImplementationStatus.REVISION: 88,
        ImplementationStatus.COMPLETED: 100,
    }

    @property
    def proposal_progress(self):
        return self.PROPOSAL_PROGRESS_MAP.get(self.proposal_status, 0)

    @property
    def moa_progress(self):
        return self.MOA_PROGRESS_MAP.get(self.moa_status, 0)

    @property
    def implementation_progress(self):
        return self.IMPLEMENTATION_PROGRESS_MAP.get(self.implementation_status, 0)

    @property
    def overall_progress(self):
        if self.status == self.OverallStatus.COMPLETED:
            return 100
        if self.status in {self.OverallStatus.REJECTED, self.OverallStatus.CANCELLED}:
            return 0

        if self.requires_moa:
            return round(
                (self.proposal_progress * 0.40)
                + (self.moa_progress * 0.20)
                + (self.implementation_progress * 0.40)
            )

        return round(
            (self.proposal_progress * 0.50)
            + (self.implementation_progress * 0.50)
        )

    @property
    def current_phase_label(self):
        if self.status == self.OverallStatus.COMPLETED:
            return "Extension Finished"
        if self.implementation_status != self.ImplementationStatus.NOT_STARTED:
            return "Implementation"
        if self.requires_moa and self.moa_status not in {
            self.MOAStatus.NOT_STARTED,
            self.MOAStatus.NOT_REQUIRED,
        }:
            return "MOA"
        return "Proposal"

    @property
    def current_status_label(self):
        if self.status == self.OverallStatus.COMPLETED:
            return "Extension Finished"
        if self.current_phase_label == "Implementation":
            return self.get_implementation_status_display()
        if self.current_phase_label == "MOA":
            return self.get_moa_status_display()
        return self.get_proposal_status_display()

    def sync_highest_progress(self):
        self.highest_proposal_progress = max(
            self.highest_proposal_progress or 0,
            self.proposal_progress,
        )
        self.highest_moa_progress = max(
            self.highest_moa_progress or 0,
            self.moa_progress,
        )
        self.highest_implementation_progress = max(
            self.highest_implementation_progress or 0,
            self.implementation_progress,
        )

    def sync_overall_status(self):
        if self.status in {self.OverallStatus.REJECTED, self.OverallStatus.CANCELLED}:
            return

        if (
            self.proposal_status == self.ProposalStatus.COMPLETED
            and (
                not self.requires_moa
                or self.moa_status in {self.MOAStatus.NOT_REQUIRED, self.MOAStatus.COMPLETED}
            )
            and self.implementation_status == self.ImplementationStatus.COMPLETED
        ):
            self.status = self.OverallStatus.COMPLETED
            if not self.closed_at:
                self.closed_at = timezone.now()
            return

        if (
            self.proposal_status != self.ProposalStatus.DRAFTING
            or self.moa_status != self.MOAStatus.NOT_STARTED
            or self.implementation_status != self.ImplementationStatus.NOT_STARTED
        ):
            self.status = self.OverallStatus.ACTIVE
        else:
            self.status = self.OverallStatus.DRAFT

    def lock_and_submit(self):
        self.proposal_status = self.ProposalStatus.SUBMITTED_FOR_REVIEW
        self.review_level = self.ReviewLevel.DEPARTMENT
        self.is_locked = True
        if not self.submitted_at:
            self.submitted_at = timezone.now()
        self.save(
            update_fields=[
                "proposal_status",
                "review_level",
                "is_locked",
                "submitted_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_in_review(self, review_level=""):
        self.proposal_status = self.ProposalStatus.IN_REVIEW
        if review_level in {
            self.ReviewLevel.DEPARTMENT,
            self.ReviewLevel.CAMPUS,
            self.ReviewLevel.DIRECTOR,
        }:
            self.review_level = review_level
        self.save(
            update_fields=[
                "proposal_status",
                "review_level",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def transition_proposal_status(self, new_status):
        """
        Strict workflow control for proposal-phase statuses.

        Lifecycle:
            DRAFTING -> SUBMITTED_FOR_REVIEW -> IN_REVIEW -> (FOR_REVISION -> SUBMITTED_FOR_REVIEW)*
            IN_REVIEW -> READY_FOR_PRINTING
            READY_FOR_PRINTING -> FOR_SUBMISSION_AND_UPLOAD
            FOR_SUBMISSION_AND_UPLOAD -> APPROVED
            APPROVED -> COMPLETED
        """

        allowed = {
            self.ProposalStatus.SUBMITTED_FOR_REVIEW: [
                self.ProposalStatus.IN_REVIEW,
            ],
            self.ProposalStatus.IN_REVIEW: [
                self.ProposalStatus.FOR_REVISION,
                self.ProposalStatus.READY_FOR_PRINTING,  # director clears for printing
            ],
            self.ProposalStatus.FOR_REVISION: [
                self.ProposalStatus.SUBMITTED_FOR_REVIEW,  # resubmission creates new round
            ],
            self.ProposalStatus.READY_FOR_PRINTING: [
                self.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,  # proponent downloads/prints
            ],
            self.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD: [
                self.ProposalStatus.APPROVED,  # proponent uploads signed proposal
            ],
            self.ProposalStatus.APPROVED: [
                self.ProposalStatus.COMPLETED,  # staff releases final documents
            ],
        }

        current = self.proposal_status

        if new_status not in allowed.get(current, []):
            raise ValidationError(f"Invalid transition: {current} → {new_status}")

        self.proposal_status = new_status

        # Lock behavior
        if new_status in {
            self.ProposalStatus.SUBMITTED_FOR_REVIEW,
            self.ProposalStatus.READY_FOR_PRINTING,
            self.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
            self.ProposalStatus.APPROVED,
            self.ProposalStatus.COMPLETED,
        }:
            self.is_locked = True
        elif new_status == self.ProposalStatus.FOR_REVISION:
            self.is_locked = False

        # Review level is only meaningful during review
        if new_status in {
            self.ProposalStatus.READY_FOR_PRINTING,
            self.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD,
            self.ProposalStatus.APPROVED,
            self.ProposalStatus.COMPLETED,
        }:
            self.review_level = ""

        if new_status == self.ProposalStatus.APPROVED and not self.approved_at:
            self.approved_at = timezone.now()

        self.save(update_fields=["proposal_status", "is_locked", "review_level", "approved_at"])

    def return_for_revision(self):
        self.proposal_status = self.ProposalStatus.FOR_REVISION
        self.is_locked = False
        self.save(
            update_fields=[
                "proposal_status",
                "is_locked",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_ready_for_printing(self):
        # Director has cleared the proposal for printing (not final approval yet).
        self.proposal_status = self.ProposalStatus.READY_FOR_PRINTING
        self.review_level = ""
        self.is_locked = True
        self.save(
            update_fields=[
                "proposal_status",
                "review_level",
                "is_locked",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_for_submission_and_upload(self):
        # Proponent has printed/downloaded the proposal and should now upload signed copies.
        self.proposal_status = self.ProposalStatus.FOR_SUBMISSION_AND_UPLOAD
        self.review_level = ""
        self.is_locked = True
        self.save(
            update_fields=[
                "proposal_status",
                "review_level",
                "is_locked",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def approve_proposal(self):
        self.proposal_status = self.ProposalStatus.APPROVED
        self.review_level = ""
        self.is_locked = True
        if not self.approved_at:
            self.approved_at = timezone.now()
        self.save(
            update_fields=[
                "proposal_status",
                "review_level",
                "is_locked",
                "approved_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_proposal_completed(self):
        # Proposal phase completed: staff has released LOA, Endorsement, and Extension Agreement.
        self.proposal_status = self.ProposalStatus.COMPLETED
        self.is_locked = True
        self.save(
            update_fields=[
                "proposal_status",
                "is_locked",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_rejected(self):
        self.status = self.OverallStatus.REJECTED
        self.review_level = ""
        self.save(update_fields=["status", "review_level", "last_saved_at"])

    def mark_cancelled(self):
        self.status = self.OverallStatus.CANCELLED
        self.save(update_fields=["status", "last_saved_at"])

    def mark_moa_not_required(self):
        self.requires_moa = False
        self.moa_status = self.MOAStatus.NOT_REQUIRED
        self.save(
            update_fields=[
                "requires_moa",
                "moa_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_moa_draft(self):
        self.requires_moa = True
        self.moa_status = self.MOAStatus.DRAFT
        if not self.moa_started_at:
            self.moa_started_at = timezone.now()
        self.save(
            update_fields=[
                "requires_moa",
                "moa_status",
                "moa_started_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_moa_legal_review(self):
        self.moa_status = self.MOAStatus.LEGAL_REVIEW
        self.save(
            update_fields=[
                "moa_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_moa_for_revision(self):
        self.moa_status = self.MOAStatus.FOR_REVISION
        self.save(
            update_fields=[
                "moa_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_moa_certification_ready(self):
        self.moa_status = self.MOAStatus.CERTIFICATION_READY
        self.save(
            update_fields=[
                "moa_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_moa_agenda_and_presentation(self):
        self.moa_status = self.MOAStatus.AGENDA_AND_PRESENTATION
        self.save(
            update_fields=[
                "moa_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_moa_completed(self):
        self.moa_status = self.MOAStatus.COMPLETED
        if not self.moa_signed_at:
            self.moa_signed_at = timezone.now()
        self.save(
            update_fields=[
                "moa_status",
                "moa_signed_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_implementation_preparation(self):
        self.implementation_status = self.ImplementationStatus.PREPARATION
        if not self.implementation_started_at:
            self.implementation_started_at = timezone.now()
        self.save(
            update_fields=[
                "implementation_status",
                "implementation_started_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_implementation_monitoring(self):
        self.implementation_status = self.ImplementationStatus.MONITORING
        self.save(
            update_fields=[
                "implementation_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_post_activity_report(self):
        self.implementation_status = self.ImplementationStatus.POST_ACTIVITY_REPORT
        if not self.partial_reports_submitted_at:
            self.partial_reports_submitted_at = timezone.now()
        self.save(
            update_fields=[
                "implementation_status",
                "partial_reports_submitted_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_terminal_report(self):
        self.implementation_status = self.ImplementationStatus.TERMINAL_REPORT
        if not self.final_reports_submitted_at:
            self.final_reports_submitted_at = timezone.now()
        self.save(
            update_fields=[
                "implementation_status",
                "final_reports_submitted_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_terminal_review(self):
        self.implementation_status = self.ImplementationStatus.TERMINAL_REVIEW
        self.save(
            update_fields=[
                "implementation_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_implementation_revision(self):
        self.implementation_status = self.ImplementationStatus.REVISION
        self.save(
            update_fields=[
                "implementation_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_implementation_completed(self):
        self.implementation_status = self.ImplementationStatus.COMPLETED
        if not self.implementation_completed_at:
            self.implementation_completed_at = timezone.now()
        if not self.final_reports_submitted_at:
            self.final_reports_submitted_at = timezone.now()
        self.save(
            update_fields=[
                "implementation_status",
                "implementation_completed_at",
                "final_reports_submitted_at",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )

    def mark_closed(self):
        self.proposal_status = self.ProposalStatus.COMPLETED
        if self.requires_moa and self.moa_status == self.MOAStatus.NOT_STARTED:
            self.moa_status = self.MOAStatus.COMPLETED
        if self.implementation_status != self.ImplementationStatus.COMPLETED:
            self.implementation_status = self.ImplementationStatus.COMPLETED
        self.status = self.OverallStatus.COMPLETED
        if not self.closed_at:
            self.closed_at = timezone.now()
        self.save(
            update_fields=[
                "proposal_status",
                "moa_status",
                "implementation_status",
                "status",
                "closed_at",
                "highest_proposal_progress",
                "highest_moa_progress",
                "highest_implementation_progress",
                "last_saved_at",
            ]
        )


class ProposalCollaborator(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="collaborators",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposal_collaborations",
    )
    can_edit = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "user"],
                name="unique_proposal_collaborator",
            )
        ]

    def __str__(self):
        return f"{self.user} -> {self.proposal}"


class ProposalProponent(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="proponents",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposal_proponentships",
    )
    full_name = models.CharField(max_length=200)
    designation = models.CharField(max_length=200, blank=True, default="")
    specialization = models.CharField(max_length=200, blank=True, default="")
    role = models.CharField(max_length=120, blank=True, default="")
    cp_number = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "user"],
                condition=Q(user__isnull=False),
                name="unique_proposal_proponent_user_nonnull",
            )
        ]

    def __str__(self):
        return self.full_name


class SDG(models.Model):
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code}: {self.title}"


class ExtensionThrust(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class ParticipantsProfiling(models.Model):
    proposal = models.OneToOneField(
        Proposal,
        on_delete=models.CASCADE,
        related_name="profiling",
    )
    sex_male = models.PositiveIntegerField(null=True, blank=True)
    sex_female = models.PositiveIntegerField(null=True, blank=True)
    gender_lesbian = models.PositiveIntegerField(null=True, blank=True)
    gender_gay = models.PositiveIntegerField(null=True, blank=True)
    gender_bisexual = models.PositiveIntegerField(null=True, blank=True)
    gender_transgender = models.PositiveIntegerField(null=True, blank=True)
    gender_straight_male = models.PositiveIntegerField(null=True, blank=True)
    gender_straight_female = models.PositiveIntegerField(null=True, blank=True)
    gender_others = models.PositiveIntegerField(null=True, blank=True)
    gender_others_specify = models.CharField(max_length=120, blank=True, default="")

    @property
    def sex_total(self):
        return (self.sex_male or 0) + (self.sex_female or 0)

    def __str__(self):
        return f"Profiling for {self.proposal}"


class ProposalImpact(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="impacts",
    )
    campus = models.CharField(max_length=120)
    year = models.PositiveIntegerField()
    metric = models.CharField(max_length=50)
    value = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.proposal} - {self.metric} ({self.year})"


class ProgramProject(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="program_projects",
    )
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    leader_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_program_projects",
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class ProposalSDG(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="sdg_links",
    )
    sdg_code = models.CharField(max_length=30, null=True, blank=True)
    explanation = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "sdg_code"],
                name="unique_proposal_sdg",
            )
        ]

    def __str__(self):
        return f"{self.proposal} - SDG {self.sdg_code}"


class ProposalThrust(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="thrust_links",
    )
    thrust_name = models.CharField(max_length=255, null=True, blank=True)
    explanation = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "thrust_name"],
                name="unique_proposal_thrust",
            )
        ]

    def __str__(self):
        return f"{self.proposal} - {self.thrust_name}"


class ProposalGenderIssue(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="gender_issue_links",
    )
    issue_key = models.CharField(max_length=100)
    issue_label = models.TextField()
    other_text = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.proposal_id} - {self.issue_key}"


class ProposalEditorPresence(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="editor_presences",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposal_editor_presences",
    )
    step = models.PositiveIntegerField(default=1)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "user"],
                name="unique_proposal_editor_presence",
            )
        ]

    def __str__(self):
        return f"{self.user} editing Proposal {self.proposal_id}"

    @property
    def is_active(self):
        return self.last_seen >= timezone.now() - timedelta(seconds=45)


class ProposalSpecificObjective(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="specific_objectives",
    )
    program_project = models.ForeignKey(
        ProgramProject,
        on_delete=models.CASCADE,
        related_name="specific_objectives",
        blank=True,
        null=True,
    )
    objective = models.TextField()

    def __str__(self):
        if self.program_project:
            return f"{self.program_project.title}: {self.objective[:50]}"
        return self.objective[:50]


class ProposalMethodology(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="methodologies",
    )
    item = models.TextField()

    def __str__(self):
        return self.item[:50]


class ProposalOutputOutcome(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="output_outcomes",
    )
    item = models.TextField()

    def __str__(self):
        return self.item[:50]


class ProposalAttachment(models.Model):
    class Category(models.TextChoices):
        DETAILS_OF_ACTIVITIES = "details_of_activities", "Details of Activities"
        MONITORING_EVAL = "monitoring_eval", "Monitoring and Evaluation"
        ABSTRACT = "abstract", "Research Abstract"
        CERT_COMPLETION = "cert_completion", "Certificate of Completion"
        OTHER = "other", "Other"

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="proposal_files/attachments/")
    label = models.CharField(max_length=255, blank=True, default="")
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.DETAILS_OF_ACTIVITIES,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.label or self.file.name


class ProposalReviewRound(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="review_rounds",
    )
    round_no = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)

    department_review_done = models.BooleanField(default=False)
    campus_review_done = models.BooleanField(default=False)
    director_review_done = models.BooleanField(default=False)

    evaluator_review_required = models.BooleanField(default=False)
    evaluator_review_done = models.BooleanField(default=False)

    ready_for_staff_summary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "round_no"],
                name="unique_proposal_review_round",
            )
        ]
        ordering = ["round_no"]

    def __str__(self):
        return f"{self.proposal} - Review Round {self.round_no}"

    def clean(self):
        if self.ready_for_staff_summary and not self.director_review_done:
            raise ValidationError(
                "Director review must be completed before marking ready for staff summary."
            )

        if self.evaluator_review_done and not self.evaluator_review_required:
            raise ValidationError(
                "Evaluator review cannot be marked done if evaluator review is not required."
            )

        if (
            self.ready_for_staff_summary
            and self.evaluator_review_required
            and not self.evaluator_review_done
        ):
            raise ValidationError(
                "Evaluator review must be completed before marking ready for staff summary."
            )

        if self.is_closed and not self.ready_for_staff_summary:
            raise ValidationError(
                "A review round should not be closed before it is ready for staff summary."
            )

    def refresh_evaluator_review_done(self):
        active_assignments = self.evaluator_assignments.filter(is_active=True)

        if not self.evaluator_review_required:
            self.evaluator_review_done = False
        elif not active_assignments.exists():
            self.evaluator_review_done = False
        else:
            self.evaluator_review_done = not active_assignments.filter(
                is_completed=False
            ).exists()

        self.save(update_fields=["evaluator_review_done"])

    def can_be_marked_ready_for_summary(self):
        if not self.director_review_done:
            return False
        if self.evaluator_review_required and not self.evaluator_review_done:
            return False
        return True

    def mark_ready_for_staff_summary(self):
        if not self.director_review_done:
            raise ValidationError("Director review must be completed.")
        self.ready_for_staff_summary = True
        self.save(update_fields=["ready_for_staff_summary"])


class ProposalSectionComment(models.Model):
    class ReviewerRole(models.TextChoices):
        DEPARTMENT_COORDINATOR = "DEPARTMENT_COORDINATOR", "Department Coordinator"
        CAMPUS_COORDINATOR = "CAMPUS_COORDINATOR", "Campus Coordinator"
        DIRECTOR = "DIRECTOR", "Director"
        EVALUATOR = "EVALUATOR", "Evaluator"

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="section_comments",
    )
    review_round = models.ForeignKey(
        ProposalReviewRound,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposal_section_comments",
    )
    reviewer_role = models.CharField(max_length=50, choices=ReviewerRole.choices)
    step_no = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    is_visible_to_proponent = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "review_round", "reviewer", "step_no"],
                name="unique_section_comment_per_reviewer_step_round",
            )
        ]
        ordering = ["step_no", "created_at"]

    def clean(self):
        if self.review_round.proposal_id != self.proposal_id:
            raise ValidationError("Review round does not belong to the selected proposal.")

    def __str__(self):
        return f"{self.proposal} - Round {self.review_round.round_no} - Step {self.step_no}"


class ProposalEvaluatorAssignment(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="evaluator_assignments",
    )
    review_round = models.ForeignKey(
        ProposalReviewRound,
        on_delete=models.CASCADE,
        related_name="evaluator_assignments",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposal_evaluator_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_evaluators",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "review_round", "evaluator"],
                name="unique_evaluator_assignment_per_round",
            )
        ]
        ordering = ["-assigned_at"]

    def clean(self):
        if self.review_round.proposal_id != self.proposal_id:
            raise ValidationError("Review round does not belong to the selected proposal.")

        assigner_profile = getattr(self.assigned_by, "profile", None)
        if not assigner_profile or assigner_profile.role != "DIRECTOR":
            raise ValidationError("Only a Director can assign evaluators.")

        evaluator_profile = getattr(self.evaluator, "profile", None)
        allowed_roles = {"FACULTY", "DEPARTMENT_COORDINATOR", "CAMPUS_COORDINATOR"}
        if not evaluator_profile or evaluator_profile.role not in allowed_roles:
            raise ValidationError("Selected user is not eligible to be assigned as evaluator.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.proposal} - {self.evaluator} - Round {self.review_round.round_no}"


class ProposalCommentSummary(models.Model):
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="comment_summaries",
    )
    review_round = models.ForeignKey(
        ProposalReviewRound,
        on_delete=models.CASCADE,
        related_name="summaries",
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposal_comment_summaries",
    )
    summary_text = models.TextField()
    sent_to_proponent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "review_round"],
                name="unique_comment_summary_per_round",
            )
        ]
        ordering = ["-created_at"]

    def clean(self):
        if self.review_round.proposal_id != self.proposal_id:
            raise ValidationError("Review round does not belong to the selected proposal.")

    def __str__(self):
        return f"{self.proposal} - Summary Round {self.review_round.round_no}"


class ProposalFinalDocument(models.Model):
    class DocumentType(models.TextChoices):
        SIGNED_PROPOSAL = "SIGNED_PROPOSAL", "Signed Proposal"
        EXTENSION_AGREEMENT = "EXTENSION_AGREEMENT", "Extension Agreement"
        ENDORSEMENT_FOR_APPROVAL = "ENDORSEMENT_FOR_APPROVAL", "Endorsement for Approval"
        LETTER_OF_AWARD = "LETTER_OF_AWARD", "Letter of Award"
        MOA = "MOA", "Memorandum of Agreement"
        REPORT_PARTIAL = "REPORT_PARTIAL", "Partial Report"
        REPORT_FINAL = "REPORT_FINAL", "Final Report"
        OTHER = "OTHER", "Other"

    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="final_documents",
    )
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    file = models.FileField(upload_to="proposal_final_documents/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_proposal_final_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, default="")
    is_verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "document_type"],
                name="unique_final_document_type_per_proposal",
            )
        ]
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.proposal} - {self.get_document_type_display()}"
    
@property
def has_draft_summary(self):
    return ProposalCommentSummary.objects.filter(
        proposal=self,
        sent_to_proponent=False
    ).exists()


@property
def summary_sent(self):
    return ProposalCommentSummary.objects.filter(
        proposal=self,
        sent_to_proponent=True
    ).exists()