"""System-wide protection against file-storage upload failures."""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile

from . import factories


class UploadStorageErrorMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("upload_error_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client = factories.make_client(self.admin)

    def _personnel_payload(self):
        return {
            "name": "Extension Staff",
            "position": "Coordinator",
            "email": "staff@example.com",
            "photo": SimpleUploadedFile("staff.jpg", b"not a real image", content_type="image/jpeg"),
        }

    @override_settings(MEDIA_STORAGE_CONFIGURATION_ERROR="Supabase file storage is incomplete.")
    def test_incomplete_storage_blocks_other_upload_pages_before_any_record_is_created(self):
        with patch("accounts.views.content.Personnel.objects.create") as create:
            response = self.client.post(
                reverse("personnel_create"), self._personnel_payload(), follow=True
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your file was not uploaded because secure file storage")
        create.assert_not_called()

    def test_storage_outage_in_another_upload_view_returns_to_the_form_instead_of_500(self):
        # Django's test client remembers the original exception before the
        # middleware replaces its 500 response. A browser receives the safe
        # redirect, so mirror browser behavior for this request.
        self.client.raise_request_exception = False

        with patch(
            "accounts.views.content.Personnel.objects.create",
            side_effect=OSError("storage unavailable"),
        ):
            with self.assertLogs("accounts.middleware", level="ERROR"):
                response = self.client.post(
                    reverse("personnel_create"), self._personnel_payload(), follow=True
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your file could not be saved right now")
