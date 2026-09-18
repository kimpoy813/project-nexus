"""End-to-end check of the configured file storage.

Uploads fail in the Template Library with a generic message that names the
Supabase bucket, the endpoint, and the S3 access keys.  This command replaces
guesswork with a step-by-step report: it validates the settings, then talks to
the configured bucket for real (head bucket, list, write, read, public
download, delete) and prints the provider's own error code plus the fix for it.

Usage:
    python manage.py check_file_storage              # full live check
    python manage.py check_file_storage --config-only  # settings only, no network
"""

import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from accounts.storage_diagnostics import describe_storage_exception, storage_failure_hint

TEST_OBJECT_PREFIX = "_nx_storage_check/"
MISSING_OBJECT_NAME = TEST_OBJECT_PREFIX + "this-object-does-not-exist"
PUBLIC_URL_TIMEOUT_SECONDS = 15


class Command(BaseCommand):
    help = (
        "Verify the Supabase bucket, endpoint, region, and S3 access keys used for uploaded "
        "files by writing and removing a small test object."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--config-only",
            action="store_true",
            help="Only validate the settings; do not contact Supabase.",
        )
        parser.add_argument(
            "--keep-test-object",
            action="store_true",
            help="Do not delete the uploaded test object (useful when debugging permissions).",
        )

    def handle(self, *args, **options):
        config_only = options["config_only"]
        keep_object = options["keep_test_object"]
        self.live_checks_ran = False

        self._print_configuration()

        failures = self._report_configuration_problems()
        if config_only:
            self.stdout.write("")
            if failures:
                raise CommandError(f"Configuration check failed ({failures} problem(s) found).")
            self.stdout.write("Configuration looks good (no network checks were run).")
            return

        if failures:
            self.stdout.write("")
            self._fail(
                "Fix the configuration problems above first; the live checks would only repeat them."
            )
            raise CommandError(f"Configuration check failed ({failures} problem(s) found).")

        live_failures = self._run_live_checks(keep_object=keep_object)

        self.stdout.write("")
        total = failures + live_failures
        if total:
            self._fail(f"File storage check failed ({total} problem(s) found).")
            raise CommandError("File storage is not usable yet; see the report above.")

        if self.live_checks_ran:
            self.stdout.write(
                self.style.SUCCESS("File storage is configured correctly and reachable.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("The file-storage settings look good (no S3 bucket was tested).")
            )

    # ----------------------------------------------------------------- helpers

    def _ok(self, message):
        self.stdout.write(f"  {self.style.SUCCESS('OK')}   {message}")

    def _warn(self, message):
        self.stdout.write(f"  {self.style.WARNING('WARN')} {message}")

    def _fail(self, message):
        self.stdout.write(f"  {self.style.ERROR('FAIL')} {message}")

    def _report_exception(self, summary, exc):
        self._fail(f"{summary}: {describe_storage_exception(exc)}")
        self.stdout.write(f"         -> {storage_failure_hint(exc)}")

    def _print_configuration(self):
        self.stdout.write("NExUS file storage check")
        backend = settings.STORAGES.get("default", {}).get("BACKEND", "unknown")
        self.stdout.write(f"  backend:      {backend}")
        self.stdout.write(f"  MEDIA_URL:    {settings.MEDIA_URL}")

        if getattr(settings, "USE_SUPABASE_STORAGE", False):
            self.stdout.write(f"  bucket:       {getattr(settings, 'SUPABASE_STORAGE_BUCKET', '')}")
            self.stdout.write(f"  endpoint:     {getattr(settings, 'SUPABASE_S3_ENDPOINT_URL', '')}")
            self.stdout.write(f"  region:       {getattr(settings, 'SUPABASE_S3_REGION_NAME', '')}")
            self.stdout.write(f"  public base:  {getattr(settings, 'SUPABASE_STORAGE_PUBLIC_URL', '') or '(not set)'}")
            self.stdout.write(
                "  access key:   "
                + _redact(_env("SUPABASE_S3_ACCESS_KEY_ID"))
                + "   secret key: "
                + _redact(_env("SUPABASE_S3_SECRET_ACCESS_KEY"))
            )
        else:
            self.stdout.write(
                "  USE_SUPABASE_STORAGE is not True, so uploads go to the local filesystem."
            )
        self.stdout.write("")

    def _report_configuration_problems(self):
        failures = 0
        supabase = getattr(settings, "SUPABASE_STORAGE", None)
        warnings = list(getattr(settings, "SUPABASE_STORAGE_CONFIGURATION_WARNINGS", ()))
        problems = list(getattr(supabase, "errors", ()))

        self.stdout.write("Configuration")
        if getattr(settings, "USE_SUPABASE_STORAGE", False):
            if problems:
                for problem in problems:
                    self._fail(problem)
                    failures += 1
            else:
                self._ok("Every Supabase Storage setting is present and well formed.")
        else:
            self._warn(
                "Supabase Storage is disabled. Production must set USE_SUPABASE_STORAGE=True, "
                "otherwise uploads are lost when the service restarts."
            )

        for warning in warnings:
            self._warn(warning)

        return failures

    def _run_live_checks(self, *, keep_object):
        self.stdout.write("")
        self.stdout.write("Live checks")
        failures = 0

        self.live_checks_ran = True
        storage = default_storage
        if not hasattr(storage, "connection") or not hasattr(storage, "bucket_name"):
            self.live_checks_ran = False
            self._warn(
                "The configured backend is "
                f"{type(storage).__module__}.{type(storage).__name__}, so there is no S3 bucket "
                "to test. Set USE_SUPABASE_STORAGE=True with the Supabase values to use remote "
                "storage."
            )
            return 0

        try:
            storage.connection  # Build the client now so bad credentials fail fast.
        except Exception as exc:  # noqa: BLE001 - the point is to report any failure
            self._report_exception("Could not build the S3 client", exc)
            return 1

        client = storage.connection.meta.client
        bucket = storage.bucket_name

        # 1. HeadBucket: proves endpoint + region + credentials + bucket.
        try:
            client.head_bucket(Bucket=bucket)
            self._ok(f"Bucket '{bucket}' is reachable with these credentials.")
        except Exception as exc:  # noqa: BLE001
            self._report_exception(f"HeadBucket on '{bucket}' failed", exc)
            failures += 1

        # 2. ListObjectsV2: proves read permission on the bucket.
        try:
            client.list_objects_v2(Bucket=bucket, MaxKeys=1)
            self._ok("The access key may list objects in the bucket.")
        except Exception as exc:  # noqa: BLE001
            self._report_exception("ListObjectsV2 failed", exc)
            failures += 1

        # 3. django-storages performs an existence check before every upload when
        #    file_overwrite is False, so a missing key must answer 404 and not an
        #    error that would abort the whole upload.
        missing_name = f"{MISSING_OBJECT_NAME}-{uuid.uuid4().hex}.txt"
        try:
            if storage.exists(missing_name):
                self._warn(f"A brand new key '{missing_name}' already reports as existing.")
            else:
                self._ok("Existence checks on new keys return 'missing' (as uploads expect).")
        except Exception as exc:  # noqa: BLE001
            self._report_exception("The existence check (HeadObject) failed", exc)
            failures += 1

        object_name = f"{TEST_OBJECT_PREFIX}{uuid.uuid4().hex}.txt"
        stored_name = ""
        try:
            stored_name = storage.save(object_name, ContentFile(b"nexus storage check"))
            self._ok(f"Uploaded a test object ('{stored_name}').")
        except Exception as exc:  # noqa: BLE001
            self._report_exception("Writing a test object failed", exc)
            failures += 1
            return failures

        try:
            with storage.open(stored_name) as handle:
                if handle.read() == b"nexus storage check":
                    self._ok("The test object reads back with the expected contents.")
                else:
                    self._fail("The test object read back different contents.")
                    failures += 1
        except Exception as exc:  # noqa: BLE001
            self._report_exception("Reading the test object back failed", exc)
            failures += 1

        public_url = ""
        try:
            public_url = storage.url(stored_name)
        except Exception as exc:  # noqa: BLE001
            self._report_exception("Building the public URL failed", exc)
            failures += 1

        if public_url:
            status = _fetch_status(public_url)
            if status == 200:
                self._ok(f"Public download works: {public_url}")
            elif status is None:
                self._warn(f"Could not reach the public URL to confirm it works: {public_url}")
            else:
                self._fail(f"Public download returned HTTP {status}: {public_url}")
                self.stdout.write(
                    "         -> The template links will be broken. In Supabase, open Storage and "
                    "make sure the bucket is marked public."
                )
                failures += 1

        if keep_object:
            self._warn(f"Keeping the test object for inspection: {stored_name}")
        else:
            try:
                storage.delete(stored_name)
                self._ok("Removed the test object again.")
            except Exception as exc:  # noqa: BLE001
                self._report_exception("Deleting the test object failed", exc)
                failures += 1

        return failures


def _env(name):
    return (os.environ.get(name) or "").strip()


def _redact(value):
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}…{value[-2:]} ({len(value)} chars)"


def _fetch_status(url):
    request = Request(url, headers={"User-Agent": "nexus-storage-check"})
    try:
        with urlopen(request, timeout=PUBLIC_URL_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status
    except HTTPError as exc:
        return exc.code
    except (URLError, OSError, ValueError):
        return None
