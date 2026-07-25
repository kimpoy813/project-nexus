def site_configuration(request):
    """Expose admin-controlled site settings to every template."""
    try:
        from .models import SiteConfiguration

        config = SiteConfiguration.get_solo()
    except Exception:
        config = None

    return {
        "site_control": config,
    }
