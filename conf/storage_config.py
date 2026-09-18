"""Validation and normalization for the Supabase S3 file-storage settings.

Supabase Storage exposes an S3-compatible API, but only a documented subset of
it.  Most "the template could not be uploaded to file storage" reports trace
back to one of a handful of setting problems:

* a copied endpoint that still contains ``PROJECT_REF`` or that points at the
  *public object* URL instead of the S3 API URL,
* the project reference and/or bucket name in ``SUPABASE_STORAGE_BUCKET`` and
  ``SUPABASE_STORAGE_PUBLIC_URL`` disagreeing, so uploads land in one bucket
  while every generated link points at another,
* Supabase *API* keys (``anon``/``service_role`` JWTs) pasted where S3 access
  keys belong,
* trailing spaces or newlines picked up from a dashboard copy/paste,
* a region that does not match the project, which makes every signature
  mismatch.

The functions below are deliberately free of Django imports so they can be
unit-tested and reused by the ``check_file_storage`` management command.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

#: Path every Supabase project's S3-compatible API is served from.
S3_ENDPOINT_PATH = "/storage/v1/s3"

#: Path prefix of the public object URLs Supabase returns for public buckets.
PUBLIC_OBJECT_PATH = "/storage/v1/object/public/"

#: Hosts that belong to Supabase-hosted projects.
SUPABASE_HOST_SUFFIXES = (".supabase.co", ".supabase.in")

#: Fragments that only ever appear in the documentation placeholders.
PLACEHOLDER_FRAGMENTS = (
    "project_ref",
    "your-project",
    "your-supabase",
    "your-access-key",
    "your-secret-key",
    "your-supabase-s3",
    "changeme",
    "example.com",
)

#: The region Supabase's own examples use when a project does not report one.
DEFAULT_S3_REGION = "us-east-1"

#: Environment variables that must be set for the remote backend.
REQUIRED_ENV_VARS = (
    "SUPABASE_STORAGE_BUCKET",
    "SUPABASE_S3_ENDPOINT_URL",
    "SUPABASE_S3_ACCESS_KEY_ID",
    "SUPABASE_S3_SECRET_ACCESS_KEY",
)

#: Values that mean "the region from the dashboard was not copied".
PLACEHOLDER_REGIONS = ("project_region", "your-region", "region")


@dataclass(frozen=True)
class SupabaseStorageConfig:
    """Normalized Supabase Storage settings plus validation results."""

    bucket: str = ""
    endpoint_url: str = ""
    region_name: str = DEFAULT_S3_REGION
    access_key: str = ""
    secret_key: str = ""
    public_url: str = ""
    missing_env_vars: tuple = ()
    errors: tuple = ()
    warnings: tuple = ()

    @property
    def is_usable(self):
        """True when the remote backend can be selected safely."""
        return not self.errors

    @property
    def project_ref(self):
        return _project_ref(urlparse(self.endpoint_url).hostname)

    @property
    def custom_domain(self):
        """Host + path form django-storages expects for ``custom_domain``."""
        if not self.public_url:
            return ""
        parsed = urlparse(self.public_url)
        return f"{parsed.netloc}{parsed.path}".rstrip("/")

    @property
    def public_url_scheme(self):
        """``https:``/``http:`` for django-storages' ``url_protocol`` option."""
        if not self.public_url:
            return "https:"
        return f"{urlparse(self.public_url).scheme}:"


