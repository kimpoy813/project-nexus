"""What NExUS is made of — one place to update the system's own profile.

The About page answers "what is this system and who built it", so the answers
live here rather than in a template: the developer's name, the office the
system was built for, the stack it runs on, and the contact address.

Everything in this module is checkable against the repository:

* the stack matches ``requirements.txt`` and ``frontend/package.json``
* the runtime matches ``render.yaml`` and ``build.sh``
* the institution name matches the MOA generator (``proposals/moa_docx.py``)
* the contact address is the site's own ``SiteConfiguration.contact_email``
  default

The developer credit is deliberately explicit: this is a person's work, and it
should be named on the page rather than left to a footer.
"""

SYSTEM_NAME = "NExUS"
SYSTEM_LONG_NAME = "Networked Extension Unified System"
SYSTEM_TAGLINE = "Extension work, from proposal to terminal report, in one system."

DEVELOPER = {
    "name": "Kim Dave Rafael",
    "role": "Developer",
}

INSTITUTION = "Ilocos Sur Polytechnic State College (ISPSC)"
OFFICE = "ISPSC-RDEI Extension Office"

#: What the system is built with, as (label, value) pairs. Kept factual: each
#: entry is a dependency the repository actually installs or serves.
STACK = (
    ("Framework", "Django 5 · Python 3.12"),
    ("Database", "PostgreSQL (SQLite for local work)"),
    ("Files", "Supabase Storage, local storage in development"),
    ("Interface", "Tailwind CSS · Alpine.js"),
    ("Serving", "Gunicorn · WhiteNoise"),
)


def profile():
    """The About page's "at a glance" card data."""
    from accounts.models import SiteConfiguration

    try:
        contact_email = SiteConfiguration.get_solo().contact_email
    except Exception:  # un-migrated database, or settings not ready
        contact_email = ""

    return {
        "system_name": SYSTEM_NAME,
        "system_long_name": SYSTEM_LONG_NAME,
        "tagline": SYSTEM_TAGLINE,
        "developer": DEVELOPER,
        "institution": INSTITUTION,
        "office": OFFICE,
        "stack": [{"label": label, "value": value} for label, value in STACK],
        "contact_email": contact_email,
    }
