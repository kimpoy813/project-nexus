import random

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from .campus_data import (
    get_campus_choices,
    is_valid_college_for_campus,
    is_valid_department_for_selection,
)


class EmailOTP(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_otp",
    )
    otp = models.CharField(max_length=6, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def generate_otp(self):
        self.otp = f"{random.randint(100000, 999999)}"
        self.is_verified = False
        self.save(update_fields=["otp", "is_verified"])

    def __str__(self):
        return f"OTP for {self.user.username}"


class Profile(models.Model):
    # ==============================
    # ROLE HELPERS
    # ==============================

    @property
    def is_faculty(self):
        return self.role == self.ROLE_FACULTY

    @property
    def is_staff(self):
        return self.role == self.ROLE_STAFF

    @property
    def is_director(self):
        return self.role == self.ROLE_DIRECTOR

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_department_coordinator(self):
        return self.role == self.ROLE_DEPARTMENT_COORDINATOR

    @property
    def is_campus_coordinator(self):
        return self.role == self.ROLE_CAMPUS_COORDINATOR

    @property
    def is_reviewer(self):
        """
        Anyone allowed to review proposals.
        """
        return self.role in [
            self.ROLE_DIRECTOR,
            self.ROLE_DEPARTMENT_COORDINATOR,
            self.ROLE_CAMPUS_COORDINATOR,
        ]

    @property
    def is_staff_or_higher(self):
        """
        Staff-level permissions and above.
        """
        return self.role in [
            self.ROLE_STAFF,
            self.ROLE_DIRECTOR,
            self.ROLE_ADMIN,
        ]

    @property
    def role_safe(self):
        return self.role or self.ROLE_FACULTY

    ROLE_FACULTY = "FACULTY"
    ROLE_DEPARTMENT_COORDINATOR = "DEPARTMENT_COORDINATOR"
    ROLE_CAMPUS_COORDINATOR = "CAMPUS_COORDINATOR"
    ROLE_STAFF = "STAFF"
    ROLE_DIRECTOR = "DIRECTOR"
    ROLE_ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (ROLE_FACULTY, "Faculty"),
        (ROLE_STAFF, "Staff"),
        (ROLE_DEPARTMENT_COORDINATOR, "Department Coordinator"),
        (ROLE_CAMPUS_COORDINATOR, "Campus Coordinator"),
        (ROLE_DIRECTOR, "Director"),
        (ROLE_ADMIN, "Admin"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    full_name = models.CharField(max_length=150, blank=True, default="")

    campus = models.CharField(
        max_length=150,
        choices=get_campus_choices(),
        blank=True,
        default="",
    )
    college = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    department = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default=ROLE_FACULTY,
    )

    email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def display_name(self):
        return self.full_name or self.user.get_username()

    def clean(self):
        super().clean()

        if self.role not in dict(self.ROLE_CHOICES):
            raise ValidationError({"role": "Invalid role selected."})

        # Only validate college if both campus and college are provided
        if self.campus and self.college:
            if not is_valid_college_for_campus(self.campus, self.college):
                raise ValidationError(
                    {"college": "Selected college does not belong to the selected campus."}
                )

        # Only validate department if campus, college, and department are all provided
        if self.campus and self.college and self.department:
            if not is_valid_department_for_selection(
                self.campus,
                self.college,
                self.department,
            ):
                raise ValidationError(
                    {"department": "Selected department does not belong to the selected campus/college."}
                )

    def save(self, *args, **kwargs):
        # Allow callers to pass clean=False (used by bootstrap/profile creation code).
        # Django's base Model.save() does not accept unknown kwargs.
        kwargs.pop("clean", None)

        if not self.full_name:
            first_name = getattr(self.user, "first_name", "").strip()
            last_name = getattr(self.user, "last_name", "").strip()

            if first_name or last_name:
                self.full_name = f"{first_name} {last_name}".strip()
            else:
                self.full_name = self.user.get_username()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_name} ({self.role})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_profile(sender, instance, created, **kwargs):
    profile, profile_created = Profile.objects.get_or_create(
        user=instance,
        defaults={
            "full_name": (
                f"{instance.first_name} {instance.last_name}".strip()
                if instance.first_name or instance.last_name
                else instance.get_username()
            ),
        },
    )

    updated_fields = []

    expected_full_name = (
        f"{instance.first_name} {instance.last_name}".strip()
        if instance.first_name or instance.last_name
        else instance.get_username()
    )

    if not profile.full_name or profile.full_name == instance.get_username():
        if profile.full_name != expected_full_name:
            profile.full_name = expected_full_name
            updated_fields.append("full_name")

    if updated_fields:
        profile.save(update_fields=updated_fields, clean=False)


