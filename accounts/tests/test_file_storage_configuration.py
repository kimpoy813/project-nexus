"""Regression tests for the Supabase Storage configuration checks.

The Template Library can only report "the template could not be uploaded to
file storage"; these tests pin down that the deployment settings catch the
usual misconfigurations *before* an upload is attempted, and that the failure
message finally names the provider error.
"""

import importlib
import io
import os
from unittest.mock import patch

from botocore.exceptions import ClientError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from accounts.storage_diagnostics import describe_storage_exception, storage_failure_hint
from conf.storage_config import build_supabase_storage_config

from . import factories

VALID_ENV = {
    "SUPABASE_STORAGE_BUCKET": "nexus-media",
    "SUPABASE_S3_ENDPOINT_URL": "https://abcdefghijklm.supabase.co/storage/v1/s3",
    "SUPABASE_S3_ACCESS_KEY_ID": "0123456789abcdef0123456789abcdef",
    "SUPABASE_S3_SECRET_ACCESS_KEY": "f" * 64,
    "SUPABASE_S3_REGION_NAME": "ap-southeast-1",
    "SUPABASE_STORAGE_PUBLIC_URL": (
        "https://abcdefghijklm.supabase.co/storage/v1/object/public/nexus-media"
    ),
}


class SupabaseStorageConfigTests(SimpleTestCase):
    def build(self, **overrides):
        env = dict(VALID_ENV)
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return build_supabase_storage_config(env)

    def assertErrorContains(self, config, fragment):
        self.assertTrue(
            any(fragment in error for error in config.errors),
            f"no error containing {fragment!r} in {config.errors!r}",
        )

    def test_a_valid_configuration_is_accepted_without_complaints(self):
        config = self.build()

        self.assertTrue(config.is_usable)
        self.assertEqual(config.errors, ())
        self.assertEqual(config.warnings, ())
        self.assertEqual(config.bucket, "nexus-media")
        self.assertEqual(config.endpoint_url, "https://abcdefghijklm.supabase.co/storage/v1/s3")
        self.assertEqual(config.region_name, "ap-southeast-1")
        self.assertEqual(
            config.custom_domain,
            "abcdefghijklm.supabase.co/storage/v1/object/public/nexus-media",
        )

    def test_values_pasted_with_whitespace_are_normalized(self):
        config = self.build(
            SUPABASE_STORAGE_BUCKET=" nexus-media\n",
            SUPABASE_S3_ENDPOINT_URL="  https://abcdefghijklm.supabase.co/storage/v1/s3/  ",
            SUPABASE_S3_REGION_NAME=" AP-Southeast-1 ",
            SUPABASE_STORAGE_PUBLIC_URL=(
                "https://abcdefghijklm.supabase.co/storage/v1/object/public/nexus-media/ "
            ),
        )

        self.assertTrue(config.is_usable)
        self.assertEqual(config.bucket, "nexus-media")
        self.assertEqual(config.endpoint_url, "https://abcdefghijklm.supabase.co/storage/v1/s3")
        self.assertEqual(config.region_name, "ap-southeast-1")
        self.assertFalse(config.public_url.endswith("/"))

    def test_missing_values_keep_the_original_actionable_message(self):
        config = self.build(SUPABASE_S3_ACCESS_KEY_ID="", SUPABASE_S3_ENDPOINT_URL="")

        self.assertFalse(config.is_usable)
        self.assertErrorContains(config, "is missing: SUPABASE_S3_ENDPOINT_URL")
        self.assertErrorContains(config, "SUPABASE_S3_ACCESS_KEY_ID")

    def test_placeholder_endpoint_is_rejected(self):
        config = self.build(
            SUPABASE_S3_ENDPOINT_URL="https://PROJECT_REF.supabase.co/storage/v1/s3",
            SUPABASE_STORAGE_PUBLIC_URL=(
                "https://PROJECT_REF.supabase.co/storage/v1/object/public/nexus-media"
            ),
        )

        self.assertFalse(config.is_usable)
        self.assertErrorContains(config, "placeholder")

    def test_endpoint_without_scheme_is_rejected(self):
        config = self.build(SUPABASE_S3_ENDPOINT_URL="abcdefghijklm.supabase.co/storage/v1/s3")

        self.assertErrorContains(config, "not a valid URL")

    def test_endpoint_with_bucket_appended_is_rejected(self):
        config = self.build(
            SUPABASE_S3_ENDPOINT_URL="https://abcdefghijklm.supabase.co/storage/v1/s3/nexus-media"
        )

        self.assertErrorContains(config, "Do not append the bucket name")

    def test_object_url_used_as_endpoint_is_rejected(self):
        config = self.build(
            SUPABASE_S3_ENDPOINT_URL=(
                "https://abcdefghijklm.supabase.co/storage/v1/object/public/nexus-media"
            )
        )

        self.assertErrorContains(config, "public object URL, not the S3 API")

    def test_api_key_pasted_into_the_s3_credentials_is_rejected(self):
        config = self.build(SUPABASE_S3_ACCESS_KEY_ID="eyJhbGciOiJIUzI1NiJ9.abc.def")

        self.assertErrorContains(config, "not valid for the S3 protocol")

    def test_identical_access_key_and_secret_are_rejected(self):
        config = self.build(SUPABASE_S3_SECRET_ACCESS_KEY=VALID_ENV["SUPABASE_S3_ACCESS_KEY_ID"])

        self.assertErrorContains(config, "are identical")

    def test_bucket_name_used_as_access_key_is_rejected(self):
        config = self.build(SUPABASE_S3_ACCESS_KEY_ID="nexus-media")

        self.assertErrorContains(config, "set to the bucket name")

    def test_placeholder_region_is_rejected(self):
        config = self.build(SUPABASE_S3_REGION_NAME="project_region")

        self.assertErrorContains(config, "placeholder value 'project_region'")

    def test_missing_region_warns_but_does_not_block_uploads(self):
        config = self.build(SUPABASE_S3_REGION_NAME=None)

        self.assertTrue(config.is_usable)
        self.assertEqual(config.region_name, "us-east-1")
        self.assertTrue(any("SUPABASE_S3_REGION_NAME is not set" in w for w in config.warnings))

    def test_public_url_pointing_at_another_bucket_is_rejected(self):
        config = self.build(
            SUPABASE_STORAGE_PUBLIC_URL=(
                "https://abcdefghijklm.supabase.co/storage/v1/object/public/other-bucket"
            )
        )

        self.assertFalse(config.is_usable)
        self.assertErrorContains(config, "points at bucket 'other-bucket'")

    def test_public_url_pointing_at_another_project_is_rejected(self):
        config = self.build(
            SUPABASE_STORAGE_PUBLIC_URL=(
                "https://zzzzzzzzzzzzz.supabase.co/storage/v1/object/public/nexus-media"
            )
        )

        self.assertErrorContains(config, "different Supabase projects")

    def test_a_custom_domain_public_url_only_warns(self):
        config = self.build(SUPABASE_STORAGE_PUBLIC_URL="https://cdn.example.org/nexus-media")

        self.assertTrue(config.is_usable)
        self.assertTrue(any("custom domain" in w for w in config.warnings))

    def test_missing_public_url_warns_but_keeps_uploads_working(self):
        config = self.build(SUPABASE_STORAGE_PUBLIC_URL=None)

        self.assertTrue(config.is_usable)
        self.assertTrue(any("MEDIA_URL stays /media/" in w for w in config.warnings))


