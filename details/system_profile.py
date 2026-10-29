"""What NExUS is made of — metadata for the ``SYSTEM_PROFILE`` content block."""

SYSTEM_NAME = "NExUS"
SYSTEM_LONG_NAME = "Networked Extension Unified System"
SYSTEM_TAGLINE = "Extension work, from proposal to terminal report, in one system."

DEVELOPER = {
    "name": "Kim Dave Rafael",
    "role": "Developer",
}

INSTITUTION = "Ilocos Sur Polytechnic State College (ISPSC)"
OFFICE = "ISPSC-RDEI Extension Office"

STACK = (
    ("Framework", "Django 5 · Python 3.12"),
    ("Database", "PostgreSQL (SQLite for local work)"),
    ("Files", "Supabase Storage, local storage in development"),
    ("Interface", "Tailwind CSS · Alpine.js"),
    ("Documents", "python-docx · openpyxl"),
    ("Serving", "Gunicorn · WhiteNoise"),
)


def profile():
    """Return the system profile dictionary consumed by the CMS block."""
    from accounts.models import SiteConfiguration

    config = SiteConfiguration.get_solo()
    return {
        "name": SYSTEM_NAME,
        "long_name": SYSTEM_LONG_NAME,
        "tagline": SYSTEM_TAGLINE,
        "developer": DEVELOPER,
        "institution": INSTITUTION,
        "office": OFFICE,
        "stack": [{"label": label, "value": value} for label, value in STACK],
        "contact_email": (config.contact_email or "").strip(),
        "facebook_url": (config.facebook_url or "").strip(),
    }