def build_supabase_storage_config(env):
    """Validate the environment and return normalized Supabase settings.

    ``env`` is any mapping, normally ``os.environ``.  Missing required values
    are reported the same way they always have been so existing deployments
    keep the same actionable message.
    """
    bucket = _clean(env.get("SUPABASE_STORAGE_BUCKET"))
    endpoint = _clean(env.get("SUPABASE_S3_ENDPOINT_URL"))
    access_key = _clean(env.get("SUPABASE_S3_ACCESS_KEY_ID"))
    secret_key = _clean(env.get("SUPABASE_S3_SECRET_ACCESS_KEY"))
    region = _clean(env.get("SUPABASE_S3_REGION_NAME")).lower()
    public_url = _clean(env.get("SUPABASE_STORAGE_PUBLIC_URL")).rstrip("/")

    errors = []
    warnings = []

    values = {
        "SUPABASE_STORAGE_BUCKET": bucket,
        "SUPABASE_S3_ENDPOINT_URL": endpoint,
        "SUPABASE_S3_ACCESS_KEY_ID": access_key,
        "SUPABASE_S3_SECRET_ACCESS_KEY": secret_key,
    }
    missing = [name for name in REQUIRED_ENV_VARS if not values[name]]
    if missing:
        errors.append(
            "Supabase file storage is enabled but is missing: "
            f"{', '.join(missing)}. "
            "Set these deployment environment variables and redeploy before uploading files."
        )
        # Without all four values there is nothing useful left to validate.
        return SupabaseStorageConfig(
            bucket=bucket,
            missing_env_vars=tuple(missing),
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    endpoint, endpoint_errors = _validate_endpoint(endpoint)
    errors.extend(endpoint_errors)

    bucket_error = _validate_bucket(bucket)
    if bucket_error:
        errors.append(bucket_error)

    errors.extend(_validate_credentials(access_key, secret_key, bucket))

    if not region:
        region = DEFAULT_S3_REGION
        warnings.append(
            "SUPABASE_S3_REGION_NAME is not set, so the S3 client signs with "
            f"{DEFAULT_S3_REGION}. Open Project Settings -> Storage -> S3 in Supabase, copy the "
            "region shown there, and set SUPABASE_S3_REGION_NAME to it. File uploads fail with "
            "'Invalid Region' or 'SignatureDoesNotMatch' when the region and the project disagree."
        )
    elif region in PLACEHOLDER_REGIONS:
        errors.append(
            f"SUPABASE_S3_REGION_NAME is still the placeholder value '{region}'. Copy the region "
            "from Project Settings -> Storage -> S3 in the Supabase dashboard."
        )

    public_url, public_errors, public_warnings = _validate_public_url(
        public_url,
        bucket=bucket,
        # Only compare projects when the endpoint itself parsed cleanly, so a
        # placeholder endpoint does not produce two overlapping complaints.
        endpoint_url=endpoint if not endpoint_errors else "",
    )
    errors.extend(public_errors)
    warnings.extend(public_warnings)

    return SupabaseStorageConfig(
        bucket=bucket,
        endpoint_url=endpoint,
        region_name=region,
        access_key=access_key,
        secret_key=secret_key,
        public_url=public_url,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _clean(value):
    return (value or "").strip()


def _is_placeholder(value):
    lowered = value.lower()
    return any(fragment in lowered for fragment in PLACEHOLDER_FRAGMENTS)


def _validate_endpoint(endpoint):
    """Return ``(normalized_endpoint, errors)``."""
    if _is_placeholder(endpoint):
        return endpoint, [
            "SUPABASE_S3_ENDPOINT_URL still contains the documentation placeholder "
            f"'{endpoint}'. Replace PROJECT_REF with your project reference, e.g. "
            "https://abcdefghijklm.supabase.co/storage/v1/s3."
        ]

    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return endpoint, [
            "SUPABASE_S3_ENDPOINT_URL is not a valid URL "
            f"('{endpoint}'). It must start with https:// and end at /storage/v1/s3, e.g. "
            "https://abcdefghijklm.supabase.co/storage/v1/s3."
        ]

    path = parsed.path.rstrip("/")
    if path.endswith(S3_ENDPOINT_PATH):
        normalized = f"{parsed.scheme}://{parsed.netloc}{S3_ENDPOINT_PATH}"
        return normalized, []

    if S3_ENDPOINT_PATH + "/" in path:
        extra = path.split(S3_ENDPOINT_PATH + "/", 1)[1]
        return endpoint, [
            "SUPABASE_S3_ENDPOINT_URL must end at /storage/v1/s3, but it also contains "
            f"'{extra}'. Do not append the bucket name to the endpoint; put the bucket in "
            "SUPABASE_STORAGE_BUCKET instead."
        ]

    if "/storage/v1/object" in path:
        return endpoint, [
            "SUPABASE_S3_ENDPOINT_URL points at the public object URL, not the S3 API. Use "
            "https://<project-ref>.supabase.co/storage/v1/s3. The "
            "/storage/v1/object/public/<bucket> form belongs in SUPABASE_STORAGE_PUBLIC_URL."
        ]

    return endpoint, [
        "SUPABASE_S3_ENDPOINT_URL must end with /storage/v1/s3 (got "
        f"'{path or '/'}'). Copy the S3 endpoint from Project Settings -> Storage -> S3 in "
        "Supabase, e.g. https://abcdefghijklm.supabase.co/storage/v1/s3."
    ]


def _validate_bucket(bucket):
    if any(char.isspace() for char in bucket) or "://" in bucket or "/" in bucket:
        return (
            f"SUPABASE_STORAGE_BUCKET ('{bucket}') is not a bucket name. Use the plain bucket "
            "name only, e.g. nexus-media."
        )
    if _is_placeholder(bucket):
        return (
            f"SUPABASE_STORAGE_BUCKET ('{bucket}') still contains a placeholder. Create the "
            "bucket in Supabase (Storage -> New bucket) and use its exact name."
        )
    return ""


def _validate_credentials(access_key, secret_key, bucket):
    errors = []

    if _looks_like_jwt(access_key) or _looks_like_jwt(secret_key):
        errors.append(
            "SUPABASE_S3_ACCESS_KEY_ID/SUPABASE_S3_SECRET_ACCESS_KEY contain a Supabase API key "
            "(the anon or service_role JWT). Those are not valid for the S3 protocol; create an "
            "S3 access key pair in Project Settings -> Storage -> S3 Access Keys."
        )
    elif access_key == secret_key:
        errors.append(
            "SUPABASE_S3_ACCESS_KEY_ID and SUPABASE_S3_SECRET_ACCESS_KEY are identical. Paste "
            "the Access key ID and the Secret access key from the same S3 access key pair."
        )
    elif bucket and access_key == bucket:
        errors.append(
            "SUPABASE_S3_ACCESS_KEY_ID is set to the bucket name. Supabase only accepts the "
            "project reference there when authenticating with a session token; with static "
            "credentials use the S3 access key created in Project Settings -> Storage."
        )

    return errors


def _validate_public_url(public_url, *, bucket, endpoint_url):
    """Return ``(normalized_public_url, errors, warnings)``."""
    if not public_url:
        return "", [], [
            "SUPABASE_STORAGE_PUBLIC_URL is not set, so MEDIA_URL stays /media/ and uploaded "
            "files render as broken links in production. Set it to "
            "https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>."
        ]

    if _is_placeholder(public_url):
        return public_url, [
            "SUPABASE_STORAGE_PUBLIC_URL still contains the documentation placeholder "
            f"'{public_url}'. Replace PROJECT_REF with your project reference and keep the "
            "bucket name identical to SUPABASE_STORAGE_BUCKET."
        ], []

    parsed = urlparse(public_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return public_url, [
            "SUPABASE_STORAGE_PUBLIC_URL is not a valid URL "
            f"('{public_url}'). Use the full https:// URL shown for public objects, e.g. "
            "https://abcdefghijklm.supabase.co/storage/v1/object/public/nexus-media."
        ], []

    errors = []
    warnings = []

    path = parsed.path.rstrip("/")
    if PUBLIC_OBJECT_PATH in path + "/":
        url_bucket = path.split(PUBLIC_OBJECT_PATH, 1)[1].split("/")[0]
        if not url_bucket:
            errors.append(
                "SUPABASE_STORAGE_PUBLIC_URL does not include a bucket name. Use "
                "https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>."
            )
        elif url_bucket != bucket:
            errors.append(
                "SUPABASE_STORAGE_PUBLIC_URL points at bucket "
                f"'{url_bucket}' but SUPABASE_STORAGE_BUCKET is '{bucket}'. Uploads would be "
                "saved to one bucket while every download link points at another; make the two "
                "values match."
            )

        url_ref = _project_ref(parsed.hostname)
        endpoint_ref = _project_ref(urlparse(endpoint_url).hostname)
        if url_ref and endpoint_ref and url_ref != endpoint_ref:
            errors.append(
                "SUPABASE_STORAGE_PUBLIC_URL and SUPABASE_S3_ENDPOINT_URL point at different "
                f"Supabase projects ('{url_ref}' vs '{endpoint_ref}'). Use the same project for "
                "both values."
            )
    else:
        warnings.append(
            "SUPABASE_STORAGE_PUBLIC_URL does not look like a Supabase public object URL "
            f"('{public_url}'). Expected "
            "https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>; file links "
            "will be wrong unless you are deliberately serving media from a custom domain."
        )

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/"), errors, warnings


def _project_ref(hostname):
    """Return the project reference of a Supabase host, or '' for other hosts."""
    if not hostname:
        return ""
    host = hostname.lower()
    if host.endswith(SUPABASE_HOST_SUFFIXES):
        return host.split(".")[0]
    return ""


def _looks_like_jwt(value):
    return value.startswith("eyJ") and value.count(".") == 2
