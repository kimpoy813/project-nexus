"""
Admin-managed replacements for the bundled document templates.

The proposal flow generates its DOCX/XLSX downloads from templates that ship
under ``proposals/template_files/``. Administrators may replace any of them
through the admin screens; these tests pin down that behaviour:

* the resolver prefers the admin upload and falls back to the bundled copy
* generated documents and downloads actually use the replacement
* uploads are validated (right slot, right file type) and can be reset
* the admin screens stay admin-only
"""

import io
import zipfile

from django.contrib import admin as django_admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories
from openpyxl import load_workbook

from .models import Proposal, ProposalTemplateOverride
from .template_store import (
    TEMPLATE_FILES,
    TemplateNotFound,
    bundled_path,
    is_valid_replacement,
    open_template,
)
from .docx_forms import build_extension_form_docx


def docx_bytes_with_marker(marker):
    """A real .docx carrying one paragraph with ``marker``."""
    from docx import Document

    document = Document()
    document.add_paragraph(marker)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def xlsx_bytes_with_marker_sheet(marker):
    """A real .xlsx whose first sheet is named ``marker``."""
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.title = marker[:31]
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class TemplateStoreTests(TestCase):
    """The resolver: override wins, bundled copy is the fallback."""

    def test_every_registered_slot_has_a_bundled_file(self):
        for key in TEMPLATE_FILES:
            with self.subTest(key=key):
                self.assertTrue(bundled_path(key).exists(), f"{key} is missing")

    def test_without_an_override_the_bundled_file_is_used(self):
        stream, filename, is_override = open_template("form2_training_design_template.docx")
        try:
            self.assertFalse(is_override)
            self.assertEqual(filename, "form2_training_design_template.docx")
            self.assertEqual(stream.read(), bundled_path("form2_training_design_template.docx").read_bytes())
        finally:
            stream.close()

    def test_an_override_replaces_the_bundled_file(self):
        marker = docx_bytes_with_marker("OVERRIDE-RESOLVER-MARKER")
        ProposalTemplateOverride.objects.create(
            key="form2_training_design_template.docx",
            file=SimpleUploadedFile("replacement.docx", marker),
        )

        stream, filename, is_override = open_template("form2_training_design_template.docx")
        try:
            self.assertTrue(is_override)
            self.assertEqual(stream.read(), marker)
        finally:
            stream.close()

    def test_a_missing_key_is_rejected(self):
        with self.assertRaises(ValueError):
            open_template("not_a_template.docx")

    def test_validation_requires_the_slot_extension(self):
        self.assertTrue(is_valid_replacement("form1_project_template.docx", "anything.DOCX"))
        self.assertFalse(is_valid_replacement("form1_project_template.docx", "anything.xlsx"))
        self.assertFalse(is_valid_replacement("project_work_plan_template.xlsx", "anything.docx"))
        self.assertFalse(is_valid_replacement("unknown_key.docx", "anything.docx"))


