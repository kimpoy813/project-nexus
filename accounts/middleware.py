# accounts/middleware.py

from datetime import timedelta
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout


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
                except Exception:
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
        try:
            from django.shortcuts import render
            from .models import SiteConfiguration

            config = SiteConfiguration.get_solo()
        except Exception:
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
