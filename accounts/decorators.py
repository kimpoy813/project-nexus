from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import Profile


FACULTY_LIKE_ROLES = [
    "FACULTY",
    "DEPARTMENT_COORDINATOR",
    "CAMPUS_COORDINATOR",
    "DIRECTOR",
]


def get_user_profile(request):
    if not request.user.is_authenticated:
        return None
    return Profile.objects.filter(user=request.user).first()


def get_normalized_role(profile):
    if not profile:
        return None

    role = profile.role or "FACULTY"

    if role == "COORDINATOR":
        role = "CAMPUS_COORDINATOR"

    return role


def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please login to access this page.")
                return redirect("login")

            profile = get_user_profile(request)
            if not profile:
                messages.error(request, "User profile not found.")
                return redirect("login")

            user_role = get_normalized_role(profile)

            if user_role == "ADMIN" or user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard_redirect")

        return _wrapped_view

    return decorator


def faculty_like_required(view_func):
    return role_required(FACULTY_LIKE_ROLES)(view_func)


def faculty_required(view_func):
    return role_required(["FACULTY"])(view_func)


def campus_coordinator_required(view_func):
    return role_required(["CAMPUS_COORDINATOR"])(view_func)


def department_coordinator_required(view_func):
    return role_required(["DEPARTMENT_COORDINATOR"])(view_func)


def staff_required(view_func):
    return role_required(["STAFF"])(view_func)


def director_required(view_func):
    return role_required(["DIRECTOR"])(view_func)


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please login to access this page.")
            return redirect("login")

        profile = get_user_profile(request)
        if not profile:
            messages.error(request, "User profile not found.")
            return redirect("login")

        user_role = get_normalized_role(profile)

        if user_role != "ADMIN":
            messages.error(request, "Admin access required.")
            return redirect("dashboard_redirect")

        if hasattr(profile, "email_verified") and not profile.email_verified:
            profile.email_verified = True
            profile.save(update_fields=["email_verified"])

        return view_func(request, *args, **kwargs)

    return _wrapped_view