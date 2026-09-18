"""
Django settings for conf project.

Production-ready configuration notes:
- Use DATABASE_URL for PostgreSQL in production.
- Use Supabase Storage's S3-compatible endpoint for uploaded media files.
- Keep secrets in environment variables, never in source code.
"""

from pathlib import Path
import os

from conf.storage_config import build_supabase_storage_config

try:
    import dj_database_url
except ImportError:  # Allows local tooling to import settings before dependencies are installed.
    dj_database_url = None

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# ==============================
# CORE / SECURITY
# ==============================

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-change-this-in-production",
)

# Default to False so an unset or misspelled DEBUG in production can never
# expose stack traces, settings, and local variables to visitors.
# Local development opts in explicitly via .env or the environment.
DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
# Django validates the complete Origin (scheme, host, and port) for unsafe
# requests.  Include the standard local development origins so the login form
# works when run with `python manage.py runserver` at localhost:8000. Deployments
# should set CSRF_TRUSTED_ORIGINS explicitly with their HTTPS public URLs.
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
)


# ==============================
# APPLICATIONS
# ==============================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_ckeditor_5",
    "details",
    "accounts",
    "axes",
    "proposals",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.SiteControlMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Must run after MessageMiddleware so failed uploads can return a safe
    # redirect with a user-facing message instead of an unhandled 500.
    "accounts.middleware.UploadStorageErrorMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.InactiveLogoutMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "conf.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.site_configuration",
            ],
        },
    },
]

WSGI_APPLICATION = "conf.wsgi.application"


# ==============================
# DATABASE
# ==============================
# Local default: SQLite.
# Production: set DATABASE_URL to your PostgreSQL connection string, e.g.
# postgresql://USER:PASSWORD@HOST:5432/DBNAME

if dj_database_url:
    DATABASES = {
        "default": dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ==============================
# PASSWORD VALIDATION
# ==============================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ==============================
# INTERNATIONALIZATION
# ==============================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True


# ==============================
# RICH TEXT EDITOR (CKEditor 5)
# ==============================
# Used by the admin Page Content editor (Home, Services, Reports, Achievements).

CKEDITOR_5_FILE_STORAGE = None  # fall back to DEFAULT_FILE_STORAGE / STORAGES
CKEDITOR_5_UPLOAD_FILE_TYPES = ["jpeg", "jpg", "png", "gif", "webp", "svg"]

_CKEDITOR_5_TOOLBAR = [
    "heading", "|",
    "bold", "italic", "underline", "link", "|",
    "bulletedList", "numberedList", "|",
    "outdent", "indent", "|",
    "blockQuote", "insertTable", "imageUpload", "|",
    "undo", "redo", "|",
    "sourceEditing",
]

CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": _CKEDITOR_5_TOOLBAR,
        "height": 320,
        "image": {
            "toolbar": [
                "imageTextAlternative",
                "imageStyle:alignLeft",
                "imageStyle:full",
                "imageStyle:alignRight",
            ],
        },
        "table": {
            "contentToolbar": ["tableColumn", "tableRow", "mergeTableCells"],
        },
        "link": {"addTargetToExternalLinks": True},
    },
}


# ==============================
# STATIC FILES
# ==============================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]


# ==============================
# MEDIA / FILE UPLOAD STORAGE
# ==============================
# Local default: filesystem under MEDIA_ROOT.
# Production option: Supabase Storage using its S3-compatible API.
# Required env vars when USE_SUPABASE_STORAGE=True:
# - SUPABASE_STORAGE_BUCKET                (plain bucket name, e.g. nexus-media)
# - SUPABASE_S3_ENDPOINT_URL               (https://<project-ref>.supabase.co/storage/v1/s3)
# - SUPABASE_S3_ACCESS_KEY_ID
# - SUPABASE_S3_SECRET_ACCESS_KEY
# Strongly recommended:
# - SUPABASE_S3_REGION_NAME                (copy it from the Supabase S3 settings page)
# - SUPABASE_STORAGE_PUBLIC_URL            (https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>)
#
# The values are validated by conf/storage_config.py.  When something is
# missing or malformed the remote backend is *not* selected and
# MEDIA_STORAGE_CONFIGURATION_ERROR explains what to fix, because sending
# uploads to a half-configured bucket is how files silently disappear.
# Run `python manage.py check_file_storage` to test a live configuration.

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

USE_SUPABASE_STORAGE = env_bool("USE_SUPABASE_STORAGE", False)

# Values copied from a dashboard can carry trailing spaces or newlines. Those
# break the SigV4 signature ("SignatureDoesNotMatch") while looking correct in
# the Render dashboard, so every value is stripped and checked here before the
# client is built.
SUPABASE_STORAGE = build_supabase_storage_config(os.environ)

