"""
Settings used when running the test suite.

Run with:
    python manage.py test --settings=conf.settings_test

Production settings are imported unchanged; only the pieces that make tests
slow, brittle, or dependent on external services are overridden.
"""

from .settings import *  # noqa: F401,F403


# ``CompressedManifestStaticFilesStorage`` requires ``collectstatic`` to have
# been run and raises on any missing entry, which would make every view test
# fail for reasons unrelated to the code under test.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Keep uploads out of the real media directory.
MEDIA_ROOT = BASE_DIR / "test-media"  # noqa: F405

# Fast, deterministic password hashing. The default PBKDF2 hasher dominates
# runtime once a suite creates more than a handful of users.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# django-axes locks accounts after repeated failures, which interferes with
# tests that deliberately submit bad credentials.
AXES_ENABLED = False

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Tests assert on responses, not log output.
LOGGING_CONFIG = None

DEBUG = False