class GeneratedDocumentOverrideTests(TestCase):
    """Generated downloads must use the admin replacement."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("tpl_owner", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(
            created_by=self.owner,
            title="Template Override Proposal",
            extension_type="COMMUNITY_BASED",
            scope_type="PROJECT",
        )

    def test_the_docx_generator_uses_the_override(self):
        marker = docx_bytes_with_marker("OVERRIDE-DOCX-MARKER")
        ProposalTemplateOverride.objects.create(
            key="form2_training_design_template.docx",
            file=SimpleUploadedFile("replacement.docx", marker),
        )

        data = build_extension_form_docx(proposal=self.proposal)

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        self.assertIn("OVERRIDE-DOCX-MARKER", xml)

    def test_the_work_plan_download_uses_the_override(self):
        marker = xlsx_bytes_with_marker_sheet("OVERRIDE-MARKER-SHEET")
        ProposalTemplateOverride.objects.create(
            key="project_work_plan_template.xlsx",
            file=SimpleUploadedFile("replacement.xlsx", marker),
        )

        client = factories.make_client(self.owner)
        response = client.get(reverse("download_work_plan_template", args=[self.proposal.id]))

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.content))
        self.assertIn("OVERRIDE-MARKER-SHEET", workbook.sheetnames)

    def test_downloads_still_work_without_any_override(self):
        client = factories.make_client(self.owner)
        for name in (
            "download_work_plan_template",
            "download_gantt_chart_template",
            "download_funding_template",
        ):
            with self.subTest(view=name):
                response = client.get(reverse(name, args=[self.proposal.id]))
                self.assertEqual(
                    response.status_code,
                    200,
                    f"{name} should serve the bundled template",
                )


class AdminTemplateScreensTests(TestCase):
    """The 'Proposal Templates' screen: admin-only, validated, resettable."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user, cls.admin_client = factories.admin()
        cls.faculty = factories.make_user("tpl_faculty", Profile.ROLE_FACULTY)

    def test_only_admins_can_open_the_screen(self):
        self.assertEqual(
            self.admin_client.get(reverse("proposal_templates_list")).status_code, 200
        )
        faculty_status = factories.make_client(self.faculty).get(
            reverse("proposal_templates_list")
        ).status_code
        self.assertIn(faculty_status, (302, 403))

    def test_the_screen_lists_every_template_slot(self):
        html = self.admin_client.get(reverse("proposal_templates_list")).content.decode()
        for key, (label, _ext) in TEMPLATE_FILES.items():
            with self.subTest(key=key):
                self.assertIn(label, html)

    def test_a_valid_upload_replaces_the_template(self):
        marker = docx_bytes_with_marker("UPLOADED-BY-ADMIN")
        response = self.admin_client.post(
            reverse("proposal_template_replace"),
            {
                "key": "form1_project_template.docx",
                "file": SimpleUploadedFile("new_form1.docx", marker),
                "notes": "2026 revision",
            },
        )
        self.assertEqual(response.status_code, 302)

        override = ProposalTemplateOverride.objects.get(key="form1_project_template.docx")
        self.assertEqual(override.notes, "2026 revision")
        self.assertEqual(override.uploaded_by, self.admin_user)

    def test_a_wrong_extension_is_refused(self):
        response = self.admin_client.post(
            reverse("proposal_template_replace"),
            {
                "key": "project_work_plan_template.xlsx",
                "file": SimpleUploadedFile("not-a-spreadsheet.docx", docx_bytes_with_marker("X")),
            },
        )
        self.assertEqual(response.status_code, 302)  # back to the list, with an error
        self.assertFalse(
            ProposalTemplateOverride.objects.filter(key="project_work_plan_template.xlsx").exists()
        )

    def test_a_non_office_file_is_refused(self):
        response = self.admin_client.post(
            reverse("proposal_template_replace"),
            {
                "key": "form1_project_template.docx",
                "file": SimpleUploadedFile("plain.docx", b"this is not a zip archive"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ProposalTemplateOverride.objects.filter(key="form1_project_template.docx").exists()
        )

    def test_reset_restores_the_bundled_template(self):
        ProposalTemplateOverride.objects.create(
            key="clear_summary_template.docx",
            file=SimpleUploadedFile("replacement.docx", docx_bytes_with_marker("X")),
        )

        response = self.admin_client.post(
            reverse("proposal_template_reset"), {"key": "clear_summary_template.docx"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ProposalTemplateOverride.objects.filter(key="clear_summary_template.docx").exists()
        )

    def test_reset_rejects_unknown_slots(self):
        response = self.admin_client.post(
            reverse("proposal_template_reset"), {"key": "not_a_template.docx"}
        )
        self.assertEqual(response.status_code, 302)

    def test_replacing_twice_updates_the_same_slot(self):
        first = docx_bytes_with_marker("FIRST")
        second = docx_bytes_with_marker("SECOND")
        for payload in (first, second):
            self.admin_client.post(
                reverse("proposal_template_replace"),
                {
                    "key": "form2_training_design_template.docx",
                    "file": SimpleUploadedFile("r.docx", payload),
                },
            )

        self.assertEqual(
            ProposalTemplateOverride.objects.filter(key="form2_training_design_template.docx").count(),
            1,
        )
        stream, _name, is_override = open_template("form2_training_design_template.docx")
        try:
            self.assertTrue(is_override)
            self.assertEqual(stream.read(), second)
        finally:
            stream.close()


class DjangoAdminRegistrationTests(TestCase):
    """The overrides are also editable through the built-in Django admin."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        cls.superuser = get_user_model().objects.create_superuser(
            username="nx_superuser", email="su@example.com", password="sup3r-Secret"
        )

    def test_the_model_is_registered(self):
        self.assertIn(ProposalTemplateOverride, django_admin.site._registry)

    def test_the_changelist_and_add_form_are_reachable(self):
        client = factories.make_client(self.superuser)
        changelist = client.get("/admin/proposals/proposaltemplateoverride/")
        self.assertEqual(changelist.status_code, 200)
        add_form = client.get("/admin/proposals/proposaltemplateoverride/add/")
        self.assertEqual(add_form.status_code, 200)