# Kept for backwards compatibility with deployment notes written before the
# validation module existed.
SUPABASE_STORAGE_MISSING_ENV_VARS = SUPABASE_STORAGE.missing_env_vars

# Non-fatal advice (for example a missing SUPABASE_STORAGE_PUBLIC_URL). Shown by
# `manage.py check_file_storage` and kept out of the upload guard.
SUPABASE_STORAGE_CONFIGURATION_WARNINGS = SUPABASE_STORAGE.warnings

# Fatal problems. Upload views and the upload middleware refuse to write files
# while this is set so nothing lands on the ephemeral service filesystem.
MEDIA_STORAGE_CONFIGURATION_ERROR = ""
if USE_SUPABASE_STORAGE:
    MEDIA_STORAGE_CONFIGURATION_ERROR = " ".join(SUPABASE_STORAGE.errors)

if USE_SUPABASE_STORAGE and SUPABASE_STORAGE.is_usable:
    SUPABASE_STORAGE_BUCKET = SUPABASE_STORAGE.bucket
    SUPABASE_S3_ENDPOINT_URL = SUPABASE_STORAGE.endpoint_url
    SUPABASE_S3_REGION_NAME = SUPABASE_STORAGE.region_name
    SUPABASE_STORAGE_PUBLIC_URL = SUPABASE_STORAGE.public_url

    supabase_options = {
        "access_key": SUPABASE_STORAGE.access_key,
        "secret_key": SUPABASE_STORAGE.secret_key,
        "bucket_name": SUPABASE_STORAGE.bucket,
        "endpoint_url": SUPABASE_STORAGE.endpoint_url,
        "region_name": SUPABASE_STORAGE.region_name,
        "addressing_style": "path",
        "file_overwrite": False,
        "querystring_auth": False,
        # NOTE: Supabase Storage does not implement S3 ACLs (the
        # compatibility table marks x-amz-acl as unsupported), so no
        # default_acl is set. Objects are readable because the bucket itself is
        # public and MEDIA_URL uses /storage/v1/object/public/<bucket>.
        "object_parameters": {
            "CacheControl": "max-age=86400",
        },
    }

    # boto3 >= 1.36 attaches data-integrity headers (x-amz-sdk-checksum-algorithm
    # and x-amz-checksum-*) to every PutObject/CreateMultipartUpload. Supabase's
    # S3 layer does not implement those headers ("Unsupported header
    # 'x-amz-sdk-checksum-algorithm' received" is the same failure other
    # S3-compatible providers report), so uploads are sent the way every other
    # Supabase client sends them: with checksums only where the API requires
    # them.
    try:
        from botocore.config import Config as _BotoConfig

        supabase_options["client_config"] = _BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            connect_timeout=10,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        )
    except ImportError:  # pragma: no cover - boto3 is a hard requirement in production.
        pass

    if SUPABASE_STORAGE.public_url:
        supabase_options["custom_domain"] = SUPABASE_STORAGE.custom_domain
        # django-storages defaults url_protocol to https: and ignores the
        # scheme of MEDIA_URL when a custom domain is set, which would break
        # self-hosted or local Supabase served over plain http.
        supabase_options["url_protocol"] = SUPABASE_STORAGE.public_url_scheme
        MEDIA_URL = f"{SUPABASE_STORAGE.public_url}/"

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": supabase_options,
    }
else:
    # This is suitable for local development. The Template Library blocks new
    # file writes when MEDIA_STORAGE_CONFIGURATION_ERROR is set so official
    # templates are never silently placed on an ephemeral service filesystem.
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }


# ==============================
# AUTH / SESSIONS
# ==============================

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard_redirect"
LOGOUT_REDIRECT_URL = "details_page"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AXES_FAILURE_LIMIT = int(os.environ.get("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = int(os.environ.get("AXES_COOLOFF_TIME", "1"))  # hours

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", "600"))
SESSION_SAVE_EVERY_REQUEST = True


# ==============================
# EMAIL
# ==============================

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"NExUS System <{EMAIL_HOST_USER or 'no-reply@example.com'}>",
)


# ==============================
# PRODUCTION SECURITY SWITCHES
# ==============================

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_HTTPONLY = env_bool("CSRF_COOKIE_HTTPONLY", False)
CSRF_USE_SESSIONS = env_bool("CSRF_USE_SESSIONS", False)
CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Lax")


# ==============================
# LOGGING
# ==============================
# Without this, Django's default configuration discards application logs
# entirely outside of DEBUG, so a swallowed exception left no trace at all.
# Everything goes to stdout, which is what Render/Heroku-style hosts capture.

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        # Application loggers. Use logging.getLogger(__name__) in each module.
        "accounts": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "proposals": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "details": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # Unhandled view exceptions.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
