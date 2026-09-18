"""Translate file-storage exceptions into short, admin-readable reasons.

Both the Template Library views and ``manage.py check_file_storage`` need to
tell an administrator *why* an upload failed.  "Check the Supabase bucket,
endpoint, and S3 access keys" is only useful once the provider's error code is
known, because ``SignatureDoesNotMatch`` (wrong keys or region),
``NoSuchBucket`` (wrong bucket or endpoint) and ``AccessDenied`` (revoked keys)
each need a different fix.
"""

from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError

#: Advice keyed by the lowercase text of the provider error. The first match
#: wins, so put the more specific fragments first.
_FAILURE_HINTS = (
    (
        "invalid region",
        "SUPABASE_S3_REGION_NAME does not match the region of the Supabase project. "
        "Copy the region from Project Settings -> Storage -> S3 and redeploy.",
    ),
    (
        "signaturedoesnotmatch",
        "The S3 access keys or the region do not match this Supabase project. Regenerate the "
        "S3 access keys, paste both values again, and confirm SUPABASE_S3_REGION_NAME.",
    ),
    (
        "invalidaccesskeyid",
        "SUPABASE_S3_ACCESS_KEY_ID is not an access key of this project. Create or rotate the "
        "pair in Project Settings -> Storage -> S3 Access Keys.",
    ),
    (
        "accessdenied",
        "Supabase rejected the credentials. Confirm the keys come from this project's S3 Access "
        "Keys page, that SUPABASE_STORAGE_BUCKET exists, and that the region matches.",
    ),
    (
        "nosuchbucket",
        "SUPABASE_STORAGE_BUCKET does not exist in the project the endpoint points at. Check the "
        "bucket name in Supabase Storage and confirm SUPABASE_S3_ENDPOINT_URL uses the same "
        "project reference as SUPABASE_STORAGE_PUBLIC_URL.",
    ),
    (
        "unsupported header",
        "The S3 client sent a header this Supabase project's S3 API does not implement. Make sure "
        "the deployment is running the current conf/settings.py, which disables S3 checksum and "
        "ACL headers.",
    ),
    (
        "checksum",
        "The S3 client sent a data-integrity header Supabase does not implement. The current "
        "settings disable those headers, so redeploy with the latest conf/settings.py.",
    ),
    (
        "invalid endpoint",
        "SUPABASE_S3_ENDPOINT_URL is malformed. It must look like "
        "https://<project-ref>.supabase.co/storage/v1/s3.",
    ),
    (
        "invalidendpoint",
        "SUPABASE_S3_ENDPOINT_URL is malformed. It must look like "
        "https://<project-ref>.supabase.co/storage/v1/s3.",
    ),
    (
        "no address associated",
        "The S3 endpoint host could not be resolved. Check SUPABASE_S3_ENDPOINT_URL for a typo "
        "in the project reference.",
    ),
    (
        "endpoint",
        "The S3 endpoint could not be reached. Confirm SUPABASE_S3_ENDPOINT_URL is correct and "
        "that outbound HTTPS from the host is allowed.",
    ),
    (
        "timed out",
        "The S3 endpoint did not respond in time. Retry; if it persists, check Supabase's status "
        "page.",
    ),
    (
        "temporarily unavailable",
        "Supabase Storage reported a temporary problem. Retry the upload in a few minutes.",
    ),
)

#: HEAD responses carry no error body, so botocore cannot report a code for
#: HeadBucket/HeadObject failures. The HTTP status still narrows it down.
_STATUS_HINTS = {
    400: "Supabase rejected the request as malformed. Check SUPABASE_S3_ENDPOINT_URL "
    "(it must end with /storage/v1/s3) and confirm the SDK is not sending unsupported "
    "headers; update to the current conf/settings.py and redeploy.",
    401: "The S3 credentials were not accepted. Create a fresh S3 access key pair in "
    "Project Settings -> Storage -> S3 Access Keys.",
    403: "Supabase rejected the signature. Confirm SUPABASE_S3_ACCESS_KEY_ID and "
    "SUPABASE_S3_SECRET_ACCESS_KEY are the S3 access key pair (not the anon/service_role API "
    "keys) and that SUPABASE_S3_REGION_NAME matches the project's region exactly.",
    404: "The bucket was not found for this project. Check the spelling of "
    "SUPABASE_STORAGE_BUCKET and that SUPABASE_S3_ENDPOINT_URL uses the same project reference "
    "as SUPABASE_STORAGE_PUBLIC_URL.",
    500: "Supabase Storage returned a server error. Retry in a few minutes and check "
    "https://status.supabase.com.",
    503: "Supabase Storage is temporarily unavailable. Retry in a few minutes.",
}

_DEFAULT_HINT = (
    "Re-run `python manage.py check_file_storage` to see which part of the Supabase setup fails."
)


def describe_storage_exception(exc):
    """Return a one-line description such as ``SignatureDoesNotMatch (HTTP 403)``."""
    if exc is None:
        return ""
    if isinstance(exc, ClientError):
        error = exc.response.get("Error") or {}
        code = error.get("Code") or "ClientError"
        status = (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
        detail = _shorten(error.get("Message") or "")
        label = f"{code} (HTTP {status})" if status else code
        return f"{label}: {detail}" if detail else label
    if isinstance(exc, BotoCoreError):
        return f"{exc.__class__.__name__}: {_shorten(str(exc))}".strip(": ")
    if isinstance(exc, ValueError):
        return f"ValueError: {_shorten(str(exc))}"
    if isinstance(exc, OSError):
        return f"{exc.__class__.__name__}: {_shorten(str(exc))}".strip(": ")
    return f"{exc.__class__.__name__}: {_shorten(str(exc))}".strip(": ")


def storage_failure_hint(exc):
    """Return actionable advice for the given storage exception."""
    if exc is None:
        return _DEFAULT_HINT

    haystack = describe_storage_exception(exc).lower()
    for fragment, hint in _FAILURE_HINTS:
        if fragment in haystack:
            return hint

    status = _http_status(exc)
    if status in _STATUS_HINTS:
        return _STATUS_HINTS[status]

    return _DEFAULT_HINT


def _http_status(exc):
    if isinstance(exc, ClientError):
        return (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    return None


def _shorten(text, limit=200):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
