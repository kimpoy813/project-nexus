"""
Admin user management: account creation, editing, roles, and site controls.
"""
import logging

import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from proposals.models import Proposal
from ..decorators import admin_required
from ..campus_data import get_campus_choices
from ..forms import AdminCreateUserForm
from ..models import Profile
from ..models import SiteConfiguration
from ..models import SiteConfigurationLog

logger = logging.getLogger(__name__)
from .helpers import User, _get_or_create_profile


def _campus_choices_with_saved(choices, saved):
    """Return campus choices, ensuring a saved (possibly legacy) value stays selectable."""
    values = list(choices)
    if saved and saved not in values:
        values.append(saved)
    return values


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

            except Exception:
                logger.exception("Admin account creation failed.")
                messages.error(
                    request,
                    "Could not create the account. The error has been logged.",
                )
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
        except Exception:
            logger.exception("Admin failed to update user %s.", user_obj.pk)
            messages.error(
                request,
                "Could not update this user. The error has been logged.",
            )

    return render(
        request,
        "accounts/admin_edit_user.html",
        {
            "edit_user": user_obj,
            "edit_profile": profile,
            "role_choices": Profile.ROLE_CHOICES,
            # Live campus list from the admin-managed Campus table so newly
            # created or renamed campuses appear here immediately. The user's
            # saved campus is kept in the list even when it is no longer a
            # managed campus, so a plain re-save never silently changes it.
            "campus_choices": _campus_choices_with_saved(
                [value for value, _label in get_campus_choices()],
                profile.campus or "",
            ),
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


def _site_configuration_snapshot(config):
    return {
        "site_name": config.site_name,
        "short_name": config.short_name,
        "tagline": config.tagline,
        "contact_email": config.contact_email,
        "facebook_url": config.facebook_url,
        "primary_color": config.primary_color,
        "secondary_color": config.secondary_color,
        "accent_color": config.accent_color,
        "announcement_enabled": config.announcement_enabled,
        "announcement_title": config.announcement_title,
        "announcement_message": config.announcement_message,
        "announcement_tone": config.announcement_tone,
        "registration_enabled": config.registration_enabled,
        "maintenance_mode": config.maintenance_mode,
        "maintenance_message": config.maintenance_message,
    }


@login_required
@admin_required
@require_POST
def admin_site_control(request):
    config = SiteConfiguration.get_solo()
    before = _site_configuration_snapshot(config)

    def clean_text(name, default=""):
        return (request.POST.get(name) or default).strip()

    def clean_hex(name, fallback):
        value = clean_text(name, fallback)
        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            return fallback
        return value

    config.site_name = clean_text("site_name", config.site_name) or "NExUS"
    config.short_name = clean_text("short_name", config.short_name) or "NExUS"
    config.tagline = clean_text("tagline", config.tagline)
    config.contact_email = clean_text("contact_email", config.contact_email)
    config.facebook_url = clean_text("facebook_url", config.facebook_url)

    config.primary_color = clean_hex("primary_color", config.primary_color)
    config.secondary_color = clean_hex("secondary_color", config.secondary_color)
    config.accent_color = clean_hex("accent_color", config.accent_color)

    config.announcement_enabled = request.POST.get("announcement_enabled") == "on"
    config.announcement_title = clean_text("announcement_title")
    config.announcement_message = clean_text("announcement_message")
    tone = clean_text("announcement_tone", config.announcement_tone)
    config.announcement_tone = tone if tone in dict(SiteConfiguration.AnnouncementTone.choices) else SiteConfiguration.AnnouncementTone.INFO

    config.registration_enabled = request.POST.get("registration_enabled") == "on"
    config.maintenance_mode = request.POST.get("maintenance_mode") == "on"
    config.maintenance_message = clean_text("maintenance_message", config.maintenance_message)
    config.updated_by = request.user
    config.save()

    after = _site_configuration_snapshot(config)
    changed = [key for key in after if before.get(key) != after.get(key)]
    if changed:
        SiteConfigurationLog.objects.create(
            changed_by=request.user,
            summary=f"Updated site controls: {', '.join(changed[:6])}{'…' if len(changed) > 6 else ''}",
            before=before,
            after=after,
        )
        messages.success(request, "Site-wide controls updated successfully.")
    else:
        messages.info(request, "No site-wide control changes were detected.")

    return redirect("admin_dashboard")


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
            except Exception:
                logger.exception("Failed to update role for user_id=%r.", user_id)
                messages.error(
                    request,
                    "Could not update the role. The error has been logged.",
                )

        return redirect("admin_dashboard")

    return redirect("admin_dashboard")
