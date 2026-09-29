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
        "workflow_phase_shares": _workflow_phase_shares(),
    }


def _workflow_phase_shares():
    """Phase weights as fractions, for the dashboard progress gauges.

    The gauges colour-band the arc by phase, so their boundaries have to come
    from the same admin-editable ``WorkflowPhase`` rows that drive
    ``Proposal.overall_progress`` - otherwise the colours would stop matching
    the percentage underneath them.
    """
    from details.models import WorkflowPhase

    try:
        return WorkflowPhase.phase_shares()
    except Exception:
        logger.exception("Failed to load workflow phase shares; using defaults.")
        defaults = WorkflowPhase.DEFAULT_WEIGHTS
        total = sum(defaults.values())
        return {key: value / total for key, value in defaults.items()}


# ---------------------------------------------------------------------------
# Page skeleton layout
# ---------------------------------------------------------------------------
# The screens in this system are not one layout repeated. The landing pages are
# a full-bleed hero over stacked content sections; the sign-in screens are a
# brand panel beside a card; the dashboards are a 240px rail beside a KPI grid;
# the admin CRUD screens are a page head over a table or a field grid; the
# proposal wizard is three rails (stepper | form | context panel); the MOA and
# implementation screens are a progress header over a 2/3 + 1/3 split.
#
# A single generic skeleton ("hero + four stat cards") therefore looked wrong on
# most of the system. Each page instead tells the overlay which layout shape to
# paint, resolved here from the route so no template has to opt in.

#: Layout names the overlay in ``templates/base.html`` knows how to paint.
SKELETON_VARIANTS = (
    "marketing",  # hero band + stacked content sections (home, reports, services)
    "auth",       # brand panel + form card (login, register, password reset)
    "dashboard",  # title bar + 240px nav rail + KPI/queue body
    "wizard",     # stepper rail | form column | context rail
    "tracker",    # progress header + 2/3 main card + 1/3 side cards
    "list",       # page head + card containing a table
    "form",       # page head + card containing a field grid
    "record",     # page head + stacked full-width detail cards
)

#: Shape used when a route is not listed below and matches no rule. ``record``
#: is the neutral screen: a heading over one or two full-width cards, which is
#: what most unlisted pages are.
SKELETON_DEFAULT = "record"

_SKELETON_BY_URL_NAME = {}
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # Public landing pages and CMS-driven content pages.
    ("details_page", "reports_page", "achievements_page", "services_home"),
    "marketing",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # Every screen built on `.nx-auth`: brand panel left, form card right.
    # Logout never renders a page of its own — it redirects to login — so the
    # skeleton painted *on the way out* must be the auth screen, not whatever
    # the user was looking at.
    (
        "login", "register", "debug_login", "verify_email", "change_password",
        "password_reset", "password_reset_done", "password_reset_confirm",
        "password_reset_complete", "logout", "logout_idle",
    ),
    "auth",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # The seven role dashboards plus the router that picks one.
    (
        "dashboard", "dashboard_redirect", "faculty_dashboard", "staff_dashboard",
        "evaluator_dashboard", "department_coordinator_dashboard",
        "campus_coordinator_dashboard", "director_dashboard", "admin_dashboard",
    ),
    "dashboard",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # `.nexus-wizard-layout`: stepper rail | form | context rail.
    ("proposal_create", "proposal_wizard", "admin_legacy_proposal_create"),
    "wizard",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # Progress header + main card + side cards.
    (
        "proposal_moa_tracker", "proposal_implementation_tracker",
        "proposal_moa_draft", "proposal_moa_step", "proposal_storage",
        "proposal_upload_signed_proposal", "staff_release_approval_documents",
        "moa_upload",
    ),
    "tracker",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # Headings over stacked detail cards, no rail and no table.
    (
        "profile_view", "admin_user_detail", "manage_roles",
        "proposal_review_comments", "proposal_comment_summary",
        "proposal_version_summary", "admin_content_dashboard",
    ),
    "record",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # Field-grid screens whose url names do not end in `_create` / `_edit`.
    ("admin_edit_user", "admin_create_account"),
    "form",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # The content change log is a list view (lives under /admin/pages/ like
    # the section editors, which are forms).
    ("page_content_logs",),
    "list",
))
_SKELETON_BY_URL_NAME.update(dict.fromkeys(
    # POST endpoints that bounce straight back to a role dashboard.
    ("admin_site_control",),
    "dashboard",
))

#: Name endings that reliably identify the two admin CRUD shapes. They are
#: checked after the explicit table so an exception above always wins.
_SKELETON_SUFFIXES = (
    ("_list", "list"),
    ("_manager", "list"),
    ("_create", "form"),
    ("_edit", "form"),
    ("_dashboard", "dashboard"),
)

#: Last-resort prefixes, for a route that is new and follows the usual shape of
#: its area of the system.
_SKELETON_PATH_PREFIXES = (
    ("/dashboard/", "dashboard"),
    ("/admin/", "list"),
)


def skeleton_variant(request):
    """Tell the page skeleton which layout the screen being rendered uses."""
    return {"nx_skeleton_variant": _resolve_skeleton_variant(request)}


def _resolve_skeleton_variant(request):
    """Map the current route to a skeleton layout, defaulting rather than raising.

    Runs on every render, including error pages, so it must never raise: a
    failure here would turn a recoverable problem into a blank 500.
    """
    try:
        match = getattr(request, "resolver_match", None)
        url_name = getattr(match, "url_name", None) or ""

        variant = _SKELETON_BY_URL_NAME.get(url_name)
        if variant:
            return variant

        for suffix, candidate in _SKELETON_SUFFIXES:
            if url_name.endswith(suffix):
                return candidate

        path = getattr(request, "path", "") or ""
        stripped = path.rstrip("/")
        if stripped.endswith(("/edit", "/new", "/create")):
            return "form"

        for prefix, candidate in _SKELETON_PATH_PREFIXES:
            if path.startswith(prefix):
                return candidate
    except Exception:
        logger.exception("Unexpected error resolving the page skeleton layout.")

    return SKELETON_DEFAULT


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
