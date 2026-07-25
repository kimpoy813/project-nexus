def site_configuration(request):
    """Expose admin-controlled site settings and role capabilities to every template."""
    try:
        from .models import SiteConfiguration

        config = SiteConfiguration.get_solo()
    except Exception:
        config = None

    capabilities = set()
    try:
        if request.user.is_authenticated:
            role = (getattr(getattr(request.user, "profile", None), "role", "") or "").upper()
            if role == "ADMIN" or getattr(request.user, "is_superuser", False):
                capabilities = {"ALL"}
            else:
                from details.models import RoleCapability

                qs = RoleCapability.objects.filter(role=role)
                capabilities = set(qs.filter(enabled=True).values_list("capability", flat=True))

                # Backward-compatible defaults before the Admin opens/saves the matrix.
                if not qs.exists() and role in {"DEPARTMENT_COORDINATOR", "CAMPUS_COORDINATOR"}:
                    capabilities.add("SUBMIT_QUARTERLY_ACCOMPLISHMENT")
    except Exception:
        capabilities = set()

    return {
        "site_control": config,
        "role_capabilities": capabilities,
        "can_submit_accomplishment": "ALL" in capabilities or "SUBMIT_QUARTERLY_ACCOMPLISHMENT" in capabilities,
    }
