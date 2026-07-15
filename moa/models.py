# -----------------------------------------------------------------------
# ADD THIS TO: your moa app's models.py (e.g. moa/models.py)
# -----------------------------------------------------------------------
# Assumes you already have a `Proposal` model in your proposal app.
# Adjust the import path below to match your actual project structure.
# -----------------------------------------------------------------------

from django.conf import settings
from django.db import models
from proposals.models import Proposal  # adjust import to your app layout


class MOADocument(models.Model):
    """
    Tracks each MOA file version for a given proposal.
    A new row is created every time a draft is generated OR a signed
    copy is uploaded, so the full history is visible to reviewers.
    """

    STATUS_CHOICES = [
        ("draft_generated", "Draft Generated"),
        ("uploaded", "Uploaded by Coordinator"),
        ("under_review", "Under Review"),
        ("revisions_requested", "Revisions Requested"),
        ("finalized", "Finalized / Signed"),
    ]

    proposal = models.ForeignKey(
        Proposal, on_delete=models.CASCADE, related_name="moa_documents"
    )
    file = models.FileField(upload_to="moa_uploads/%Y/%m/")
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="draft_generated"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewer_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "version"], name="unique_moa_version_per_proposal"
            )
        ]

    def __str__(self):
        return f"MOA v{self.version} — {self.proposal.title} ({self.status})"

    def save(self, *args, **kwargs):
        # Auto-increment version per proposal if not explicitly set
        if self._state.adding and not self.pk:
            last = (
                MOADocument.objects.filter(proposal=self.proposal)
                .order_by("-version")
                .first()
            )
            self.version = (last.version + 1) if last else 1
        super().save(*args, **kwargs)
