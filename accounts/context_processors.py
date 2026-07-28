import logging

from django.db import DatabaseError

logger = logging.getLogger(__name__)


def site_configuration(request):
    """Expose admin-controlled site settings and role capabilities to every template.

    This runs on every render, including error pages, so it must never raise —
    a failure here would turn a recoverable problem into a blank 500 for the
    whole site. The broad handlers below are therefore deliberate, but each one
    now logs with a traceback instead of discarding the error, so a database
    problem is distinguishable from "this user genuinely has no permissions".
    """
    from .models import SiteConfiguration

    try:
        config = SiteConfiguration.get_solo()
    except DatabaseError:
        # Expected before the first migration runs, so this is not alarming.
        logger.warning("SiteConfiguration unavailable; falling back to defaults.", exc_info=True)
        config = None
    except Exception:
        logger.exception("Unexpected error loading SiteConfiguration.")
        config = None

    capabilities = _resolve_capabilities(request)

    # Resolved through accounts.permissions so templates and views can never
    # disagree about who may submit or view accomplishment reports.
    can_submit_accomplishment = False
    can_view_accomplishment = False
    try:
        from . import permissions

        can_submit_accomplishment = permissions.can_submit_accomplishment_reports(request.user)
        can_view_accomplishment = permissions.can_view_accomplishment_reports(request.user)
    except AttributeError:
        # No request.user (e.g. a request that bypassed AuthenticationMiddleware).
        logger.debug("No user on request while resolving accomplishment permissions.")
    except Exception:
        logger.exception("Failed to resolve accomplishment report permissions.")

    return {
        "site_control": config,
        "role_capabilities": capabilities,
        "can_submit_accomplishment": can_submit_accomplishment,
        "can_view_accomplishment": can_view_accomplishment,
    }


def _resolve_capabilities(request):
    """Capability set for the current user, or an empty set on failure."""
    from details.models import RoleCapability

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return set()

    try:
        role = (getattr(getattr(user, "profile", None), "role", "") or "").upper()

        if role == "ADMIN" or getattr(user, "is_superuser", False):
            return {"ALL"}

        queryset = RoleCapability.objects.filter(role=role)
        capabilities = set(
            queryset.filter(enabled=True).values_list("capability", flat=True)
        )

        # Backward-compatible defaults before the Admin opens/saves the matrix.
        if not queryset.exists() and role in {
            "DEPARTMENT_COORDINATOR",
            "CAMPUS_COORDINATOR",
        }:
            capabilities.add("SUBMIT_QUARTERLY_ACCOMPLISHMENT")

        return capabilities
    except DatabaseError:
        logger.warning("Could not read RoleCapability rows.", exc_info=True)
        return set()
    except Exception:
        logger.exception("Unexpected error resolving role capabilities.")
        return set()