class SettingsWiringTests(SimpleTestCase):
    """The validated values must reach the storage backend."""

    def load_settings(self, env):
        import conf.settings as settings_module

        with patch.dict(os.environ, env, clear=True):
            return importlib.reload(settings_module)

    def test_valid_configuration_selects_the_s3_backend_without_acl_or_checksums(self):
        settings_module = self.load_settings({"USE_SUPABASE_STORAGE": "True", **VALID_ENV})
        try:
            options = settings_module.STORAGES["default"]["OPTIONS"]
            self.assertEqual(
                settings_module.STORAGES["default"]["BACKEND"],
                "storages.backends.s3.S3Storage",
            )
            self.assertEqual(settings_module.MEDIA_STORAGE_CONFIGURATION_ERROR, "")

            # Supabase does not implement S3 ACLs, so no x-amz-acl is sent.
            self.assertNotIn("default_acl", options)

            # boto3 >= 1.36 would otherwise attach checksum headers Supabase's
            # S3 layer does not implement.
            client_config = options["client_config"]
            self.assertEqual(client_config.request_checksum_calculation, "when_required")
            self.assertEqual(client_config.response_checksum_validation, "when_required")
            self.assertEqual(client_config.s3["addressing_style"], "path")

            self.assertEqual(settings_module.MEDIA_URL, VALID_ENV["SUPABASE_STORAGE_PUBLIC_URL"] + "/")
        finally:
            self.load_settings({})

    def test_malformed_endpoint_falls_back_to_local_storage_with_an_explanation(self):
        settings_module = self.load_settings(
            {
                "USE_SUPABASE_STORAGE": "True",
                **VALID_ENV,
                "SUPABASE_S3_ENDPOINT_URL": "abcdefghijklm.supabase.co/storage/v1/s3",
            }
        )
        try:
            self.assertEqual(
                settings_module.STORAGES["default"]["BACKEND"],
                "django.core.files.storage.FileSystemStorage",
            )
            self.assertIn("not a valid URL", settings_module.MEDIA_STORAGE_CONFIGURATION_ERROR)
            self.assertEqual(settings_module.MEDIA_URL, "/media/")
        finally:
            self.load_settings({})


