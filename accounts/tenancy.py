"""Helpers for keeping NExUS data scoped to an institution/tenant."""

from .models import Institution


def get_user_institution(user):
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        profile = user.profile
    except Exception:
        return None
    return getattr(profile, "institution", None)


def get_request_institution(request):
    """
    Resolve the institution for a request.

    Logged-in users are scoped to their profile institution. Anonymous/public
    pages currently fall back to the legacy ISPSC tenant so old URLs continue to
    render until host/subdomain tenant routing is introduced.
    """
    institution = get_user_institution(getattr(request, "user", None))
    if institution is not None:
        return institution
    return Institution.get_default()


def scoped_queryset(qs, institution):
    """Filter a queryset to the institution while preserving legacy null rows."""
    if institution is None:
        return qs.filter(institution__isnull=True)
    return qs.filter(institution=institution)


def assign_institution(obj, institution):
    if hasattr(obj, "institution") and institution is not None:
        obj.institution = institution
    return obj