# ==============================
# SIGNATORIES (ADMIN MANAGED)
# ==============================

class Signatory(models.Model):
    """
    Admin-managed signatories for printed documents.

    You requested NO Active/SortOrder: the system enforces exactly ONE record per:
      (position_title, campus, college, department)

    So you can simply edit the record anytime.
    """

    class Position(models.TextChoices):
        DIRECTOR_EXTENSION = "DIRECTOR_EXTENSION", "Director for Extension"
        DEPARTMENT_EXTENSION_COORDINATOR = "DEPARTMENT_EXTENSION_COORDINATOR", "Department Extension Coordinator"
        DEAN = "DEAN", "Dean"
        CAMPUS_EXTENSION_COORDINATOR = "CAMPUS_EXTENSION_COORDINATOR", "Campus Extension Coordinator"
        CAMPUS_DIRECTOR = "CAMPUS_DIRECTOR", "Campus Director"
        VPRDE = "VPRDE", "Vice President for Research Development and Extension"
        SUC_PRESIDENT_III = "SUC_PRESIDENT_III", "SUC President III"

    position_title = models.CharField(
        max_length=80,
        choices=Position.choices,
        default=Position.DIRECTOR_EXTENSION,
    )

    campus = models.CharField(
        max_length=150,
        choices=get_campus_choices(),
        blank=True,
        default="",
    )
    college = models.CharField(max_length=255, blank=True, default="")
    department = models.CharField(max_length=255, blank=True, default="")

    full_name = models.CharField(max_length=200)
    credentials = models.CharField(max_length=120, blank=True, default="")  # e.g., MSCrim.

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position_title", "campus", "college", "department", "full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["position_title", "campus", "college", "department"],
                name="unique_signatory_per_position_scope",
            ),
        ]

    def __str__(self):
        return f"{self.get_position_title_display()}: {self.display_name} ({self.scope_label})"

    @property
    def display_name(self):
        return f"{self.full_name}{(', ' + self.credentials) if self.credentials else ''}"

    @property
    def scope_label(self):
        parts = []
        if self.campus:
            parts.append(self.campus)
        if self.college:
            parts.append(self.college)
        if self.department:
            parts.append(self.department)
        return " / ".join(parts) if parts else "Global"

    def clean(self):
        super().clean()

        # Normalize blanks
        self.campus = (self.campus or "").strip()
        self.college = (self.college or "").strip()
        self.department = (self.department or "").strip()
        self.full_name = (self.full_name or "").strip()
        self.credentials = (self.credentials or "").strip()

        if not self.full_name:
            raise ValidationError({"full_name": "Full name is required."})

        pos = self.position_title

        campus_only = {self.Position.CAMPUS_EXTENSION_COORDINATOR, self.Position.CAMPUS_DIRECTOR}
        college_scoped = {self.Position.DEAN}
        dept_scoped = {self.Position.DEPARTMENT_EXTENSION_COORDINATOR}
        global_positions = {
            self.Position.DIRECTOR_EXTENSION,
            self.Position.VPRDE,
            self.Position.SUC_PRESIDENT_III,
        }

        # Global scope: no campus/college/department
        if pos in global_positions:
            if self.campus or self.college or self.department:
                raise ValidationError("Global positions must not have campus/college/department set.")

        # Campus scope: campus required; no college/department
        if pos in campus_only:
            if not self.campus:
                raise ValidationError({"campus": "Campus is required for this position."})
            if self.college or self.department:
                raise ValidationError("Campus-scoped positions must not set college/department.")

        # College scope: campus+college required; no department
        if pos in college_scoped:
            if not self.campus:
                raise ValidationError({"campus": "Campus is required for Dean signatory."})
            if not self.college:
                raise ValidationError({"college": "College is required for Dean signatory."})
            if self.department:
                raise ValidationError("College-scoped positions must not set department.")
            if not is_valid_college_for_campus(self.campus, self.college):
                raise ValidationError({"college": "Selected college does not belong to the selected campus."})

        # Department scope: campus+college+department required
        if pos in dept_scoped:
            if not self.campus:
                raise ValidationError({"campus": "Campus is required for Department Extension Coordinator."})
            if not self.college:
                raise ValidationError({"college": "College is required for Department Extension Coordinator."})
            if not self.department:
                raise ValidationError({"department": "Department is required for Department Extension Coordinator."})
            if not is_valid_college_for_campus(self.campus, self.college):
                raise ValidationError({"college": "Selected college does not belong to the selected campus."})
            if not is_valid_department_for_selection(self.campus, self.college, self.department):
                raise ValidationError({"department": "Selected department does not belong to the selected campus/college."})