class StorageDiagnosticsTests(SimpleTestCase):
    def make_client_error(self, code, message="", status=403):
        return ClientError(
            {
                "Error": {"Code": code, "Message": message},
                "ResponseMetadata": {"HTTPStatusCode": status},
            },
            "PutObject",
        )

    def test_client_error_is_reported_with_code_and_status(self):
        described = describe_storage_exception(
            self.make_client_error("SignatureDoesNotMatch", "Check your key and signing method")
        )

        self.assertIn("SignatureDoesNotMatch", described)
        self.assertIn("HTTP 403", described)
        self.assertIn("Check your key and signing method", described)

    def test_hints_point_at_the_right_setting(self):
        self.assertIn(
            "SUPABASE_S3_REGION_NAME",
            storage_failure_hint(self.make_client_error("AccessDenied", "Invalid Region")),
        )
        self.assertIn(
            "SUPABASE_STORAGE_BUCKET",
            storage_failure_hint(self.make_client_error("NoSuchBucket", "The specified bucket")),
        )
        self.assertIn(
            "S3 access keys",
            storage_failure_hint(self.make_client_error("SignatureDoesNotMatch")),
        )

    def test_a_bodiless_head_failure_still_gets_status_based_advice(self):
        # HeadBucket/HeadObject replies carry no error body, so botocore only
        # knows the HTTP status. That must still point at the keys/region.
        head_failure = ClientError(
            {
                "Error": {"Code": "403", "Message": "Forbidden"},
                "ResponseMetadata": {"HTTPStatusCode": 403},
            },
            "HeadBucket",
        )

        hint = storage_failure_hint(head_failure)

        self.assertIn("SUPABASE_S3_REGION_NAME", hint)
        self.assertIn("S3 access key pair", hint)

    def test_unknown_errors_fall_back_to_the_check_command(self):
        self.assertIn("check_file_storage", storage_failure_hint(OSError("boom")))


class CheckFileStorageCommandTests(SimpleTestCase):
    @staticmethod
    def _capture_output(*args):
        buffer = io.StringIO()
        with patch("sys.stdout", buffer):
            call_command(*args)
        return buffer.getvalue()

    def test_configuration_only_run_reports_the_local_filesystem(self):
        out = self._capture_output("check_file_storage", "--config-only")

        self.assertIn("NExUS file storage check", out)
        self.assertIn("USE_SUPABASE_STORAGE is not True", out)

    def test_a_full_run_skips_live_checks_without_an_s3_backend(self):
        # Tests use in-memory storage: the command must say so instead of
        # crashing on the missing boto3 client.
        out = self._capture_output("check_file_storage")

        self.assertIn("no S3 bucket to test", out)
        self.assertIn("no S3 bucket was tested", out)

    @override_settings(
        USE_SUPABASE_STORAGE=True,
        MEDIA_STORAGE_CONFIGURATION_ERROR="SUPABASE_S3_ENDPOINT_URL is not a valid URL ('x').",
    )
    def test_a_broken_configuration_fails_the_command(self):
        with self.assertRaises(CommandError):
            call_command("check_file_storage", "--config-only")


class TemplateUploadErrorMessageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("storage_message_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client = factories.make_client(self.admin)

    def _payload(self):
        return {
            "title": "Extension Work Plan",
            "category": "PROPOSAL",
            "version_label": "2026 v1",
            "description": "Official office template.",
            "is_active": "on",
            "file": SimpleUploadedFile(
                "extension-work-plan.docx",
                b"a small document for upload testing",
                content_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
            ),
        }

    def test_provider_error_code_and_hint_are_shown_to_the_administrator(self):
        error = ClientError(
            {
                "Error": {
                    "Code": "SignatureDoesNotMatch",
                    "Message": "The request signature we calculated does not match.",
                },
                "ResponseMetadata": {"HTTPStatusCode": 403},
            },
            "PutObject",
        )

        with patch("accounts.views.builders.DocumentTemplateForm.save", side_effect=error):
            with self.assertLogs("accounts.views.builders", level="ERROR"):
                response = self.client.post(reverse("document_template_create"), self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The template could not be uploaded to file storage")
        self.assertContains(response, "SignatureDoesNotMatch")
        self.assertContains(response, "S3 access keys")
