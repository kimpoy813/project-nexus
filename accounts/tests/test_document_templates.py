"""Regression tests for the admin Template Library upload flow."""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from details.models import DocumentTemplate

from . import factories


class DocumentTemplateUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("template_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client = factories.make_client(self.admin)

    def _payload(self, **overrides):
        payload = {
            "title": "Extension Work Plan",
            "category": DocumentTemplate.Category.PROPOSAL,
            "version_label": "2026 v1",
            "description": "Official office template.",
            "is_active": "on",
            "file": SimpleUploadedFile(
                "extension-work-plan.docx",
                b"a small document for upload testing",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }
        payload.update(overrides)
        return payload

    def test_admin_can_upload_a_template(self):
        response = self.client.post(reverse("document_template_create"), self._payload())

        self.assertRedirects(response, reverse("document_templates_list"))
        template = DocumentTemplate.objects.get(title="Extension Work Plan")
        self.assertEqual(template.category, DocumentTemplate.Category.PROPOSAL)
        self.assertTrue(template.is_active)
        self.assertTrue(template.file.name.startswith("office_templates/"))

    def test_invalid_field_lengths_are_rendered_as_form_errors_not_database_errors(self):
        response = self.client.post(
            reverse("document_template_create"),
            self._payload(title="x" * 181),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ensure this value has at most 180 characters")
        self.assertFalse(DocumentTemplate.objects.exists())

    @override_settings(
        MEDIA_STORAGE_CONFIGURATION_ERROR=(
            "Supabase file storage is enabled but is missing: SUPABASE_S3_ENDPOINT_URL."
        )
    )
    def test_incomplete_supabase_configuration_shows_an_actionable_error_without_uploading(self):
        response = self.client.post(
            reverse("document_template_create"), self._payload(), follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "File uploads are not configured yet.")
        self.assertContains(response, "Your file was not uploaded because secure file storage")
        self.assertFalse(DocumentTemplate.objects.exists())

    def test_storage_outage_is_logged_and_shown_as_a_message_instead_of_a_500(self):
        with patch(
            "accounts.views.builders.DocumentTemplateForm.save",
            side_effect=OSError("storage unavailable"),
        ):
            with self.assertLogs("accounts.views.builders", level="ERROR"):
                response = self.client.post(reverse("document_template_create"), self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The template could not be uploaded to file storage")
        self.assertFalse(DocumentTemplate.objects.exists())

    @override_settings(MEDIA_STORAGE_CONFIGURATION_ERROR="Supabase file storage is incomplete.")
    def test_replacing_a_file_with_incomplete_storage_keeps_the_existing_template_intact(self):
        template = DocumentTemplate.objects.create(
            title="Existing template",
            category=DocumentTemplate.Category.OTHER,
            file=SimpleUploadedFile("existing.docx", b"old"),
        )

        response = self.client.post(
            reverse("document_template_edit", args=[template.pk]),
            self._payload(title="Attempted replacement"),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "office_templates/existing.docx")
        template.refresh_from_db()
        self.assertEqual(template.title, "Existing template")
        self.assertEqual(template.file.name, "office_templates/existing.docx")

    @override_settings(MEDIA_STORAGE_CONFIGURATION_ERROR="Supabase file storage is incomplete.")
    def test_admin_can_still_change_template_metadata_without_replacing_its_file(self):
        template = DocumentTemplate.objects.create(
            title="Old template",
            category=DocumentTemplate.Category.OTHER,
            file=SimpleUploadedFile("old.docx", b"old"),
        )

        response = self.client.post(
            reverse("document_template_edit", args=[template.pk]),
            {
                "title": "Renamed template",
                "category": DocumentTemplate.Category.REPORT,
                "version_label": "v2",
                "description": "Updated description",
                # Deliberately no file: this is a metadata-only update.
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("document_templates_list"))
        template.refresh_from_db()
        self.assertEqual(template.title, "Renamed template")
        self.assertEqual(template.category, DocumentTemplate.Category.REPORT)
        self.assertEqual(template.file.name, "office_templates/old.docx")
