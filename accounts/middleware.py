# accounts/middleware.py

import logging
from datetime import timedelta

from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import SuspiciousFileOperation
from django.db import DatabaseError
from django.shortcuts import redirect
from django.utils import timezone

from .storage_diagnostics import describe_storage_exception

logger = logging.getLogger(__name__)


class UploadStorageErrorMiddleware:
    """Turn file-storage failures from every upload flow into safe feedback.

    A number of workflows save FileField/ImageField values directly rather
    than through the Template Library form. Without this request-boundary
    guard, a temporary S3 outage or an incomplete Supabase setup bubbled out
    of those views as a generic 500 response.
    """

    WRITE_METHODS = {"POST", "PUT", "PATCH"}
    STORAGE_ERRORS = (BotoCoreError, ClientError, OSError, SuspiciousFileOperation)

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_file_upload(self, request):
        return request.method in self.WRITE_METHODS and bool(request.FILES)

    def _return_to_form(self, request, message, *, exc_info=False):
        logger.error(message, exc_info=exc_info)
        messages.error(request, message)
        # Returning to the same URL keeps each workflow's authorization and
        # form-rendering behavior in its own view; no unsafe Referer is used.
        return redirect(request.get_full_path())

    def __call__(self, request):
        # The configured fallback filesystem is intentionally not used when a
        # production Supabase setup was requested but is incomplete. It would
        # appear to work until a service restart silently removed the upload.
        configuration_error = getattr(settings, "MEDIA_STORAGE_CONFIGURATION_ERROR", "")
        if self._is_file_upload(request) and configuration_error:
            return self._return_to_form(
                request,
                "Your file was not uploaded because secure file storage is not configured. "
                "Please contact an administrator to complete the Supabase storage setup.",
            )

        try:
            response = self.get_response(request)
        except self.STORAGE_ERRORS as exc:
            # This branch is useful for a custom middleware/backend which
            # raises directly. Django's normal request handler converts view
            # exceptions into a 500 response first; that path is handled just
            # below as well.
            if request.method not in self.WRITE_METHODS:
                raise
            # Include the provider's own error code so the administrator knows
            # whether to look at the bucket, the endpoint, or the keys.
            reason = describe_storage_exception(exc)
            return self._return_to_form(
                request,
                f"Your file could not be saved right now ({reason}). Please try again; if the "
                "problem continues, ask an administrator to run `python manage.py "
                "check_file_storage` on the server.",
                exc_info=True,
            )
        except ValueError as exc:
            # boto3 reports a malformed configured endpoint as ValueError.
            # Do not swallow unrelated view bugs unless this is an S3 write.
            if request.method not in self.WRITE_METHODS or not getattr(settings, "USE_SUPABASE_STORAGE", False):
                raise
            return self._return_to_form(
                request,
                "Your file could not be saved because secure file storage is misconfigured "
                f"({describe_storage_exception(exc)}). Please ask an administrator to check the "
                "Supabase endpoint and access keys.",
                exc_info=True,
            )

        # Django wraps the view callback in its own exception converter, so a
        # FileField storage exception normally arrives here as a response with
        # status 500 rather than being re-raised.  Handle it at this boundary
        # for every multipart upload route, including forms outside accounts.
        if self._is_file_upload(request) and response.status_code >= 500:
            return self._return_to_form(
                request,
                "Your file could not be saved right now. Please try again; if the problem continues, "
                "ask an administrator to check secure file storage.",
            )

        return response


class InactiveLogoutMiddleware:
    """
    Auto-logout authenticated users after N minutes of inactivity.
    Inactivity = no requests made within the timeout window.
    """

    TIMEOUT_SECONDS = 600  # 10 minutes

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only track authenticated users
        if request.user.is_authenticated:
            now = timezone.now()

            last_activity_str = request.session.get("last_activity")
            if last_activity_str:
                try:
                    last_activity = timezone.datetime.fromisoformat(last_activity_str)
                    if timezone.is_naive(last_activity):
                        last_activity = timezone.make_aware(last_activity, timezone.get_current_timezone())
                except (ValueError, TypeError):
                    # Corrupt or legacy session value; treat as no recorded activity.
                    logger.debug("Unparseable last_activity in session: %r", last_activity_str)
                    last_activity = None
            else:
                last_activity = None

            # If idle too long -> logout
            if last_activity and (now - last_activity) > timedelta(seconds=self.TIMEOUT_SECONDS):
                logout(request)
                request.session.flush()
                messages.warning(request, "You were logged out due to 10 minutes of inactivity.")
                return redirect("login")

            # Update activity timestamp on every request
            request.session["last_activity"] = now.isoformat()

        return self.get_response(request)


class SiteControlMiddleware:
    """Apply admin-controlled site-wide behavior such as maintenance mode."""

    ALLOWED_PATH_PREFIXES = (
        "/login/",
        "/logout/",
        "/logout-idle/",
        "/password/",
        "/static/",
        "/media/",
        "/admin/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.shortcuts import render

        from .models import SiteConfiguration

        try:
            config = SiteConfiguration.get_solo()
        except DatabaseError:
            # Fail open: if the settings row cannot be read we let the request
            # through rather than locking everyone out. Logged because a
            # silent failure here would also silently disable maintenance mode.
            logger.warning(
                "Could not load SiteConfiguration; skipping maintenance check.",
                exc_info=True,
            )
            return self.get_response(request)
        except Exception:
            logger.exception("Unexpected error loading SiteConfiguration in middleware.")
            return self.get_response(request)

        if not getattr(config, "maintenance_mode", False):
            return self.get_response(request)

        path = request.path or "/"
        is_allowed_path = any(path.startswith(prefix) for prefix in self.ALLOWED_PATH_PREFIXES)
        profile = getattr(getattr(request, "user", None), "profile", None)
        is_admin = bool(
            getattr(getattr(request, "user", None), "is_superuser", False)
            or getattr(profile, "role", "") == "ADMIN"
        )

        # Admins keep full access so they can turn maintenance mode off.
        if is_admin or is_allowed_path:
            return self.get_response(request)

        return render(request, "maintenance.html", {"site_control": config}, status=503)
