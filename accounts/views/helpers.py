"""
Small shared helpers: login throttling, profile lookup, role normalisation.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from ..models import Profile

User = get_user_model()


FAILED_LOGIN_LIMIT = 5


FAILED_LOGIN_WINDOW = 60 * 60


BLOCK_TIMEOUT = 60 * 60


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
    if role == Profile.ROLE_EVALUATOR:
        return "evaluator_dashboard"
    return "faculty_dashboard"


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _user_role(user):
    profile = getattr(user, "profile", None)
    return (getattr(profile, "role", "") or "").upper()


def _safe_next_url(request, default):
    """Return a ``?next=`` target that is safe to redirect back to.

    The unified page editors link out to the record managers (personnel,
    activities, processes, targets, thrusts) with ``?next=`` pointing back at
    the editor, so saving returns the admin to the page they were editing
    instead of stranding them on a standalone list. Only local admin paths are
    honoured; anything else falls back to ``default``.
    """
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate.startswith("/") and not candidate.startswith("//") and "\n" not in candidate and "\r" not in candidate:
        return candidate
    return default
