"""
Django settings for conf project.

Production-ready configuration notes:
- Use DATABASE_URL for PostgreSQL in production.
- Use Supabase Storage's S3-compatible endpoint for uploaded media files.
- Keep secrets in environment variables, never in source code.
"""

from pathlib import Path
import os

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
# - SUPABASE_STORAGE_BUCKET
# - SUPABASE_S3_ENDPOINT_URL, e.g. https://PROJECT_REF.supabase.co/storage/v1/s3
# - SUPABASE_S3_ACCESS_KEY_ID
# - SUPABASE_S3_SECRET_ACCESS_KEY
# Optional:
# - SUPABASE_S3_REGION_NAME
# - SUPABASE_STORAGE_PUBLIC_URL, e.g.
#   https://PROJECT_REF.supabase.co/storage/v1/object/public/BUCKET

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if env_bool("USE_SUPABASE_STORAGE", False):
    SUPABASE_STORAGE_PUBLIC_URL = os.environ.get("SUPABASE_STORAGE_PUBLIC_URL", "").rstrip("/")

    supabase_options = {
        "access_key": os.environ.get("SUPABASE_S3_ACCESS_KEY_ID", ""),
        "secret_key": os.environ.get("SUPABASE_S3_SECRET_ACCESS_KEY", ""),
        "bucket_name": os.environ.get("SUPABASE_STORAGE_BUCKET", ""),
        "endpoint_url": os.environ.get("SUPABASE_S3_ENDPOINT_URL", ""),
        "region_name": os.environ.get("SUPABASE_S3_REGION_NAME", "us-east-1"),
        "addressing_style": "path",
        "file_overwrite": False,
        "querystring_auth": False,
        "default_acl": "public-read",
        "object_parameters": {
            "CacheControl": "max-age=86400",
        },
    }

    if SUPABASE_STORAGE_PUBLIC_URL:
        supabase_options["custom_domain"] = SUPABASE_STORAGE_PUBLIC_URL.replace("https://", "").replace("http://", "")
        MEDIA_URL = f"{SUPABASE_STORAGE_PUBLIC_URL}/"

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": supabase_options,
    }
else:
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
